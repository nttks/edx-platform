"""
Management command to send reminder email for all biz students who have not submitted on target sections.
"""
import logging
import time
from optparse import make_option

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.test.client import RequestFactory
from django.utils import translation
from xmodule.modulestore.django import modulestore

from biz.djangoapps.ga_achievement.achievement_store import ScoreStore
from biz.djangoapps.ga_achievement.management.commands.update_biz_score_status import (
    GroupedTargetSections, get_grouped_target_sections,
)
from biz.djangoapps.ga_achievement.models import ScoreBatchStatus, SubmissionReminderBatchStatus
from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.ga_contract_operation.models import ContractReminderMail
from biz.djangoapps.ga_contract_operation.utils import replace_braces
from biz.djangoapps.ga_invitation.models import ContractRegister
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.decorators import handle_command_exception, ExitWithWarning
from courseware.model_data import FieldDataCache
from courseware.module_render import get_module_for_descriptor
from microsite_configuration import microsite
from student.models import UserStanding, CourseEnrollment

log = logging.getLogger(__name__)


class ContractHasNoCourses(Exception):
    """
    This exception is raised in the case where contract has no courses
    """
    pass


class ContractReminderMailNotFound(Exception):
    """
    This exception is raised in the case where reminder mail template (including default template) is not found
    """
    pass


class InvalidReminderEmailDays(Exception):
    """
    This exception is raised in the case where the value of the reminder e-mail days is invalid
    """
    pass


class ScoreBatchNotFinished(Exception):
    """
    This exception is raised in the case where score status process has not finished yet today
    """
    pass


class SendMailError(Exception):
    """
    This exception is raised in the case where sending email failed accidentally
    """
    pass


class Command(BaseCommand):
    """
    Send reminder email for submission.
    """
    help = """
    Usage: python manage.py lms --settings=aws send_submission_reminder_email [--debug] [--excludes=<exclude_ids>|<contract_id>]
    """

    option_list = BaseCommand.option_list + (
        make_option('--debug',
                    default=False,
                    action='store_true',
                    help='Use debug log'),
        make_option('--excludes',
                    default=None,
                    action='store',
                    help='Specify contract ids to exclude as comma-delimited integers (like 1 or 1,2)'),
    )

    @handle_command_exception(settings.BIZ_SEND_SUBMISSION_REMINDER_COMMAND_OUTPUT)
    def handle(self, *args, **options):
        # Note: BaseCommand translations are deactivated by default, so activate here
        translation.activate(settings.LANGUAGE_CODE)

        debug = options.get('debug')
        if debug:
            stream = logging.StreamHandler(self.stdout)
            log.addHandler(stream)
            log.setLevel(logging.DEBUG)
        exclude_ids = options.get('excludes') or []
        if exclude_ids:
            try:
                exclude_ids = map(int, exclude_ids.split(','))
            except ValueError:
                raise CommandError("excludes should be specified as comma-delimited integers (like 1 or 1,2).")
        log.debug(u"exclude_ids={}".format(exclude_ids))

        if len(args) > 1:
            raise CommandError("This command requires one or no arguments: |<contract_id>|")

        contract_id = args[0] if len(args) > 0 else None
        if contract_id:
            if exclude_ids:
                raise CommandError("Cannot specify exclude_ids and contract_id at the same time.")
            try:
                contracts = [Contract.objects.enabled().get(pk=contract_id)]
            except Contract.DoesNotExist:
                raise ExitWithWarning(
                    "The specified contract does not exist or is not active. contract_id={}".format(contract_id)
                )
        else:
            contracts = Contract.objects.enabled().all().exclude(id__in=exclude_ids).order_by('id')
        log.debug(u"contract_ids=[{}]".format(','.join([str(contract.id) for contract in contracts])))

        start_datetime = datetime_utils.timezone_now()
        error_flag = False
        for contract in contracts:
            # Check if send_submission_reminder option is available
            if not contract.can_send_submission_reminder:
                log.warning(
                    u"Option for send_submission_reminder is not available for the contract(id={}), so skip.".format(contract.id))
                continue
            # Note: If contract has contract-auth but send_mail option is False, skip it. (#1816)
            elif not contract.can_send_mail:
                log.warning(
                    u"Contract(id={}) has contract-auth but send_mail option is False, so skip.".format(contract.id))
                continue

            try:
                log.info(
                    u"Command send_submission_reminder_email for contract(id={}) is now processing...".format(contract.id))
                SubmissionReminderBatchStatus.save_for_started(contract.id)
                send_success = 0
                send_failure = 0

                # Get courses in contract
                courses = []
                for contract_detail in contract.details.all().order_by('id'):
                    # Check if course exists in modulestore
                    course = modulestore().get_course(contract_detail.course_id)
                    if not course:
                        log.warning(
                            u"This course does not exist in modulestore. contract_id={}, course_id={}".format(
                                contract.id, unicode(contract_detail.course_id)))
                        continue
                    # Check if update_biz_score_status process has finished today
                    if not ScoreBatchStatus.finished_today(contract.id, course.id):
                        raise ScoreBatchNotFinished()
                    courses.append(course)

                if not courses:
                    raise ContractHasNoCourses()

                # Calculate target min and max datetime
                contract_mail = ContractReminderMail.get_or_default(contract,
                                                                    ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER)
                if not contract_mail:
                    raise ContractReminderMailNotFound()
                reminder_email_days = contract_mail.reminder_email_days
                if reminder_email_days < ContractReminderMail.REMINDER_EMAIL_DAYS_MIN_VALUE or ContractReminderMail.REMINDER_EMAIL_DAYS_MAX_VALUE < reminder_email_days:
                    raise InvalidReminderEmailDays()
                target_day_min, target_day_max = datetime_utils.min_and_max_of_date(start_datetime.date(), reminder_email_days)

                # Get target users
                for contract_register in ContractRegister.find_input_and_register_by_contract(contract.id):
                    start = time.clock()
                    user = contract_register.user
                    # Skip if user already resigned
                    if hasattr(user, 'standing') and user.standing \
                            and user.standing.account_status == UserStanding.ACCOUNT_DISABLED:
                        continue
                    # Skip if user already masked (#1970)
                    if '@' not in user.email:
                        log.warning(u"User({}) has been already masked, so skip.".format(user.id))
                        continue

                    # Extract sections whose due dates are approaching within the specified days
                    target_courses_per_user = []
                    for course in courses:
                        # Exclude course in which user don't enroll at this time
                        course_enrollment = CourseEnrollment.get_enrollment(user, course.id)
                        if not course_enrollment or not course_enrollment.is_active:
                            continue

                        # In self-paced course, due date differs by user (#1240)
                        if course.self_paced:
                            request = RequestFactory().get('/')
                            field_data_cache = FieldDataCache([course], course.id, user)
                            course = get_module_for_descriptor(user, request, course, field_data_cache, course.id, course=course)

                        # Get user's score
                        score_store = ScoreStore(contract.id, unicode(course.id))
                        record = score_store.get_record_document_by_username(user.username)

                        # Choice 'Not Attempted' section from user's score
                        grouped_target_sections_per_user = GroupedTargetSections()
                        for target_section in get_grouped_target_sections(course).target_sections:
                            due = target_section.section_descriptor.due
                            if due and target_day_min <= due <= target_day_max:
                                # Note: record is None if user enrolled after update_biz_score_status finished. (#1980)
                                if record is None or record.get(target_section.column_name) == ScoreStore.VALUE__NOT_ATTEMPTED:
                                    grouped_target_sections_per_user.append(target_section)
                        if grouped_target_sections_per_user.keys():
                            target_courses_per_user.append(grouped_target_sections_per_user)

                    # Send email for user
                    if target_courses_per_user:
                        try:
                            send_reminder_email(contract, user, target_courses_per_user, debug)
                            send_success += 1
                            end = time.clock()
                            log.debug(u"Processed time to send submission reminder email ... {:.2f}s".format(end - start))
                        except Exception as ex:
                            send_failure += 1
                            log.error(u"Error occurred while sending reminder email: {}".format(ex))

                if send_failure > 0:
                    raise SendMailError()

            # Warning
            except ContractHasNoCourses:
                log.warning(u"Contract(id={}) has no valid courses.".format(contract.id))
                SubmissionReminderBatchStatus.save_for_error(contract.id, send_success, send_failure)

            # Error (need recovery)
            except ScoreBatchNotFinished:
                error_flag = True
                log.error(u"Score batches for the contract(id={}) have not finished yet today.".format(contract.id))
                SubmissionReminderBatchStatus.save_for_error(contract.id, send_success, send_failure)
            except ContractReminderMailNotFound:
                error_flag = True
                log.error(u"Default email template record for submission reminder is not found.")
                SubmissionReminderBatchStatus.save_for_error(contract.id, send_success, send_failure)
            except InvalidReminderEmailDays:
                error_flag = True
                log.error(u"The value of the reminder e-mail days is invalid for the contract(id={}).".format(contract.id))
                SubmissionReminderBatchStatus.save_for_error(contract.id, send_success, send_failure)
            except SendMailError:
                error_flag = True
                log.error(u"Error occurred while sending emails for the contract(id={}).".format(contract.id))
                SubmissionReminderBatchStatus.save_for_error(contract.id, send_success, send_failure)
            except Exception as ex:
                error_flag = True
                log.error(u"Unexpected error occurred: {}".format(ex))
                SubmissionReminderBatchStatus.save_for_error(contract.id, send_success, send_failure)

            # Success
            else:
                SubmissionReminderBatchStatus.save_for_finished(contract.id, send_success, send_failure)

        if error_flag:
            raise CommandError("Error occurred while handling send_submission_reminder_email command.")


def send_reminder_email(contract, user, target_courses, debug):
    from_address = microsite.get_value('email_from_address', settings.DEFAULT_FROM_EMAIL)
    to_addresses = [user.email]

    contract_mail = ContractReminderMail.get_or_default(contract, ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER)
    replace_dict = {'username': user.username}
    subject = replace_braces(contract_mail.mail_subject, replace_dict)
    message = replace_braces(contract_mail.compose_mail_body(target_courses), replace_dict)

    if debug:
        log.warning("This is a debug mode, so we don't send a reminder email.")
        log.debug(u"From Address={}".format(from_address))
        log.debug(u"To Addresses={}".format(to_addresses))
        log.debug(u"Subject={}".format(subject))
        log.debug(u"Message={}".format(message))
    else:
        send_mail(subject, message, from_address, to_addresses)

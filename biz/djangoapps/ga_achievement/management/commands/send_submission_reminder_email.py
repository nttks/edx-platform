"""
Management command to send reminder email for all biz students who have not submitted on target sections.
"""
import logging
import time
from optparse import make_option

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from xmodule.modulestore.django import modulestore

from biz.djangoapps.ga_achievement.achievement_store import ScoreStore
from biz.djangoapps.ga_achievement.management.commands.update_biz_score_status import TargetSection, GroupedTargetSections
from biz.djangoapps.ga_achievement.models import ScoreBatchStatus, SubmissionReminderBatchStatus
from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.ga_invitation.models import ContractRegister
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.decorators import handle_command_exception
from lms.djangoapps.instructor.enrollment import render_message_to_string
from microsite_configuration import microsite
from student.models import UserStanding, CourseEnrollment

log = logging.getLogger(__name__)


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
                raise CommandError("The specified contract does not exist or is not active.")
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

                # Calculate target min and max datetime
                target_day_min, target_day_max = datetime_utils.min_and_max_of_date(
                    start_datetime.date(), settings.INTERVAL_DAYS_TO_SEND_SUBMISSION_REMINDER_EMAIL)

                # Get target courses
                target_courses = []
                for contract_detail in contract.details.all().order_by('id'):
                    # Check if course exists in modulestore
                    course = modulestore().get_course(contract_detail.course_id)
                    if not course:
                        log.warning(
                            u"This course does not exist in modulestore. contract_id={}, course_id={}".format(
                                contract.id, unicode(contract_detail.course_id)))
                        continue
                    # TODO: As of now, exclude the self-paced courses. We'll fix it later. (#1816)
                    elif course.self_paced:
                        log.warning(
                            u"This course is self-paced. So, we exclude it from the target courses. contract_id={}, course_id={}".format(
                                contract.id, unicode(course.id)))
                        continue

                    # Extract sections whose due dates are approaching within the specified days
                    grouped_target_sections = GroupedTargetSections()
                    for chapter in course.get_children():
                        for section in chapter.get_children():
                            if section.due and target_day_min <= section.due <= target_day_max:
                                grouped_target_sections.append(TargetSection(section))
                                log.debug(u"column_name={}".format(TargetSection(section).column_name))
                    if grouped_target_sections.keys():
                        target_courses.append(grouped_target_sections)

                log.debug(u"Target courses for contract(id={}) are [{}]".format(
                    contract.id, ', '.join([unicode(grouped_target_sections.course_key) for grouped_target_sections in target_courses]))
                )
                if not target_courses:
                    log.warning(u"Contract(id={}) has no target courses for submission reminder today, so skip.".format(
                        contract.id))
                else:
                    # Check if update_biz_score_status process for all target courses has all finished today
                    score_batch_finished_today = all(
                        ScoreBatchStatus.finished_today(contract.id, grouped_target_sections.course_key)
                        for grouped_target_sections in target_courses
                    )
                    if not score_batch_finished_today:
                        raise ScoreBatchNotFinished()

                    # Get target users
                    for contract_register in ContractRegister.find_input_and_register_by_contract(contract.id):
                        start = time.clock()
                        user = contract_register.user
                        # Skip if user already resigned
                        if hasattr(user, 'standing') and user.standing \
                                and user.standing.account_status == UserStanding.ACCOUNT_DISABLED:
                            continue

                        target_courses_per_user = []
                        for grouped_target_sections in target_courses:
                            course_key = grouped_target_sections.course_key

                            # Exclude course in which user don't enroll at this time
                            course_enrollment = CourseEnrollment.get_enrollment(user, course_key)
                            if not course_enrollment or not course_enrollment.is_active:
                                continue

                            # Get user's score
                            score_store = ScoreStore(contract.id, unicode(course_key))
                            record = score_store.get_record_document_by_username(user.username)

                            # Choice 'Not Attempted' section from user's score
                            grouped_target_sections_per_user = GroupedTargetSections()
                            for target_section in grouped_target_sections.target_sections:
                                if record.get(target_section.column_name) == ScoreStore.VALUE__NOT_ATTEMPTED:
                                    grouped_target_sections_per_user.append(target_section)
                            if grouped_target_sections_per_user.keys():
                                target_courses_per_user.append(grouped_target_sections_per_user)

                        # Send email for user
                        if target_courses_per_user:
                            try:
                                send_reminder_email(user, target_courses_per_user, debug)
                                send_success += 1
                            except Exception as ex:
                                send_failure += 1
                                log.error(u"Error occurred while sending reminder email: {}".format(ex))

                        end = time.clock()
                        log.debug(u"Processed time to send submission reminder email ... {:.2f}s".format(end - start))

                    if send_failure > 0:
                        raise SendMailError()

            except ScoreBatchNotFinished:
                error_flag = True
                log.error(u"Score batches for the contract(id={}) have not finished yet today.".format(contract.id))
                SubmissionReminderBatchStatus.save_for_error(contract.id, send_success, send_failure)
            except SendMailError:
                error_flag = True
                log.error(u"Error occurred while sending emails for the contract(id={}).".format(contract.id))
                SubmissionReminderBatchStatus.save_for_error(contract.id, send_success, send_failure)
            except Exception as ex:
                error_flag = True
                log.error(u"Unexpected error occurred: {}".format(ex))
                SubmissionReminderBatchStatus.save_for_error(contract.id, send_success, send_failure)
            else:
                SubmissionReminderBatchStatus.save_for_finished(contract.id, send_success, send_failure)

        if error_flag:
            raise CommandError("Error occurred while handling send_submission_reminder_email command.")


def send_reminder_email(user, target_courses, debug):
    subject, message = render_message_to_string(
        'ga_achievement/emails/submission_reminder_email_subject.txt',
        'ga_achievement/emails/submission_reminder_email_message.txt',
        {
            'user': user,
            'target_courses': target_courses,
        }
    )

    if debug:
        log.warning("This is a debug mode, so we don't send a reminder email.")
        log.debug(u"Subject={}".format(subject))
        log.debug(u"Message={}".format(message))
    else:
        from_address = microsite.get_value(
            'email_from_address',
            settings.DEFAULT_FROM_EMAIL
        )
        send_mail(subject, message, from_address, [user.email])

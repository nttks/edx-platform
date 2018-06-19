# -*- coding: utf-8 -*-
"""
Management command to send reminder of closure email for all students at self-paced course whose individual end date is approaching.
"""
import logging
import time
from optparse import make_option

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from xmodule.modulestore.django import modulestore

from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.ga_invitation.models import ContractRegister
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.decorators import handle_command_exception, ExitWithWarning
from ga_bulk_email.models import (
    SelfPacedCourseClosureReminderBatchStatus, SelfPacedCourseClosureReminderMail,
)
from microsite_configuration import microsite
from student.models import UserStanding, CourseEnrollment

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from openedx.core.djangoapps.ga_optional.api import is_available
from openedx.core.djangoapps.ga_optional.models import SELF_PACED_COURSE_CLOSURE_REMINDER_EMAIL_KEY
from openedx.core.djangoapps.ga_self_paced.api import get_course_end_date
from openedx.core.lib.ga_course_utils import sort_by_start_date
from openedx.core.lib.ga_mail_utils import send_mail, replace_braces

log = logging.getLogger(__name__)


class SelfPacedCourseClosureReminderEmailNotFound(Exception):
    """
    This exception is raised in the case where self-paced course closure reminder email template (including default template) is not found
    """
    pass


class InvalidSelfPacedCourseClosureReminderEmailDays(Exception):
    """
    This exception is raised in the case where the value of the self-paced course closure reminder email days is invalid
    """
    pass


class SendMailError(Exception):
    """
    This exception is raised in the case where sending email failed accidentally
    """
    pass


class Command(BaseCommand):
    """
    Send reminder of closure email for self-paced course.
    """
    help = """
    Usage: python manage.py lms --settings=aws send_self_paced_course_closure_reminder_email [--debug] [--excludes=<exclude_ids>|<course_id>]
    """

    option_list = BaseCommand.option_list + (
        make_option('--debug',
                    default=False,
                    action='store_true',
                    help='Use debug log'),
        make_option('--excludes',
                    default=None,
                    action='store',
                    help='Specify course ids to exclude as comma-delimited (like course-v1:gacco+sp001+2018_04 or course-v1:gacco+sp001+2018_04,course-v1:gacco+sp002+2019_04))'),
    )

    @handle_command_exception(settings.GA_BULK_EMAIL_SEND_SELF_PACED_COURSE_CLOSURE_REMINDER_EMAIL_COMMAND_OUTPUT)
    def handle(self, *args, **options):
        start_datetime = datetime_utils.timezone_now()

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
                exclude_ids = exclude_ids.split(',')
                # Check course id format.
                [CourseKey.from_string(s) for s in exclude_ids]
            except InvalidKeyError:
                raise CommandError("The exclude_ids is not of the right format. It should be like 'org/course/run' or 'course-v1:org+course+run'.")
        log.debug(u"exclude_ids={}".format(exclude_ids))

        if len(args) > 1:
            raise CommandError("This command requires one or no arguments: |<course_id>|")

        course_id = args[0] if len(args) > 0 else None
        if course_id:
            if exclude_ids:
                raise CommandError("Cannot specify exclude_ids and course_id at the same time.")
            # Check args: course_id
            try:
                course_id = CourseKey.from_string(course_id)
            except InvalidKeyError:
                raise CommandError("The specified course_id is not of the right format. It should be like 'org/course/run' or 'course-v1:org+course+run'.")
            course = modulestore().get_course(course_id)
            if not course:
                raise ExitWithWarning("No such course(id={}) was found.".format(str(course_id)))
            if not course.self_paced:
                raise ExitWithWarning("The specified course(id={}) was not self-paced.".format(str(course_id)))
            self_paced_courses = [course]
        else:
            self_paced_courses = [c for c in modulestore().get_courses() if c.self_paced and str(c.id) not in exclude_ids]
            self_paced_courses = sort_by_start_date(self_paced_courses)
        log.debug(u"self_paced_course_ids[{}]=[{}]".format(len(self_paced_courses), ','.join([str(c.id) for c in self_paced_courses])))

        available_self_paced_courses = []
        for course in self_paced_courses:
            # Check if self-paced-course-closure-reminder-email option is available
            if not is_available(SELF_PACED_COURSE_CLOSURE_REMINDER_EMAIL_KEY, course.id):
                log.warning(u"Option for self-paced-course-closure-reminder-email is not available for the course(id={}), so skip.".format(course.id))
                continue
            # Check if global course is skip
            if course.id in set(CourseGlobalSetting.all_course_id()):
                log.warning(u"Course(id={}) is global course, so skip.".format(course.id))
                continue
            available_self_paced_courses.append(course)
        log.debug(u"available_courses_ids[{}]=[{}]".format(
            len(available_self_paced_courses), ','.join([str(c.id) for c in available_self_paced_courses])))

        error_flag = False
        for course in available_self_paced_courses:
            # Check if the course is SPOC or MOOC
            # Note: The courses related to the contract of gacco service are treated as MOOC.
            if Contract.exists_spoc_by_course_key(course.id):
                enrollments = _get_target_enrollments_spoc(course)
            else:
                enrollments = _get_target_enrollments(course)

            try:
                log.info(u"Command send_self_paced_course_closure_reminder_email for course(id={}) is now processing...".format(course.id))
                send_success = 0
                send_failure = 0

                SelfPacedCourseClosureReminderBatchStatus.save_for_started(course.id)

                course_mail = SelfPacedCourseClosureReminderMail.get_or_default(
                    course.id, SelfPacedCourseClosureReminderMail.MAIL_TYPE_SELF_PACED_COURSE_CLOSURE_REMINDER)
                if not course_mail:
                    raise SelfPacedCourseClosureReminderEmailNotFound()

                reminder_email_days = course_mail.reminder_email_days
                if reminder_email_days < SelfPacedCourseClosureReminderMail.REMINDER_EMAIL_DAYS_MIN_VALUE \
                        or SelfPacedCourseClosureReminderMail.REMINDER_EMAIL_DAYS_MAX_VALUE < reminder_email_days:
                    raise InvalidSelfPacedCourseClosureReminderEmailDays()
                target_day_min, target_day_max = datetime_utils.min_and_max_of_date(start_datetime.date(), reminder_email_days)

                for enrollment in enrollments:
                    start = time.clock()
                    course_end_date = get_course_end_date(enrollment)
                    if course_end_date is None:
                        log.warning(u"User(id={},name={}) could not get the course(id={}) end date and time.".format(
                            enrollment.user.id, enrollment.user.username, str(course.id)))
                        continue

                    log.debug(u"{} <= {} <= {} : {}".format(
                        target_day_min, datetime_utils.to_jst(course_end_date), target_day_max, target_day_min <= course_end_date <= target_day_max))
                    if target_day_min <= course_end_date <= target_day_max:
                        try:
                            _send_email(enrollment.user, course, course_end_date, course_mail, debug)
                            send_success += 1
                            end = time.clock()
                            log.debug(u"Processed time to self-paced-course-closure-reminder-email ... {:.2f}s".format(end - start))
                        except Exception as ex:
                            send_failure += 1
                            log.error(u"Error occurred while sending self-paced course closure reminder email: {}".format(ex))

                if send_failure > 0:
                    raise SendMailError()

            # Error (need recovery)
            except SelfPacedCourseClosureReminderEmailNotFound:
                error_flag = True
                log.error(u"Default email template record for self-paced course closure reminder email is not found.")
                SelfPacedCourseClosureReminderBatchStatus.save_for_error(course.id, send_success, send_failure)
            except InvalidSelfPacedCourseClosureReminderEmailDays:
                error_flag = True
                log.error(u"The value of the reminder email days is invalid for the course(id={}).".format(str(course.id)))
                SelfPacedCourseClosureReminderBatchStatus.save_for_error(course.id, send_success, send_failure)
            except SendMailError:
                error_flag = True
                log.error(u"Error occurred while sending emails for the course(id={}).".format(course.id))
                SelfPacedCourseClosureReminderBatchStatus.save_for_error(course.id, send_success, send_failure)
            except Exception as ex:
                error_flag = True
                log.error(u"Unexpected error occurred: {}".format(ex))
                SelfPacedCourseClosureReminderBatchStatus.save_for_error(course.id, send_success, send_failure)
            else:
                # Success
                SelfPacedCourseClosureReminderBatchStatus.save_for_finished(course.id, send_success, send_failure)

        if error_flag:
            raise CommandError("Error occurred while handling send_self_paced_course_closure_reminder_email command.")


def _get_target_enrollments_spoc(course):
    """
    Get enrollments of the user to send mail for the course of SPOC.

    :param course: course object
    :return: CourseEnrollment objects
    """
    enabled_spoc_contracts = Contract.find_enabled_spoc_by_course_key(course.id)

    log.debug(u"enabled_spoc_contracts[{}]=[id:names={}]".format(
        len(enabled_spoc_contracts), u",".join([u"{}{}{}".format(str(c.id), u":", c.contract_name) for c in enabled_spoc_contracts])))

    if len(enabled_spoc_contracts) == 1:
        contract = enabled_spoc_contracts.first()
    else:
        log.warning(u"Course(id={}) is related to multiple active contracts(id:names[{}]=[{}]), so skip.".format(
            str(course.id), len(enabled_spoc_contracts), u",".join([u"{}{}{}".format(str(c.id), u":", c.contract_name) for c in enabled_spoc_contracts])))
        return []

    if not contract.can_send_mail:
        log.warning(u"The contract(id={},name={}) has contract-auth but send_mail option is False, so skip.".format(contract.id, contract.contract_name))
        return []

    return _get_target_enrollments(course, contract)


def _get_target_enrollments(course, contract=None):
    """
    Get enrollments of the user to send mail.

    :param course: course object
    :param contract: Contract object
    :return: CourseEnrollment objects
    """
    # Exclude course in which user don't enroll at this time
    enrollments = CourseEnrollment.objects.select_related('user').filter(course_id=course.id, is_active=True)
    if not enrollments.exists():
        log.warning(u"No active enrollment of course(id={}).".format(str(course.id)))
        return []

    log.debug(u"Course(id={}) ActiveUsers[{}]=[id:names={}]".format(
        str(course.id), len(enrollments), u",".join([u"{}{}{}".format(str(e.user.id), u":", e.user.username) for e in enrollments])))

    target_enrollments = []
    for enrollment in enrollments:
        # invitation code registered check is spoc only.
        if contract and not ContractRegister.has_input_and_register_by_user_and_contract_ids(enrollment.user, [contract.id]):
            log.debug(u"The user(id={},name={}) is not registered in the invitation code of the contract(id={},name={}), so skip.".format(
                enrollment.user.id, enrollment.user.username, contract.id, contract.contract_name))
            continue

        user = enrollment.user
        # Skip if user already resigned
        if hasattr(user, 'standing') and user.standing and user.standing.account_status == UserStanding.ACCOUNT_DISABLED:
            log.debug(u"The user(id={},name={}) has already resigned, so skip.".format(user.id, user.username))
            continue

        # Skip if user already masked (#1970)
        if '@' not in user.email:
            log.warning(u"the user(id={},name={}) has been already masked, so skip.".format(user.id, user.username))
            continue

        target_enrollments.append(enrollment)
    return target_enrollments


def _send_email(user, course, course_end_date, mail, debug):
    from_address = microsite.get_value('email_from_address', settings.DEFAULT_FROM_EMAIL)
    to_addresses = [user.email]
    terminate_date_jp = datetime_utils.to_jst(course_end_date).strftime('%Y年%-m月%-d日')  # ex. 2018年1月1日
    terminate_date_en = datetime_utils.to_jst(course_end_date).strftime('%d/%m/%Y')  # ex. 01/01/2018

    replace_dict = SelfPacedCourseClosureReminderMail.replace_dict(
        user.profile.name, str(course.id), course.display_name, terminate_date_jp, terminate_date_en)

    subject = replace_braces(mail.mail_subject.encode('utf-8'), replace_dict)
    message = replace_braces(mail.mail_body.encode('utf-8'), replace_dict)

    if debug:
        log.warning("This is a debug mode, so we don't send a email.")
        log.debug(u"From Address={}".format(from_address))
        log.debug(u"To Addresses={}".format(to_addresses))
        log.debug(u"Subject={}".format(subject.decode('utf-8')))
        log.debug(u"Message={}".format(message.decode('utf-8')))
    else:
        send_mail(subject, message, from_address, to_addresses)

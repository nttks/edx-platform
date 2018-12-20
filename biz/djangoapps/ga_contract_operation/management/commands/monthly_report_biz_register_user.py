"""
Management command to generate a report
of register user count for biz students each contract.
"""
import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
from optparse import make_option
from pytz import utc

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from biz.djangoapps.ga_contract.models import Contract, CONTRACT_TYPE_PF, CONTRACT_TYPE_GACCO_SERVICE, CONTRACT_TYPE_OWNER_SERVICE
from biz.djangoapps.ga_invitation.models import ContractRegisterHistory, REGISTER_INVITATION_CODE
from biz.djangoapps.util.datetime_utils import timezone_today
from biz.djangoapps.util.decorators import handle_command_exception
from lms.djangoapps.instructor.enrollment import render_message_to_string
from openedx.core.djangoapps.ga_self_paced import api as self_paced_api
from student.models import UserStanding, CourseEnrollment
from xmodule.modulestore.django import modulestore

log = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """
    Generate a report of register user count for biz students each contract.

    Example:
      python manage.py lms --settings=aws monthly_report_biz_register_user [--debug] 2016 4
    """

    option_list = BaseCommand.option_list + (
        make_option('--debug',
                    default=False,
                    action='store_true',
                    help='Use debug log'),
    )

    def add_arguments(self, parser):
        parser.add_argument('args', nargs=argparse.REMAINDER)

    @handle_command_exception(settings.BIZ_MONTHLY_REPORT_COMMAND_OUTPUT)
    def handle(self, *args, **options):

        debug = options.get('debug')
        if debug:
            stream = logging.StreamHandler(self.stdout)
            log.addHandler(stream)
            log.setLevel(logging.DEBUG)

        # Validate
        year, month, target_date, last_target_date = _validate(args)
        log.debug("Start datetime of the target month (last_target_date)={}".format(last_target_date))
        log.debug("End datetime of the target month (target_date)={}".format(target_date))

        # Create report data
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        # Rendering message
        subject, message = _render_message(year, month, pfgs_contract_list, os_contract_list)

        # Send a mail
        if not debug:
            send_mail(subject, message, settings.BIZ_FROM_EMAIL, settings.BIZ_RECIPIENT_LIST)
        else:
            log.warning("This is a debug mode, so we don't send a monthly report mail.")
            log.debug(u"Subject={}".format(subject))
            log.debug(u"Message={}".format(message))


def _validate(args):
    # Validate settings
    if not settings.BIZ_FROM_EMAIL:
        raise CommandError('Invalid settings, BIZ_FROM_EMAIL is empty.')
    if not settings.BIZ_RECIPIENT_LIST:
        raise CommandError('Invalid settings, BIZ_RECIPIENT_LIST is empty.')

    # Validate args
    if len(args) == 2:
        return _target_date(int(args[0]), int(args[1]))
    elif len(args) == 0:
        today = timezone_today()
        return _target_date(today.year, today.month)
    else:
        raise CommandError('monthly_report_biz_register_user requires two arguments or no argument: |<year> <month>|')


def _target_date(year, month):
    # To use in 'ModelClass.objects.raw({SQL})'
    last_target_date = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.get_default_timezone())
    target_date = last_target_date + relativedelta(months=1)
    return (year, month, target_date.astimezone(utc), last_target_date.astimezone(utc))


def _render_message(year, month, pfgs_contract_list, os_contract_list):
    return render_message_to_string(
        'ga_contract_operation/emails/monthly_report_subject.txt',
        'ga_contract_operation/emails/monthly_report_message.txt',
        {
            'year': year,
            'month': month,
            'pfgs_contract_list': pfgs_contract_list,
            'os_contract_list': os_contract_list,
        }
    )


def _create_report_data(target_date, last_target_date):
    # PF and gacco service list
    pfgs_contract_list = []
    # Owner service list
    os_contract_list = []
    for contract in Contract.objects.select_related(
        'contractor_organization', 'owner_organization'
    ).filter(
        contract_type__in=[CONTRACT_TYPE_PF[0], CONTRACT_TYPE_GACCO_SERVICE[0], CONTRACT_TYPE_OWNER_SERVICE[0]],
        end_date__gt=last_target_date
    ):
        log.debug("Processing contract(id={})...".format(contract.id))

        # Note(#918, #847)
        #   Select following users from ContractRegisterHistory.
        #     1) users who registered between `last_target_date` and `target_date`
        #     2) users whose invitation code was 'Register' just before `last_target_date`
        #   Additionally, exclude following users.
        #     A) users who had already resigned before `last_target_date`
        contract_register_list = list(ContractRegisterHistory.objects.raw('''
            SELECT 0 AS id, user_id, contract_id FROM ga_invitation_contractregisterhistory
                WHERE id IN (
                    SELECT
                        MAX(id)
                    FROM
                        ga_invitation_contractregisterhistory
                    WHERE
                        status = '{status}' AND contract_id = {contract_id} AND
                        '{last_target_date}' <= modified AND modified < '{target_date}' AND
                        NOT EXISTS (
                            SELECT id FROM student_userstanding WHERE student_userstanding.user_id = ga_invitation_contractregisterhistory.user_id AND account_status = 'disabled' AND standing_last_changed_at < '{last_target_date}'
                        )
                    GROUP BY
                        user_id
                )
            UNION
            SELECT 0 AS id, user_id, contract_id FROM ga_invitation_contractregisterhistory
                WHERE status = '{status}' AND id IN (
                    SELECT
                        MAX(id)
                    FROM
                        ga_invitation_contractregisterhistory
                    WHERE
                        contract_id = {contract_id} AND
                        modified < '{last_target_date}' AND
                        NOT EXISTS (
                            SELECT id FROM student_userstanding WHERE student_userstanding.user_id = ga_invitation_contractregisterhistory.user_id AND account_status = 'disabled' AND standing_last_changed_at < '{last_target_date}'
                        )
                    GROUP BY
                        user_id
                )
        '''.format(
            contract_id=contract.id,
            target_date=target_date.strftime('%Y-%m-%d %H:%M:%S'),
            status=REGISTER_INVITATION_CODE,
            last_target_date=last_target_date.strftime('%Y-%m-%d %H:%M:%S'),
        )))

        courses = [modulestore().get_course(contract_detail.course_id) for contract_detail in contract.details.all()]
        includes_self_paced_course = any(c.self_paced for c in courses)
        # Note(#1635):
        #     There are some operational rules for every contract.
        #     - Every contract should not include both self-paced and instructor-paced courses.
        #     - Every contract should not include two or more self-paced courses.
        if len(courses) > 1 and includes_self_paced_course:
            log.warning(
                "A self-paced course should not be mixed with any other course in the same contract(id={}).".format(
                    contract.id))

        # Exclude users whose all self-paced courses had already expired before the target month
        if includes_self_paced_course:
            for contract_register in contract_register_list[:]:
                user = User.objects.get(pk=contract_register.user_id)
                for course in courses:
                    enrollment = CourseEnrollment.get_enrollment(user, course.id)
                    self_paced_end_date = self_paced_api.get_course_end_date(enrollment)
                    if not self_paced_end_date or last_target_date <= self_paced_end_date:
                        # This is a target user, so include it!
                        break
                else:
                    contract_register_list.remove(contract_register)
                    log.debug(
                        "Excluded a user(id={user_id}) because the user's all courses in the contract(id={contract_id}) "
                        "had already expired before the target month.".format(
                            user_id=user.id,
                            contract_id=contract.id,
                        ))
        contract.contract_register_list = contract_register_list

        if contract.contract_type == CONTRACT_TYPE_OWNER_SERVICE[0]:
            os_contract_list.append(contract)
        else:
            pfgs_contract_list.append(contract)

    # PF and gacco service list sort by contractor_organization_id for grouping
    pfgs_contract_list.sort(key=lambda contract: contract.contractor_organization_id)

    # Owner service list sort by owner_organization_id for grouping
    os_contract_list.sort(key=lambda contract: contract.owner_organization_id)

    return (pfgs_contract_list, os_contract_list)

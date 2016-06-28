"""
Management command to generate a report
of register user count for biz students each contract.
"""
import datetime
from dateutil.relativedelta import relativedelta
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from biz.djangoapps.ga_contract.models import Contract, CONTRACT_TYPE_PF, CONTRACT_TYPE_GACCO_SERVICE, CONTRACT_TYPE_OWNER_SERVICE
from biz.djangoapps.ga_invitation.models import ContractRegisterHistory, UNREGISTER_INVITATION_CODE
from biz.djangoapps.util.datetime_utils import timezone_today
from biz.djangoapps.util.decorators import handle_command_exception
from lms.djangoapps.instructor.enrollment import render_message_to_string

from student.models import UserStanding

log = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """
    Generate a report of register user count for biz students each contract.

    Example:
      python manage.py lms --settings=aws monthly_report_biz_register_user 2016 4
    """

    @handle_command_exception(settings.BIZ_MONTHLY_REPORT_COMMAND_OUTPUT)
    def handle(self, *args, **options):

        # Validate
        year, month, target_date, last_target_date = _validate(args)

        # Create report data
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        # Rendering message
        subject, message = _render_message(year, month, pfgs_contract_list, os_contract_list)

        # Send a mail
        send_mail(subject, message, settings.BIZ_FROM_EMAIL, settings.BIZ_RECIPIENT_LIST)


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
    last_target_date = datetime.date(year, month, 1)
    return (year, month, last_target_date + relativedelta(months=1), last_target_date)


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

    # userstanding disabled list
    user_disabled_list = [
        str(x.user_id)
        for x in UserStanding.objects.filter(
            account_status=UserStanding.ACCOUNT_DISABLED,
            standing_last_changed_at__lt=last_target_date
        )
    ]

    # PF and gacco service list
    pfgs_contract_list = []
    # Owner service list
    os_contract_list = []
    for contract in Contract.objects.select_related(
        'contractor_organization', 'owner_organization'
    ).filter(
        contract_type__in=[CONTRACT_TYPE_PF[0], CONTRACT_TYPE_GACCO_SERVICE[0], CONTRACT_TYPE_OWNER_SERVICE[0]],
        end_date__gte=last_target_date
    ):

        # Select input, register without userstanding, unregistered in last target month.
        contract.contract_register_list = list(ContractRegisterHistory.objects.raw('''
            SELECT id, user_id, contract_id, status, created, MAX(modified) AS modified FROM ga_invitation_contractregisterhistory
            WHERE contract_id = {} AND modified < '{}' AND user_id NOT IN ({})
            GROUP BY user_id
            HAVING NOT (status = '{}' AND modified < '{}')
        '''.format(
            contract.id,
            target_date.strftime('%Y-%m-%d'),
            ','.join(user_disabled_list),
            UNREGISTER_INVITATION_CODE,
            last_target_date.strftime('%Y-%m-%d'),
        )))

        if contract.contract_type == CONTRACT_TYPE_OWNER_SERVICE[0]:
            os_contract_list.append(contract)
        else:
            pfgs_contract_list.append(contract)

    # PF and gacco service list sort by contractor_organization_id for grouping
    pfgs_contract_list.sort(key=lambda contract: contract.contractor_organization_id)

    # Owner service list sort by owner_organization_id for grouping
    os_contract_list.sort(key=lambda contract: contract.owner_organization_id)

    return (pfgs_contract_list, os_contract_list)

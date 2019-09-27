# -*- coding: utf-8 -*-
"""
Management command to register students automatically.
"""
import json
import time
import logging
import hashlib
from optparse import make_option
from datetime import datetime
from django.core.management.base import BaseCommand
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.ga_contract.models import Contract, ContractOption
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_member.tasks import REFLECT_CONDITIONS_BATCH, REFLECT_CONDITIONS_RESERVATION
from biz.djangoapps.gx_save_register_condition.utils import (
    ReflectConditionExecutor, TASK_PROGRESS_META_KEY_REGISTER, TASK_PROGRESS_META_KEY_UNREGISTER,
    TASK_PROGRESS_META_KEY_MASK)
from biz.djangoapps.gx_save_register_condition.models import ReflectConditionTaskHistory
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress

log = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """
    Register students automatically.

    Example:
      python manage.py lms --settings=aws register_students_automatically [--debug]
    """

    option_list = BaseCommand.option_list + (
        make_option('--debug',
                    default=False,
                    action='store_true',
                    help='Use debug log'),
    )

    def _get_organization(self):
        for org in Organization.objects.exclude(org_code='gacco'):
            yield org

    def _get_contract(self, org):
        for contract in Contract.objects.filter(contractor_organization=org):
            yield contract

    def handle(self, *args, **options):
        debug = options.get('debug')
        if debug:
            stream = logging.StreamHandler(self.stdout)
            log.addHandler(stream)
            log.setLevel(logging.DEBUG)
        log.info(u"register_students_automatically command start {}".format('(dry run)' if debug else ''))

        now = datetime.now().strftime('%Y/%m/%d')
        for org in self._get_organization():
            log.debug('Target organization is {0}'.format(str(org.id)))
            member_total_count = Member.find_active_by_org(org=org).count()
            for contract in self._get_contract(org):
                # check contract and set action_name
                action_name = None
                if contract.can_auto_register_students:
                    action_name = REFLECT_CONDITIONS_BATCH
                elif contract.auto_register_reservation_date and contract.auto_register_reservation_date.strftime(
                        '%Y/%m/%d') == now:
                    action_name = REFLECT_CONDITIONS_RESERVATION

                if action_name:
                    log.info('execute target : organization={0}, contract={1}'.format(str(org.id), str(contract.id)))
                    # Create Executor instance
                    executor = ReflectConditionExecutor(org=org, contract=contract, send_mail_flg=True)

                    # Create task data
                    # Note: create task_id because for loop import
                    task = Task.create(action_name, hashlib.md5(str(org.org_code)).hexdigest(), '', org.created_by)
                    task_history = ReflectConditionTaskHistory.objects.create(
                        task_id=task.task_id, organization=org, contract=contract, requester=None)
                    task_progress = TaskProgress(action_name, member_total_count, time.time())

                    # Execute
                    executor.execute()

                    # Update ContractOption.auto_register_reservation_date
                    if action_name is REFLECT_CONDITIONS_RESERVATION:
                        option = ContractOption.objects.get(contract=contract)
                        option.auto_register_reservation_date = None
                        option.save()

                    # Update task_history
                    task_history.update_result(result=True, messages=','.join(executor.errors))

                    # Update Task
                    task_progress.attempted = task_progress.total
                    task_progress.succeeded = executor.count_register + executor.count_unregister
                    task_progress.failed = executor.count_error
                    task.task_output = json.dumps({
                        'action_name': task_progress.action_name,
                        'attempted': task_progress.attempted,
                        'succeeded': task_progress.succeeded,
                        'skipped': task_progress.skipped,
                        'failed': task_progress.failed,
                        'total': task_progress.total,
                        'duration_ms': int((time.time() - task_progress.start_time) * 1000),
                        TASK_PROGRESS_META_KEY_REGISTER: executor.count_register,
                        TASK_PROGRESS_META_KEY_UNREGISTER: executor.count_unregister,
                        TASK_PROGRESS_META_KEY_MASK: executor.count_masked,
                    })
                    task.task_state = 'SUCCESS'
                    task.save()
                else:
                    log.debug('Skip contract {}.'.format(str(contract.id)))

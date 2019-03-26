# -*- coding: utf-8 -*-
import time
import logging

from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_save_register_condition.utils import (
    ReflectConditionExecutor, TASK_PROGRESS_META_KEY_REGISTER, TASK_PROGRESS_META_KEY_UNREGISTER,
    TASK_PROGRESS_META_KEY_MASK
)
from biz.djangoapps.gx_save_register_condition.models import ReflectConditionTaskHistory

from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress

log = logging.getLogger(__name__)


def perform_delegate_reflect_conditions(entry_id, task_input, action_name):
    entry = Task.objects.get(pk=entry_id)
    task_id = entry.task_id
    task_history, org_id, contract_id, send_mail_flg = _validate_and_get_arguments(task_id, task_input)
    task_progress = TaskProgress(action_name, Member.find_active_by_org(org=org_id).count(), time.time())
    task_progress.update_task_state()

    # Execute
    executor = ReflectConditionExecutor(
        Organization.objects.get(id=org_id), Contract.objects.get(id=contract_id), send_mail_flg)
    executor.execute()

    # Set errors to task_history
    task_history.update_result(result=True, messages=','.join(executor.errors))

    # Set result to task_progress
    task_progress.attempted = task_progress.total
    task_progress.succeeded = executor.count_register + executor.count_unregister
    task_progress.failed = executor.count_error

    return task_progress.update_task_state({
        # Set extra meta field.
        TASK_PROGRESS_META_KEY_REGISTER: executor.count_register,
        TASK_PROGRESS_META_KEY_UNREGISTER: executor.count_unregister,
        TASK_PROGRESS_META_KEY_MASK: executor.count_masked,
    })


def _validate_and_get_arguments(task_id, task_input):
    """
    Get task history and task targets by task input.

    :param task_id:
    :param task_input:
    :return task_history, task_targets
    """
    if any(param not in task_input for param in ['organization_id', 'contract_id', 'history_id', 'send_mail_flg']):
        raise ValueError(
            "Task {task_id}: Missing required value {task_input}".format(task_id=task_id, task_input=task_input))

    try:
        history_id = task_input['history_id']
        task_history = ReflectConditionTaskHistory.objects.get(pk=history_id)
    except ReflectConditionTaskHistory.DoesNotExist:
        # The ReflectConditionTaskHistory object should be committed in the view function before the task
        # is submitted and reaches this point.
        log.warning(
            "Task {task_id}: Failed to get ReflectConditionTaskHistory with id {history_id}".format(
                task_id=task_id, history_id=history_id
            )
        )
        raise

    organization_id = task_input['organization_id']
    if int(task_history.organization.id) != organization_id:
        _msg = "Organization id conflict: submitted value {task_history_organization_id} does not match {organization_id}" \
            .format(task_history_organization_id=task_history.organization.id, organization_id=organization_id)
        log.warning("Task {task_id}: {msg}".format(task_id=task_id, msg=_msg))
        raise ValueError(_msg)

    contract_id = task_input['contract_id']
    if int(task_history.contract.id) != contract_id:
        _msg = "Contract id conflict: submitted value {task_history_contract_id} does not match {contract_id}" \
            .format(task_history_contract_id=task_history.contract.id, contract_id=contract_id)
        log.warning("Task {task_id}: {msg}".format(task_id=task_id, msg=_msg))
        raise ValueError(_msg)

    send_mail_flg = False
    param_send_mail_flg = task_input['send_mail_flg']
    if param_send_mail_flg is not None and int(param_send_mail_flg) == 1:
        send_mail_flg = True

    return task_history, organization_id, contract_id, send_mail_flg

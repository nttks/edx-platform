"""
Tasks for contract operation.
"""

from celery import task
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract_operation.personalinfo import perform_delegate_personalinfo_mask
from openedx.core.djangoapps.ga_task.task import BaseTask, run_main_task


PERSONALINFO_MASK = 'personalinfo_mask'
TASKS = {
    PERSONALINFO_MASK: _("Personal Information Mask"),
}


@task(base=BaseTask)
def personalinfo_mask(entry_id):
    action_name = PERSONALINFO_MASK
    visit_func = perform_delegate_personalinfo_mask
    return run_main_task(entry_id, visit_func, action_name)

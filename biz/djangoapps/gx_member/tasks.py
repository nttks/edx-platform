"""
Tasks for organization operation.
"""

from celery import task
from django.utils.translation import ugettext as _

from biz.djangoapps.gx_member.member_editer import perform_delegate_member_register, perform_delegate_member_register_one

from openedx.core.djangoapps.ga_task.task import BaseTask, run_main_task

MEMBER_REGISTER = 'member_register'
TASKS = {
    MEMBER_REGISTER: _("Member Register"),
}

@task(base=BaseTask)
def member_register(entry_id):
    action_name = MEMBER_REGISTER
    visit_func = perform_delegate_member_register
    return run_main_task(entry_id, visit_func, action_name)

@task(base=BaseTask)
def member_register_one(entry_id):
    action_name = MEMBER_REGISTER
    visit_func = perform_delegate_member_register_one
    return run_main_task(entry_id, visit_func, action_name)

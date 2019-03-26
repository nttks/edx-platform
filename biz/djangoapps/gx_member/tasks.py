"""
Tasks for organization operation.
"""

from celery import task
from django.utils.translation import ugettext as _

from biz.djangoapps.gx_member.member_editer import perform_delegate_member_register, perform_delegate_member_register_one
from biz.djangoapps.gx_save_register_condition.reflect_conditions import perform_delegate_reflect_conditions

from openedx.core.djangoapps.ga_task.task import BaseTask, run_main_task

MEMBER_REGISTER = 'member_register'
REFLECT_CONDITIONS_IMMEDIATE = 'reflect_conditions_immediate'
TASKS = {
    MEMBER_REGISTER: _("Member Register"),
    REFLECT_CONDITIONS_IMMEDIATE: _("Reflect Conditions Immediate"),
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

@task(base=BaseTask)
def reflect_conditions_immediate(entry_id):
    action_name = REFLECT_CONDITIONS_IMMEDIATE
    visit_func = perform_delegate_reflect_conditions
    return run_main_task(entry_id, visit_func, action_name)

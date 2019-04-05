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
# for batch reflect_conditions_(reservation, batch, member_register, student_member_register)
REFLECT_CONDITIONS_RESERVATION = 'reflect_conditions_reservation'
REFLECT_CONDITIONS_BATCH = 'reflect_conditions_batch'
REFLECT_CONDITIONS_MEMBER_REGISTER = 'reflect_conditions_member_register'
REFLECT_CONDITIONS_STUDENT_MEMBER_REGISTER = 'reflect_conditions_student_member_register'
TASKS = {
    MEMBER_REGISTER: _("Member Register"),
    REFLECT_CONDITIONS_IMMEDIATE: _("Reflect Conditions Immediate"),
    REFLECT_CONDITIONS_RESERVATION: _("Reflect Conditions Reservation"),
    REFLECT_CONDITIONS_BATCH: _("Reflect Conditions Batch"),
    REFLECT_CONDITIONS_MEMBER_REGISTER: _("Reflect Conditions Member Register"),
    REFLECT_CONDITIONS_STUDENT_MEMBER_REGISTER: _("Reflect Conditions Student Member Register"),
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

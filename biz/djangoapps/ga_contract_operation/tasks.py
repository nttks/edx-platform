"""
Tasks for contract operation.
"""

from celery import task
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract_operation.additionalinfo import perform_delegate_additionalinfo_update
from biz.djangoapps.ga_contract_operation.personalinfo import perform_delegate_personalinfo_mask
from biz.djangoapps.ga_contract_operation.student_register import perform_delegate_student_register
from biz.djangoapps.ga_contract_operation.student_unregister import perform_delegate_sutudent_unregister
from openedx.core.djangoapps.ga_task.task import BaseTask, run_main_task


PERSONALINFO_MASK = 'personalinfo_mask'
STUDENT_REGISTER = 'student_register'
STUDENT_UNREGISTER = 'student_unregister'
ADDITIONALINFO_UPDATE = 'additionalinfo_update'
TASKS = {
    PERSONALINFO_MASK: _("Personal Information Mask"),
    STUDENT_REGISTER: _("Student Register"),
    STUDENT_UNREGISTER: _("Student Unregister"),
    ADDITIONALINFO_UPDATE: _("Additional Item Update"),
}


@task(base=BaseTask)
def personalinfo_mask(entry_id):
    action_name = PERSONALINFO_MASK
    visit_func = perform_delegate_personalinfo_mask
    return run_main_task(entry_id, visit_func, action_name)


@task(base=BaseTask)
def student_register(entry_id):
    action_name = STUDENT_REGISTER
    visit_func = perform_delegate_student_register
    return run_main_task(entry_id, visit_func, action_name)


@task(base=BaseTask)
def student_unregister(entry_id):
    action_name = STUDENT_UNREGISTER
    visit_func = perform_delegate_sutudent_unregister
    return run_main_task(entry_id, visit_func, action_name)


@task(base=BaseTask)
def additional_info_update(entry_id):
    action_name = ADDITIONALINFO_UPDATE
    visit_func = perform_delegate_additionalinfo_update
    return run_main_task(entry_id, visit_func, action_name)

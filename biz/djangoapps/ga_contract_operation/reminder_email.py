# -*- coding: utf-8 -*-
import json
import logging
import time

from django.conf import settings
from django.core.mail import send_mail as django_send_mail, get_connection as get_mail_connection
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory, ReminderMailTaskHistory, ReminderMailTaskTarget
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress
from xmodule.modulestore.django import modulestore
from openedx.core.lib.ga_mail_utils import replace_braces
from opaque_keys.edx.locator import CourseLocator

log = logging.getLogger(__name__)


def _validate_and_get_arguments(task_id, task_input):
    if 'contract_id' not in task_input or 'history_id' not in task_input:
        raise ValueError("Task {task_id}: Missing required value {task_input}".format(task_id=task_id, task_input=task_input))

    try:
        history_id = task_input['history_id']
        task_history = ReminderMailTaskHistory.objects.select_related('contract__contractauth').get(pk=history_id)
    except ContractTaskHistory.DoesNotExist:
        # The ContactTaskHistory object should be committed in the view function before the task
        # is submitted and reaches this point.
        log.warning(
            "Task {task_id}: Failed to get ReminderMailTaskHistory with id {history_id}".format(
                task_id=task_id, history_id=history_id
            )
        )
        raise

    contract_id = task_input['contract_id']
    if task_history.contract.id != task_input['contract_id']:
        _msg = "Contract id conflict: submitted value {task_history_contract_id} does not match {contract_id}".format(
            task_history_contract_id=task_history.contract.id, contract_id=contract_id
        )
        log.warning("Task {task_id}: {msg}".format(task_id=task_id, msg=_msg))
        raise ValueError(_msg)

    contract = task_history.contract
    targets = ReminderMailTaskTarget.find_by_history_id(task_history.id)
    return (contract, targets)


def reminder_bulk_email_customize(entry_id, task_input, action_name):
    """
    Executes to register students. This function is called by run_main_task.
    """
    log.info('reminder search mail to send task start')
    entry = Task.objects.get(pk=entry_id)
    task_id = entry.task_id

    contract, targets = _validate_and_get_arguments(task_id, task_input)
    mail_connection = get_mail_connection(username=None, password=None)
    mail_connection.open()

    task_progress = TaskProgress(action_name, len(targets), time.time())
    task_progress.update_task_state()

    mail_subject, mail_body, course = _get_mail_data(entry.task_input)
    expire_datetime = course.deadline_start

    for target in targets:
        log.info('reminder search mail to send transaction start')
        task_progress.attempt()
        if len(target.student_email.split(',', 3)) != 4:
            task_progress.skip()
            log.info('reminder search mail to send transaction skip')
            target.complete('')
            continue
        email, username, error_message, full_name = target.student_email.split(',', 3)
        if error_message:
            task_progress.fail()
            target.complete(
                "{email}:{message}".format(email=email, message=error_message.encode('utf_8')) if error_message else '')
            continue
        try:
            replace_dict = {
                'username': username,
                'email_address': email,
                'fullname': full_name.encode('utf-8'),
                'course_name': course.display_name.encode('utf-8'),
                'expire_date': unicode(expire_datetime.strftime("%Y-%m-%d")) if expire_datetime else '',
            }
            replaced_mail_subject = replace_braces(mail_subject, replace_dict)
            replaced_mail_body = replace_braces(mail_body, replace_dict)
            django_send_mail(replaced_mail_subject, replaced_mail_body, settings.DEFAULT_FROM_EMAIL, [email])
            task_progress.success()
        except:
            task_progress.fail()
            error_message = _("Failed to send the e-mail.")

        target.complete(
            "{email}:{message}".format(email=email, message=error_message.encode('utf_8')) if error_message else '')
        log.info('reminder search mail to send complete')


    return task_progress.update_task_state()


def _get_mail_data(task_input):
    data = json.loads(task_input)
    mail_subject = data['mail_subject'].encode('utf_8')
    mail_body = data['mail_body'].encode('utf_8')
    course = modulestore().get_course(CourseLocator.from_string(data['course_id']))
    return mail_subject, mail_body, course

import logging
import time

from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import ugettext as _

from student.models import CourseEnrollment

from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory, StudentUnregisterTaskTarget
from biz.djangoapps.ga_invitation.models import ContractRegister, UNREGISTER_INVITATION_CODE
from biz.djangoapps.util.access_utils import has_staff_access
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress

log = logging.getLogger(__name__)


class _UnregisterStudentExecutor(object):
    """
    Helper class for executing unregister student.
    """

    def __init__(self, task_id, contract):
        self.task_id = task_id
        self.contract = contract
        self.course_keys = [detail.course_id for detail in contract.details.all()]

    def unregister_student(self, contract_register):
        # ContractRegister and ContractRegisterHistory for end-of-month
        contract_register.status = UNREGISTER_INVITATION_CODE
        contract_register.save()
        # CourseEnrollment only spoc
        if self.contract.is_spoc_available:
            for course_key in self.course_keys:
                if CourseEnrollment.is_enrolled(contract_register.user, course_key) and not has_staff_access(contract_register.user, course_key):
                    CourseEnrollment.unenroll(contract_register.user, course_key)


def _validate_and_get_arguments(task_id, task_input):
    if 'contract_id' not in task_input or 'history_id' not in task_input:
        raise ValueError("Task {task_id}: Missing required value {task_input}".format(task_id=task_id, task_input=task_input))

    try:
        history_id = task_input['history_id']
        task_history = ContractTaskHistory.objects.get(pk=history_id)
    except ContractTaskHistory.DoesNotExist:
        # The ContactTaskHistory object should be committed in the view function before the task
        # is submitted and reaches this point.
        log.warning(
            "Task {task_id}: Failed to get ContractTaskHistory with id {history_id}".format(
                task_id=task_id, history_id=history_id
            )
        )
        raise

    contract_id = task_input['contract_id']
    if task_history.contract.id != contract_id:
        _msg = "Contract id conflict: submitted value {task_history_contract_id} does not match {contract_id}".format(
            task_history_contract_id=task_history.contract.id, contract_id=contract_id
        )
        log.warning("Task {task_id}: {msg}".format(task_id=task_id, msg=_msg))
        raise ValueError(_msg)

    contract = task_history.contract
    targets = StudentUnregisterTaskTarget.find_by_history_id(task_history.id)

    return (contract, targets, task_history.requester)


def perform_delegate_sutudent_unregister(entry_id, task_input, action_name):
    """
    Executes to studnet unregister information. This function is called by run_main_task.
    """
    entry = Task.objects.get(pk=entry_id)
    task_id = entry.task_id
    contract, targets, task_history_requester = _validate_and_get_arguments(task_id, task_input)

    task_progress = TaskProgress(action_name, len(targets), time.time())
    task_progress.update_task_state()

    executor = _UnregisterStudentExecutor(task_id, contract)

    def _skip(message):
        task_progress.skip()
        return (message, None)

    def _fail(message):
        task_progress.fail()
        return (message, None)

    def _validate_and_get_contract_register(target):
        # split
        inputdata_columns = target.inputdata.split(',') if target.inputdata else []
        len_inputdata_columns = len(inputdata_columns)
        # blank line
        if len_inputdata_columns == 0:
            return _skip(None)
        # unmatch columns
        if len_inputdata_columns != 1:
            return _fail(_("Data must have exactly one column: username."))

        contract_register = None
        try:
            contract_register = ContractRegister.get_by_user_contract(
                User.objects.get(username=inputdata_columns[0]),
                contract,
            )
        except User.DoesNotExist:
            pass

        # contract_register not found
        if contract_register is None:
            return _fail(_("username {username} is not registered student.").format(username=inputdata_columns[0]))
        # validate yourself
        if contract_register.user_id == task_history_requester.id:
            return _fail(_("You can not change of yourself."))
        # already unregister
        if contract_register.status == UNREGISTER_INVITATION_CODE:
            return _skip(_("username {username} already unregistered student.").format(username=inputdata_columns[0]))

        return (None, contract_register)

    for line_number, target in enumerate(targets, start=1):
        task_progress.attempt()
        contract_register = None
        try:
            with transaction.atomic():
                message, contract_register = _validate_and_get_contract_register(target)

                if contract_register is not None:
                    # update table
                    executor.unregister_student(contract_register)
                    task_progress.success()

                target.complete(_("Line {line_number}:{message}").format(line_number=line_number, message=message) if message else "")
        except:
            # If an exception occur, logging it and to continue processing next target.
            log.exception("Task {task_id}: Failed to process of the students unregistered to User {user}".format(task_id=task_id, user=target.inputdata if target else ''))
            task_progress.fail()
            target.incomplete(_("Line {line_number}:{message}").format(
                line_number=line_number,
                message=_("Failed to unregistered student. Please operation again after a time delay."),
            ))
        else:
            log.info("Task {task_id}: Success to process of students unregistered to User {user_id}".format(task_id=task_id, user_id=contract_register.user_id if contract_register else ''))

    return task_progress.update_task_state()

import logging
import time
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import ugettext as _
from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory, ContractTaskTarget
from biz.djangoapps.ga_contract_operation.utils import PersonalinfoMaskExecutor
from biz.djangoapps.ga_invitation.models import ContractRegister
from biz.djangoapps.util import mask_utils
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress

log = logging.getLogger(__name__)


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
    if task_history.contract.id != task_input['contract_id']:
        _msg = "Contract id conflict: submitted value {task_history_contract_id} does not match {contract_id}".format(
            task_history_contract_id=task_history.contract.id, contract_id=contract_id
        )
        log.warning("Task {task_id}: {msg}".format(task_id=task_id, msg=_msg))
        raise ValueError(_msg)

    contract = task_history.contract
    targets = ContractTaskTarget.find_by_history_id(task_history.id)

    return (contract, targets, task_history.requester)


def perform_delegate_personalinfo_mask(entry_id, task_input, action_name):
    """
    Executes to mask personal information. This function is called by run_main_task.
    """
    entry = Task.objects.get(pk=entry_id)
    task_id = entry.task_id

    contract, targets, task_history_requester = _validate_and_get_arguments(task_id, task_input)

    task_progress = TaskProgress(action_name, len(targets), time.time())
    task_progress.update_task_state()

    executor = PersonalinfoMaskExecutor(contract)

    for line_number, target in enumerate(targets, start=1):
        task_progress.attempt()
        contract_register = target.register if target.register else None
        try:
            with transaction.atomic():
                # bulk operation case
                # use inputdata
                if not contract_register:
                    inputdata_columns = target.inputdata.split(',') if target.inputdata else []
                    len_inputdata_columns = len(inputdata_columns)

                    # blank line
                    if len_inputdata_columns == 0:
                        task_progress.skip()
                        continue

                    # unmatch columns
                    if len_inputdata_columns != 1:
                        message = _("Data must have exactly one column: username.")
                        target.incomplete(_("Line {line_number}:{message}").format(line_number=line_number, message=message))
                        task_progress.fail()
                        continue

                    try:
                        contract_register = ContractRegister.get_by_user_contract(
                            User.objects.get(username=inputdata_columns[0]),
                            contract,
                        )
                    except User.DoesNotExist:
                        pass

                    # contractregister not found
                    if contract_register is None:
                        message = _("username {username} is not registered student.").format(username=inputdata_columns[0])
                        target.incomplete(_("Line {line_number}:{message}").format(line_number=line_number, message=message))
                        task_progress.fail()
                        continue

                    # validate yourself
                    if contract_register.user_id == task_history_requester.id:
                        message = _("You can not change of yourself.")
                        target.incomplete(_("Line {line_number}:{message}").format(line_number=line_number, message=message))
                        task_progress.fail()
                        continue

                user = contract_register.user

                # already mask
                if ContractTaskTarget.is_completed_by_user_and_contract(user, contract):
                    message = _("username {username} already personal information masked.").format(username=user.username)
                    target.incomplete(_("Line {line_number}:{message}").format(line_number=line_number, message=message))
                    task_progress.skip()
                    continue

                # Mask of additional information will run for all users even if it does not mask an user
                # information. Therefore, it might be run more than once, but this is not a problem.
                executor.disable_additional_info(contract_register)
                # Try to mask user information if contract is SPOC.
                if contract.is_spoc_available:
                    error_setting = executor.check_enrollment(user)
                    if error_setting is not None and error_setting['code'] is executor.ERROR_CODE_ENROLLMENT_SPOC:
                        log.info("Task {task_id}: User {user_id} is enrolled in other SPOC course {course_ids}".format(
                            task_id=task_id, user_id=user.id,
                            course_ids=','.join([unicode(course_id) for course_id in error_setting['course_id']])))
                        task_progress.skip()
                        continue
                    elif error_setting is not None and error_setting['code'] is executor.ERROR_CODE_ENROLLMENT_MOOC:
                        log.info("Task {task_id}: User {user_id} is enrolled in MOOC course {course_ids}".format(
                            task_id=task_id, user_id=user.id,
                            course_ids=','.join([unicode(course_id) for course_id in error_setting['course_id']])
                        ))
                        task_progress.skip()
                        continue
                    else:
                        # No error
                        mask_utils.disable_user_info(user)
                target.complete()
        except:
            # If an exception occur, logging it and to continue processing next target.
            log.exception("Task {task_id}: Failed to process of the personal information mask to User {user_id}".format(
                task_id=task_id, user_id=contract_register.user.id if contract_register.user else ''))
            task_progress.fail()
            target.incomplete(_("Line {line_number}:{message}").format(
                line_number=line_number,
                message=_("Failed to personal information masked. Please operation again after a time delay."),
            ))

        else:
            log.info("Task {task_id}: Success to process of mask to User {user_id}".format(
                task_id=task_id, user_id=contract_register.user.id))
            task_progress.success()

    return task_progress.update_task_state()

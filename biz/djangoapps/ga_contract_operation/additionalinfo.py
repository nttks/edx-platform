import logging
import time

from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract.models import AdditionalInfo
from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory, AdditionalInfoUpdateTaskTarget
from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting, ContractRegister
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress

log = logging.getLogger(__name__)


def _validate_and_get_arguments(task_id, task_input):
    if 'contract_id' not in task_input or 'history_id' not in task_input or 'additional_info_ids' not in task_input:
        raise ValueError("Task {task_id}: Missing required value {task_input}".format(task_id=task_id, task_input=task_input))

    try:
        history_id = task_input['history_id']
        task_history = ContractTaskHistory.objects.select_related('contract__contractauth').get(pk=history_id)
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
    targets = AdditionalInfoUpdateTaskTarget.find_by_history_id(task_history.id)

    additional_info_list = AdditionalInfo.validate_and_find_by_ids(contract, task_input['additional_info_ids'])
    if additional_info_list is None:
        raise ValueError("Task {task_id}: Additional item is changed".format(task_id=task_id))

    return (contract, targets, additional_info_list)


def perform_delegate_additionalinfo_update(entry_id, task_input, action_name):
    """
    Executes to update additional info. This function is called by run_main_task.
    """
    entry = Task.objects.get(pk=entry_id)
    task_id = entry.task_id
    contract, targets, additional_info_list = _validate_and_get_arguments(task_id, task_input)

    task_progress = TaskProgress(action_name, len(targets), time.time())
    task_progress.update_task_state()

    def _fail(message):
        return (message, None, None)

    def _validate(inputline):
        inputline_columns = inputline.split(',') if inputline else []
        len_inputline_columns = len(inputline_columns)
        if not inputline:
            # skip
            return (None, None, None)

        if len_inputline_columns != 1 + len(additional_info_list):
            # e-mail + additional_info* 1 line
            return _fail(_("Number of [emails] and [new items] must be the same."))

        return _validate_email_and_additional_info(*inputline_columns)

    def _validate_email_and_additional_info(email, *additional_info_values):
        # validate user
        try:
            user = User.objects.get(email=email)

            if not ContractRegister.objects.filter(user=user, contract=contract).exists():
                return _fail(_("Could not find target user."))

        except User.DoesNotExist:
            return _fail(_("The user does not exist. ({email})").format(email=email))

        # validate additional info value
        value_max_length = AdditionalInfoSetting._meta.get_field('value').max_length
        for additional_info_value in additional_info_values:
            if len(additional_info_value) > value_max_length:
                return _fail(_("Please enter the name of item within {max_number} characters.").format(max_number=value_max_length))

        return (None, user, additional_info_values)

    for line_number, target in enumerate(targets, start=1):
        task_progress.attempt()
        try:
            with transaction.atomic():
                message, user, additional_info_values = _validate(target.inputline)

                if user is None:
                    if message is None:
                        task_progress.skip()
                    else:
                        task_progress.fail()
                else:
                    if additional_info_values:
                        # Additional info
                        for i, additional_info in enumerate(additional_info_list):
                            additional_info_setting, created = AdditionalInfoSetting.objects.get_or_create(
                                contract=contract,
                                display_name=additional_info.display_name,
                                user=user,
                                defaults={'value': additional_info_values[i]}
                            )
                            if not created:
                                additional_info_setting.value = additional_info_values[i]
                                additional_info_setting.save()

                    log.info("Task {task_id}: Success to process of register to User {user_id}".format(task_id=task_id, user_id=user.id))
                    task_progress.success()

                target.complete(_("Line {line_number}:{message}").format(line_number=line_number, message=message) if message else "")

        except:
            # If an exception occur, logging it and to continue processing next target.
            log.exception(u"Task {task_id}: Failed to register {input}".format(task_id=task_id, input=target.inputline))
            task_progress.fail()
            target.incomplete(_("Line {line_number}:{message}").format(
                line_number=line_number,
                message=_("Failed to register. Please operation again after a time delay."),
            ))

    return task_progress.update_task_state()

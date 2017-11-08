import logging
import time

from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract.models import ContractDetail
from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory, ContractTaskTarget
from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting, ContractRegister, UNREGISTER_INVITATION_CODE
from biz.djangoapps.util import mask_utils
from biz.djangoapps.util.access_utils import has_staff_access
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress
from student.models import CourseEnrollment

log = logging.getLogger(__name__)


class _PersonalinfoMaskExecutor(object):
    """
    Helper class for executing mask of personal information.
    """

    def __init__(self, task_id, contract):
        self.task_id = task_id
        self.contract = contract
        _all_spoc_contract_details = ContractDetail.find_all_spoc()
        # all of spoc course ids
        self.spoc_course_ids = set([cd.course_id for cd in _all_spoc_contract_details])
        # spoc course ids which excluding courses relate with unavailable contract.
        self.enabled_spoc_course_ids = set([cd.course_id for cd in _all_spoc_contract_details if cd.contract.is_enabled()])
        # spoc course ids of target contract
        self.target_spoc_course_ids = set([cd.course_id for cd in contract.details.all()])
        # course ids of global course
        self.global_course_ids = set(CourseGlobalSetting.all_course_id())

    def check_enrollment(self, user):
        enrollment_course_ids = set([ce.course_id for ce in CourseEnrollment.enrollments_for_user(user)])
        # exclude global course
        enrollment_course_ids = enrollment_course_ids - self.global_course_ids

        enrollment_other_spoc_course_ids = (enrollment_course_ids & self.enabled_spoc_course_ids) - self.target_spoc_course_ids
        if enrollment_other_spoc_course_ids:
            log.info("Task {task_id}: User {user_id} is enrolled in other SPOC course {course_ids}".format(
                task_id=self.task_id,
                user_id=user.id,
                course_ids=','.join([unicode(course_id) for course_id in enrollment_other_spoc_course_ids])
            ))
            return False

        enrollment_mooc_course_ids = enrollment_course_ids - self.spoc_course_ids
        if enrollment_mooc_course_ids:
            log.info("Task {task_id}: User {user_id} is enrolled in MOOC course {course_ids}".format(
                task_id=self.task_id,
                user_id=user.id,
                course_ids=','.join([unicode(course_id) for course_id in enrollment_mooc_course_ids])
            ))
            return False

        return True

    def disable_user_info(self, user):
        """
        Override masked value to user information.

        Note: We can `NEVER` restore the masked value.
        """
        # To force opt-out state since global course is to be registered on a daily batch.
        mask_utils.optout_receiving_global_course_emails(user, self.global_course_ids)
        mask_utils.disconnect_third_party_auth(user)
        mask_utils.mask_name(user)
        mask_utils.mask_email(user)
        mask_utils.mask_login_code(user)
        mask_utils.delete_certificates(user)

    def disable_additional_info(self, contract_register):
        """
        Override masked value to additional information.

        Note: We can `NEVER` restore the masked value.
        """
        for additional_setting in AdditionalInfoSetting.find_by_user_and_contract(contract_register.user, self.contract):
            additional_setting.value = mask_utils.hash(additional_setting.value)
            additional_setting.save()

        # ContractRegister and ContractRegisterHistory for end-of-month
        contract_register.status = UNREGISTER_INVITATION_CODE
        contract_register.save()
        # CourseEnrollment only spoc
        if self.contract.is_spoc_available:
            for course_key in self.target_spoc_course_ids:
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

    executor = _PersonalinfoMaskExecutor(task_id, contract)

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
                    if not executor.check_enrollment(user):
                        task_progress.skip()
                        continue
                    executor.disable_user_info(user)
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

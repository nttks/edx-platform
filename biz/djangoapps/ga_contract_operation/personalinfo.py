
import hashlib
import hmac
import logging
import time

from django.conf import settings
from django.db import transaction
from social.apps.django_app import utils as social_utils

from bulk_email.models import Optout
from certificates.models import GeneratedCertificate
from student.models import (
    CourseEnrollment, CourseEnrollmentAllowed, ManualEnrollmentAudit, PendingEmailChange,
)
from third_party_auth import pipeline

from biz.djangoapps.ga_contract.models import Contract, ContractDetail
from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory, ContractTaskTarget
from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress

log = logging.getLogger(__name__)


def _hash(value):
    """
    Returns hashed value.
    """
    return hmac.new(settings.SECRET_KEY.encode('utf-8'), value.encode('utf-8'), hashlib.sha256).hexdigest()


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
        self._optout_global_courses(user)
        self._disconnect_third_party_auth(user)
        self._mask_name(user)
        self._mask_email(user)

    def disable_additional_info(self, user):
        """
        Override masked value to additional information.

        Note: We can `NEVER` restore the masked value.
        """
        for additional_setting in AdditionalInfoSetting.find_by_user_and_contract(user, self.contract):
            additional_setting.value = _hash(additional_setting.value)
            additional_setting.save()

    def _optout_global_courses(self, user):
        for global_course_id in self.global_course_ids:
            optout, _ = Optout.objects.get_or_create(user=user, course_id=global_course_id)
            optout.force_disabled = True
            optout.save()

    def _mask_name(self, user):
        hashed_name = _hash(user.profile.name)
        for certificate in GeneratedCertificate.objects.filter(user_id=user.id):
            certificate.name = hashed_name
            certificate.save()
        user.profile.name = hashed_name
        user.profile.save()
        # first_name and last_name of User are limited 32 length. Therefore, update to blank.
        user.first_name = ''
        user.last_name = ''
        user.save()

    def _mask_email(self, user):
        hashed_email = _hash(user.email)
        for cea in CourseEnrollmentAllowed.objects.filter(email=user.email):
            cea.email = hashed_email
            cea.save()
        for mea in ManualEnrollmentAudit.objects.filter(enrolled_by_id=user.id):
            mea.enrolled_email = hashed_email
            mea.save()
        for pec in PendingEmailChange.objects.filter(user_id=user.id):
            pec.new_email = hashed_email
            pec.save()
        user.email = hashed_email
        user.save()
        # If the user has changed the email address, it has been stored in the meta.
        user.profile.meta = ''
        user.profile.save()

    def _disconnect_third_party_auth(self, user):
        for state in pipeline.get_provider_user_states(user):
            strategy = social_utils.load_strategy()
            backend = social_utils.load_backend(strategy, state.provider.backend_name, None)
            backend.disconnect(user=user, association_id=state.association_id)


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

    return (contract, targets)


def perform_delegate_personalinfo_mask(entry_id, task_input, action_name):
    """
    Executes to mask personal information. This function is called by run_main_task.
    """
    entry = Task.objects.get(pk=entry_id)
    task_id = entry.task_id

    contract, targets = _validate_and_get_arguments(task_id, task_input)

    task_progress = TaskProgress(action_name, len(targets), time.time())
    task_progress.update_task_state()

    executor = _PersonalinfoMaskExecutor(task_id, contract)
    for target in targets:
        task_progress.attempt()
        user = target.register.user
        try:
            with transaction.commit_on_success():
                if ContractTaskTarget.is_completed_by_user_and_contract(user, contract):
                    log.info(
                        "Task {task_id}: User {user_id} has already been processed of mask.".format(
                            task_id=task_id, user_id=user.id
                        )
                    )
                    task_progress.skip()
                    continue
                # Mask of additional information will run for all users even if it does not mask an user
                # information. Therefore, it might be run more than once, but this is not a problem.
                executor.disable_additional_info(user)
                # Try to mask user information if contract is SPOC.
                if contract.is_spoc_available:
                    if not executor.check_enrollment(user):
                        task_progress.skip()
                        continue
                    executor.disable_user_info(user)
                target.complete()
        except:
            # If an exception occur, logging it and to continue processing next target.
            log.exception("Task {task_id}: Failed to process of the personal information mask to User {user_id}".format(task_id=task_id, user_id=user.id))
            task_progress.fail()
        else:
            log.info("Task {task_id}: Success to process of mask to User {user_id}".format(task_id=task_id, user_id=user.id))
            task_progress.success()

    return task_progress.update_task_state()

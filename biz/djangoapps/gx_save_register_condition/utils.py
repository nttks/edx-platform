# -*- coding: utf-8 -*-
import json
import time
import logging
from django.db import transaction
from django.db.models import Q
from django.utils.translation import ugettext as _
from biz.djangoapps.ga_contract.models import Contract, ContractOption, AdditionalInfo
from biz.djangoapps.ga_contract_operation.utils import PersonalinfoMaskExecutor
from biz.djangoapps.ga_invitation.models import (
    ContractRegister, AdditionalInfoSetting, UNREGISTER_INVITATION_CODE, REGISTER_INVITATION_CODE)
from biz.djangoapps.ga_contract_operation.models import ContractMail
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_save_register_condition.models import (
    ParentCondition, ChildCondition, ReflectConditionTaskHistory)
from biz.djangoapps.gx_reservation_mail.models import ReservationMail
from biz.djangoapps.util import mask_utils
from enrollment.api import _default_course_mode
from openedx.core.lib.ga_mail_utils import replace_braces
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress
from student.models import CourseEnrollment

log = logging.getLogger(__name__)

IMMEDIATE_REFLECT_MAX_SIZE = 10000
TASK_PROGRESS_META_KEY_REGISTER = 'student_register'
TASK_PROGRESS_META_KEY_UNREGISTER = 'student_unregister'
TASK_PROGRESS_META_KEY_MASK = 'personalinfo_mask'


def _get_member_query_by_child_conditions(org, contract, child_conditions):
    """
    Create query of Member by ChildCondition.
    :param org: biz.ga_organization.models.Organization
    :param contract: biz.ga_contract.models.Contract
    :param child_conditions: [ChildCondition, ...]
    :return: Q
    """
    if len(child_conditions) is 0:
        return None

    replace_string = u'NULL'

    additional_info_name_list = AdditionalInfo.find_by_contract_id(
        contract_id=contract.id).values_list("display_name", flat=True)

    query = Q()
    query.add(Q(('org', org)), Q.AND)
    query.add(Q(('is_active', True)), Q.AND)
    query.add(Q(('is_delete', False)), Q.AND)

    for child_condition in child_conditions:

        query_string = child_condition.comparison_string
        key = child_condition.comparison_type
        is_not = False

        replaced_string = ''
        if child_condition.comparison_target == ChildCondition.COMPARISON_TARGET_GROUP_NAME:
            replaced_string = None
            if key == ChildCondition.COMPARISON_TYPE_IN_NO:
                replaced_string = 'NULL'
            elif key == ChildCondition.COMPARISON_TYPE_NOT_IN_NO:
                replaced_string = 'NULL'

        query_type = None
        if key == ChildCondition.COMPARISON_TYPE_EQUAL_NO:
            # 'NULL' replace blank or None
            query_string = replaced_string if query_string == replace_string else query_string
            query_type = ChildCondition.COMPARISON_TYPE_OPERATOR[key]

        elif key == ChildCondition.COMPARISON_TYPE_NOT_EQUAL_NO:
            # 'NULL' replace blank or None
            query_string = replaced_string if query_string == replace_string else query_string
            is_not = True
            query_type = ChildCondition.COMPARISON_TYPE_OPERATOR[ChildCondition.COMPARISON_TYPE_EQUAL_NO]

        elif key == ChildCondition.COMPARISON_TYPE_NOT_CONTAINS_NO:
            is_not = True
            query_type = ChildCondition.COMPARISON_TYPE_OPERATOR[ChildCondition.COMPARISON_TYPE_CONTAINS_NO]

        elif key == ChildCondition.COMPARISON_TYPE_IN_NO:
            query_string = query_string.split(",")
            # 'NULL' replace blank or None
            query_string = [
                replaced_string if tmp_string == replace_string else tmp_string for tmp_string in query_string]
            query_type = ChildCondition.COMPARISON_TYPE_OPERATOR[key]

        elif key == ChildCondition.COMPARISON_TYPE_NOT_IN_NO:
            is_not = True
            query_string = query_string.split(",")
            # 'NULL' replace blank or None
            query_string = [
                replaced_string if tmp_string == replace_string else tmp_string for tmp_string in query_string]
            query_type = ChildCondition.COMPARISON_TYPE_OPERATOR[ChildCondition.COMPARISON_TYPE_IN_NO]

        elif key in ChildCondition.COMPARISON_TYPE_OPERATOR:
            query_type = ChildCondition.COMPARISON_TYPE_OPERATOR[key]

        query_key = None
        if child_condition.comparison_target == ChildCondition.COMPARISON_TARGET_USERNAME:
            query_key = 'user__username'
        elif child_condition.comparison_target == ChildCondition.COMPARISON_TARGET_EMAIL:
            query_key = 'user__email'
        elif child_condition.comparison_target == ChildCondition.COMPARISON_TARGET_LOGIN_CODE:
            query_key = 'user__bizuser__login_code'
        elif child_condition.comparison_target == ChildCondition.COMPARISON_TARGET_GROUP_NAME:
            query_key = 'group__group_name'
        elif child_condition.comparison_target in ChildCondition.COMPARISON_TARGET_ORG_LIST + \
                ChildCondition.COMPARISON_TARGET_ITEM_LIST + [ChildCondition.COMPARISON_TARGET_CODE]:
            query_key = child_condition.comparison_target
        elif child_condition.comparison_target in additional_info_name_list:
            # When additional info setting, set query_key, query_type.
            additional_info_query = Q()
            additional_info_query.add(Q(('contract', contract)), Q.AND)
            additional_info_query.add(Q(('display_name', child_condition.comparison_target)), Q.AND)
            additional_info_query.add(Q(('value__' + query_type, query_string)), Q.AND)
            query_string = [info['user__id'] for info in AdditionalInfoSetting.objects.filter(
                additional_info_query).values('user__id')]
            query_key = 'user__id'
            query_type = ChildCondition.COMPARISON_TYPE_OPERATOR[ChildCondition.COMPARISON_TYPE_IN_NO]

        if None in [query_type, query_key]:
            continue

        # Add condition in Q objects
        if is_not:
            query.add(~Q((query_key + '__' + query_type, query_string)), Q.AND)
        else:
            query.add(Q((query_key + '__' + query_type, query_string)), Q.AND)

    return query


def get_members_by_child_conditions(org, contract, child_conditions):
    """
    Search member by ChildCondition.
    :param org: biz.ga_organization.models.Organization
    :param contract: biz.ga_contract.models.Contract
    :param child_conditions: [ChildCondition, ...]
    :return: [Member, ...]
    """
    if child_conditions is None or len(child_conditions) is 0:
        return []

    return Member.objects.filter(
        _get_member_query_by_child_conditions(
            org, contract, child_conditions)).select_related('user', 'user__profile', 'user__bizuser').order_by('code')


def get_members_by_all_parents_conditions(org, contract):
    """
    Search member by ParentCondition and ChildCondition.
    :param org: biz.ga_organization.models.Organization
    :param contract: biz.ga_contract.models.Contract
    :return: [Member, ...]
    """
    all_conditions_query = None
    for parent_condition in ParentCondition.objects.filter(contract=contract):
        query = _get_member_query_by_child_conditions(
            org, contract, ChildCondition.objects.filter(parent_condition=parent_condition))

        if query is None:
            continue

        all_conditions_query = query if all_conditions_query is None else all_conditions_query | query

    return Member.objects.filter(all_conditions_query).select_related(
        'user', 'user__profile', 'user__bizuser').order_by('code') if all_conditions_query is not None else []


class ReflectConditionExecutor(object):
    """
    Reflect Condition Helper class.
    """
    def __init__(self, org, contract, send_mail_flg=False):
        """
        :param org: biz.ga_organization.models.Organization
        :param contract: biz.ga_contract.models.Contract
        """
        self.errors = []
        self.count_unregister = 0
        self.count_register = 0
        self.count_masked = 0
        self.count_error = 0
        self.register_user_ids = []
        self.unregister_user_ids = []
        self.masked_user_ids = []
        self.org = org
        self.contract = contract
        self.send_mail_flg = send_mail_flg
        self.details = [{
            'key': detail.course_id,
            'mode': _default_course_mode(unicode(detail.course_id))
        } for detail in self.contract.details.all()]
        self.option = ContractOption.objects.filter(contract=contract)
        if self.contract.has_auth:
            self.mail = ContractMail.get_register_existing_user_logincode(self.contract)
        else:
            self.mail = ContractMail.get_register_existing_user(self.contract)

    def execute(self):
        log.info('ReflectConditionExecutor.execute Organization:{org}, Contract:{contract}'.format(
            org=self.org.org_code, contract=self.contract.invitation_code))

        # Search
        searched_members = get_members_by_all_parents_conditions(self.org, self.contract)

        # Unregister unmatched conditions
        searched_members_user_ids = searched_members.values_list('id', flat=True) if searched_members else []
        unregister_user_ids = Member.find_active_by_org(org=self.org).exclude(
            id__in=searched_members_user_ids).values_list('user__id', flat=True)
        for contract_register in ContractRegister.objects.filter(
                contract=self.contract, user__id__in=unregister_user_ids).exclude(
                status=UNREGISTER_INVITATION_CODE).select_related('user'):
            self._unregister(contract_register=contract_register)

        # Unregister delete targets of member
        delete_target_user_ids = Member.find_delete_by_org(org=self.org).values_list('user__id', flat=True)
        for contract_register in ContractRegister.objects.filter(
                contract=self.contract, user__id__in=delete_target_user_ids).exclude(
                status=UNREGISTER_INVITATION_CODE).select_related('user'):
            self._unregister(contract_register=contract_register, not_count=True)

        # Register
        for member in searched_members:
            self._register(user=member.user)

        # Mask
        if self.org.can_auto_mask and self.contract.is_spoc_available:
            for member in Member.find_delete_by_org(org=self.org):
                self._mask(member.user)

        # result log output
        log.info('Register user id:{register}'.format(register=",".join(map(str, self.register_user_ids))))
        log.info('Unregister user id:{unregister}'.format(unregister=",".join(map(str, self.unregister_user_ids))))
        log.info('Masked user id:{masked}'.format(masked=",".join(map(str, self.masked_user_ids))))

    def _unregister(self, contract_register, not_count=False):
        with transaction.atomic():
            try:
                count_flg = False
                if contract_register.status is not UNREGISTER_INVITATION_CODE:
                    contract_register.status = UNREGISTER_INVITATION_CODE
                    contract_register.save()
                    count_flg = True

                if self.contract.is_spoc_available:
                    for detail in self.details:
                        if CourseEnrollment.is_enrolled(contract_register.user, detail['key']):
                            CourseEnrollment.unenroll(contract_register.user, detail['key'])

                if count_flg:
                    self.unregister_user_ids.append(contract_register.user.id)
                    log.debug('Unregister: {username}'.format(username=contract_register.user.email))
                    if not not_count:
                        self.count_unregister += 1

            except Exception as e:
                log.error(e)
                self.count_error += 1
                self.errors.append(
                    _("Failed to unregister of {username}.").format(username=contract_register.user.username))

    def _register(self, user):
        with transaction.atomic():
            try:
                count_flg = False

                if not ContractRegister.objects.filter(
                        contract=self.contract, user=user, status=REGISTER_INVITATION_CODE).exists():
                    count_flg = True
                    contract_register, __ = ContractRegister.objects.get_or_create(contract=self.contract, user=user)
                    if contract_register.status is not REGISTER_INVITATION_CODE:
                        contract_register.status = REGISTER_INVITATION_CODE
                        contract_register.save()

                for detail in self.details:
                    enrollment = CourseEnrollment.get_or_create_enrollment(user, detail['key'])
                    enrollment.update_enrollment(is_active=True, mode=detail['mode'])

                if self.contract.can_send_mail and self.send_mail_flg:
                    replace_dict = ContractMail.register_replace_dict(user, self.contract)
                    ReservationMail.objects.create(
                        user=user,
                        org=self.org,
                        mail_subject=replace_braces(self.mail.mail_subject, replace_dict),
                        mail_body=replace_braces(self.mail.mail_body, replace_dict)
                    )
                if count_flg:
                    self.count_register += 1
                    self.register_user_ids.append(user.id)
                    log.debug('Register: {username}'.format(username=user.username))

            except Exception as e:
                log.error(e)
                self.count_error += 1
                self.errors.append(_("Failed to register of {username}.").format(username=user.username))

    def _mask(self, user):
        with transaction.atomic():
            if PersonalinfoMaskExecutor(self.contract).check_enrollment(user) is None:
                mask_utils.disable_user_info(user)
                Member.find_backup_by_user(org=self.org, user=user).delete()
                Member.find_delete_by_user(org=self.org, user=user).delete()
                self.count_masked += 1
                self.masked_user_ids.append(user.id)


def reflect_condition_execute_call_by_another_task(task_id, org, user, action_name):
    """
    Called from other task than 'reflect_condition'.
    :param task_id: str
    :param org: biz.ga_organization.models.Organization
    :param user: django.contrib.auth.models.User
    :param action_name: str
    :return:
    """
    # Note: Import here to prevent circular reference.
    from biz.djangoapps.gx_member.tasks import (
        REFLECT_CONDITIONS_MEMBER_REGISTER, REFLECT_CONDITIONS_STUDENT_MEMBER_REGISTER)
    # Do not call from other than specific tasks
    if action_name not in [REFLECT_CONDITIONS_MEMBER_REGISTER, REFLECT_CONDITIONS_STUDENT_MEMBER_REGISTER]:
        raise ValueError

    member_total_count = Member.find_active_by_org(org=org).count()
    log.info('can_immediate_reflection is True.')
    for contract in Contract.objects.filter(contractor_organization=org):
        if contract.can_auto_register_students and len(
                get_members_by_all_parents_conditions(org, contract)) <= IMMEDIATE_REFLECT_MAX_SIZE:
            log.info('Target contract is {0}'.format(contract.id))
            # Create Executor instance
            executor = ReflectConditionExecutor(org=org, contract=contract)
            # Create task data
            task = Task.create(action_name, task_id, '', org.created_by)
            task_history = ReflectConditionTaskHistory.objects.create(
                task_id=task.task_id, organization=org, contract=contract, requester=user)
            task_progress = TaskProgress(action_name, member_total_count, time.time())

            # Execute
            executor.execute()

            # Update task_history
            task_history.update_result(result=True, messages=','.join(executor.errors))

            # Update Task
            task_progress.attempted = task_progress.total
            task_progress.succeeded = executor.count_register + executor.count_unregister
            task_progress.failed = executor.count_error
            task.task_output = json.dumps({
                'action_name': task_progress.action_name,
                'attempted': task_progress.attempted,
                'succeeded': task_progress.succeeded,
                'skipped': task_progress.skipped,
                'failed': task_progress.failed,
                'total': task_progress.total,
                'duration_ms': int((time.time() - task_progress.start_time) * 1000),
                TASK_PROGRESS_META_KEY_REGISTER: executor.count_register,
                TASK_PROGRESS_META_KEY_UNREGISTER: executor.count_unregister,
                TASK_PROGRESS_META_KEY_MASK: executor.count_masked,
            })
            task.task_state = 'SUCCESS'
            task.save()
        else:
            log.info('Skip contract {}.'.format(contract.id))

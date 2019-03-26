# -*- coding: utf-8 -*-
"""
Test for reflect conditions feature
"""
import ddt
import json
from celery.states import SUCCESS # pylint: disable=no-name-in-module, import-error
from mock import patch
from django.core.exceptions import ObjectDoesNotExist
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.ga_organization.tests.factories import OrganizationOptionFactory
from biz.djangoapps.gx_member.tasks import reflect_conditions_immediate
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_save_register_condition.tests.factories import (
    ParentConditionFactory, ChildConditionFactory, ReflectConditionTaskHistoryFactory)
from biz.djangoapps.gx_save_register_condition.models import ChildCondition
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin
from student.tests.factories import UserFactory


@ddt.ddt
class ReflectConditionsTaskTest(BizContractTestBase, TaskTestMixin):

    def setUp(self):
        """
        Set up for test
        """
        super(ReflectConditionsTaskTest, self).setUp()
        self.setup_user()
        self._create_contract_mail_default()
        patcher = patch('biz.djangoapps.gx_save_register_condition.reflect_conditions.log')
        self.mock_log = patcher.start()
        self.addCleanup(patcher.stop)

    def _create_member(
            self, org, group, user, code, is_active=True, is_delete=False, **kwargs):
        return MemberFactory.create(
            org=org, group=group, user=user, code=code,
            created_by=user, creator_org=org,
            updated_by=user, updated_org=org,
            is_active=is_active,
            is_delete=is_delete,
            **kwargs
        )

    def _test_run_with_task(self, task_class, action_name, expected_attempted=0, expected_num_succeeded=0,
                            expected_num_failed=0, expected_register=0, expected_unregister=0, expected_mask=0,
                            expected_total=0, task_entry=None):
        """
        Run a task and check the number of processed.
        Note: Orverride TaskTestMixin._test_run_with_task(), Because this task use extra meta.
        """
        status = self._run_task_with_mock_celery(task_class, task_entry.id, task_entry.task_id)
        # check return value
        self.assertEquals(status.get('attempted'), expected_attempted)
        self.assertEquals(status.get('succeeded'), expected_num_succeeded)
        self.assertEquals(status.get('failed'), expected_num_failed)
        self.assertEqual(status.get('student_register'), expected_register)
        self.assertEqual(status.get('student_unregister'), expected_unregister)
        self.assertEqual(status.get('personalinfo_mask'), expected_mask)
        self.assertEquals(status.get('total'), expected_total)
        self.assertEquals(status.get('action_name'), action_name)
        self.assertGreater(status.get('duration_ms'), 0)
        # compare with entry in table:
        entry = Task.objects.get(id=task_entry.id)
        self.assertEquals(json.loads(entry.task_output), status)
        self.assertEquals(entry.task_state, SUCCESS)

    def _create_input_entry(self, organization=None, contract=None, send_mail_flg=None, history=None):
        """ Create task """
        task_input = {}
        if organization is not None:
            task_input['organization_id'] = organization.id
        if contract is not None:
            task_input['contract_id'] = contract.id
        if send_mail_flg is not None:
            task_input['send_mail_flg'] = send_mail_flg
        if history is not None:
            task_input['history_id'] = history.id
        return TaskTestMixin._create_input_entry(self, task_input=task_input)

    def test_validate_and_get_arguments_when_not_found_organization_id_in_task_input(self):
        history = ReflectConditionTaskHistoryFactory.create(
            organization=self.contract_org, contract=self.contract, requester=self.user)
        entry = self._create_input_entry(
                organization=None, contract=self.contract, send_mail_flg=1, history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(reflect_conditions_immediate, entry.id, entry.task_id)

        self.assertEqual("Task {task_id}: Missing required value {task_input}".format(
            task_id=entry.task_id, task_input=json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_validate_and_get_arguments_when_not_found_contract_id_in_task_input(self):
        history = ReflectConditionTaskHistoryFactory.create(
            organization=self.contract_org, contract=self.contract, requester=self.user)
        entry = self._create_input_entry(
                organization=self.contract_org, contract=None, send_mail_flg=1, history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(reflect_conditions_immediate, entry.id, entry.task_id)

        self.assertEqual("Task {task_id}: Missing required value {task_input}".format(
            task_id=entry.task_id, task_input=json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_validate_and_get_arguments_when_not_found_send_mail_flg_in_task_input(self):
        history = ReflectConditionTaskHistoryFactory.create(
            organization=self.contract_org, contract=self.contract, requester=self.user)
        entry = self._create_input_entry(
                organization=self.contract_org, contract=self.contract, send_mail_flg=None, history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(reflect_conditions_immediate, entry.id, entry.task_id)

        self.assertEqual("Task {task_id}: Missing required value {task_input}".format(
            task_id=entry.task_id, task_input=json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_validate_and_get_arguments_when_not_found_history_id_in_task_input(self):
        entry = self._create_input_entry(
                organization=self.contract_org, contract=self.contract, send_mail_flg=1, history=None)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(reflect_conditions_immediate, entry.id, entry.task_id)

        self.assertEqual("Task {task_id}: Missing required value {task_input}".format(
            task_id=entry.task_id, task_input=json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_validate_and_get_arguments_when_not_found_history(self):
        history = ReflectConditionTaskHistoryFactory.create(
            organization=self.contract_org, contract=self.contract, requester=self.user)
        entry = self._create_input_entry(
                organization=self.contract_org, contract=self.contract, send_mail_flg=1, history=history)
        history.delete()

        with self.assertRaises(ObjectDoesNotExist):
            self._run_task_with_mock_celery(reflect_conditions_immediate, entry.id, entry.task_id)

        self._assert_task_failure(entry.id)

    def test_validate_and_get_arguments_when_not_match_org_id(self):
        history = ReflectConditionTaskHistoryFactory.create(
            organization=self.contract_org, contract=self.contract, requester=self.user)
        entry = self._create_input_entry(
                organization=self.contract_org_other, contract=self.contract, send_mail_flg=1, history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(reflect_conditions_immediate, entry.id, entry.task_id)

        msg = "Organization id conflict: submitted value {task_history_organization_id} " \
               "does not match {organization_id}".format(
            task_history_organization_id=history.organization.id, organization_id=self.contract_org_other.id)
        self.assertEqual(msg, cm.exception.message)
        self.mock_log.warning.assert_any_call("Task {task_id}: {msg}".format(task_id=entry.task_id, msg=msg))
        self._assert_task_failure(entry.id)

    def test_validate_and_get_arguments_when_not_match_contract_id(self):
        history = ReflectConditionTaskHistoryFactory.create(
            organization=self.contract_org, contract=self.contract, requester=self.user)
        entry = self._create_input_entry(
                organization=self.contract_org, contract=self.contract_mooc, send_mail_flg=1, history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(reflect_conditions_immediate, entry.id, entry.task_id)

        msg = "Contract id conflict: submitted value {task_history_contract_id} does not match {contract_id}".format(
            task_history_contract_id=history.contract.id, contract_id=self.contract_mooc.id)
        self.assertEqual(msg, cm.exception.message)
        self.mock_log.warning.assert_any_call("Task {task_id}: {msg}".format(task_id=entry.task_id, msg=msg))
        self._assert_task_failure(entry.id)

    def test_perform_delegate_reflect_conditions(self):
        # Create org option
        OrganizationOptionFactory.create(org=self.contract_org, auto_mask_flg=True, modified_by=self.user)
        # Create data
        parent1 = ParentConditionFactory.create(
            contract=self.contract, parent_condition_name='parent_1', setting_type=1,
            created_by=self.user, modified_by=self.user
        )
        ChildConditionFactory.create(
            contract=self.contract,
            parent_condition=parent1,
            parent_condition_name=parent1.parent_condition_name,
            comparison_target=ChildCondition.COMPARISON_TARGET_CODE,
            comparison_type=ChildCondition.COMPARISON_TYPE_STARTSWITH_NO,
            comparison_string='register'
        )
        expected_register_members = [self._create_member(
            org=self.contract_org, group=None, user=UserFactory.create(), code='register_' + str(i)) for i in range(7)]
        expected_unregister_members = []
        for i in range(2):
            user = UserFactory.create()
            expected_unregister_members.append(self._create_member(
                org=self.contract_org, group=None, user=user, code='unregister_' + str(i)))
            self.create_contract_register(user=user, contract=self.contract)

        expected_masked_members = []
        for i in range(1):
            user = UserFactory.create()
            expected_masked_members.append(self._create_member(
                org=self.contract_org, group=None, user=UserFactory.create(), code='masked_' + str(i),
                is_active=False, is_delete=True))
            self.create_contract_register(user=user, contract=self.contract)

        history = ReflectConditionTaskHistoryFactory.create(
            organization=self.contract_org, contract=self.contract, requester=self.user)
        entry = self._create_input_entry(
                organization=self.contract_org, contract=self.contract, send_mail_flg=1, history=history)

        self._test_run_with_task(
            reflect_conditions_immediate, 'reflect_conditions_immediate', 9, 9, 0,
            len(expected_register_members), len(expected_unregister_members), len(expected_masked_members), 9, entry)

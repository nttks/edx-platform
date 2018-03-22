"""
Tests for additional item task
"""
from mock import patch

from django.utils.crypto import get_random_string

from biz.djangoapps.ga_contract_operation.models import AdditionalInfoUpdateTaskTarget
from biz.djangoapps.ga_contract_operation.tasks import additional_info_update
from biz.djangoapps.ga_contract_operation.tests.factories import AdditionalInfoUpdateTaskTargetFactory
from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting
from biz.djangoapps.util.tests.testcase import BizViewTestBase
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin
from student.tests.factories import UserFactory

ADDITIONAL_INFO = ['setting1', 'setting2']


class AdditionalInfoTaskTest(BizViewTestBase, TaskTestMixin):

    def setUp(self):
        super(AdditionalInfoTaskTest, self).setUp()
        self.contract = self._create_contract()
        self.registers = [self._create_user_and_contract_register(self.contract) for _ in range(3)]
        self.history = self._create_task_history(contract=self.contract)
        self.additional_infos = [self._create_additional_info(contract=self.contract, display_name=d) for d in ADDITIONAL_INFO]
        self.additional_setting_value1 = get_random_string(8)
        self.additional_setting_value2 = get_random_string(8)

    @staticmethod
    def _create_targets(history, inputlines, completed=False):
        for inputline in inputlines:
            AdditionalInfoUpdateTaskTargetFactory.create(history=history, inputline=inputline, completed=completed)

    def _create_entry(self, contract=None, history=None, additional_infos=[]):
        task_input = {}
        if contract is not None:
            task_input['contract_id'] = contract.id
        if history is not None:
            task_input['history_id'] = history.id
        if additional_infos is not None:
            task_input['additional_info_ids'] = [a.id for a in additional_infos]
        return TaskTestMixin._create_input_entry(self, task_input=task_input)

    def _assert_additional_info_setting(self, user, display_name, value, contract=None):
        if contract is None:
            contract = self.contract
        additional_info_setting = AdditionalInfoSetting.objects.filter(
            contract=contract, user=user, display_name=display_name)
        self.assertEqual(value, additional_info_setting[0].value)

    def test_success_update_additional_info(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        input_line = ['{},{},{}'.format(self.registers[0].user.email,
                                        self.additional_setting_value1,
                                        self.additional_setting_value2)]
        self._create_targets(self.history, input_line)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            additional_info_update,
            'additionalinfo_update',
            task_entry=self._create_entry(
                contract=self.contract, history=self.history, additional_infos=self.additional_infos),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=False).count())
        self.assertEqual(1, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=True).count())
        self._assert_additional_info_setting(user=self.registers[0].user,
                                             display_name=ADDITIONAL_INFO[0],
                                             value=self.additional_setting_value1)
        self._assert_additional_info_setting(user=self.registers[0].user,
                                             display_name=ADDITIONAL_INFO[1],
                                             value=self.additional_setting_value2)

    def test_user_does_not_exist_in_gacco(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        email = '{}@gacco.com'.format(get_random_string(8))
        input_line = ['{},{},{}'.format(email,
                                        self.additional_setting_value1,
                                        self.additional_setting_value2)]
        self._create_targets(self.history, input_line)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            additional_info_update,
            'additionalinfo_update',
            task_entry=self._create_entry(
                contract=self.contract, history=self.history, additional_infos=self.additional_infos),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=False).count())
        self.assertEqual(1, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=True).count())
        self.assertEqual(
            "Line 1:The user does not exist. ({email})".format(email=email),
            AdditionalInfoUpdateTaskTarget.objects.get(history=self.history).message,
        )

    def test_user_does_not_exist_in_contract(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        user = UserFactory.create()
        input_line = ['{},{},{}'.format(user.email,
                                        self.additional_setting_value1,
                                        self.additional_setting_value2)]
        self._create_targets(self.history, input_line)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            additional_info_update,
            'additionalinfo_update',
            task_entry=self._create_entry(
                contract=self.contract, history=self.history, additional_infos=self.additional_infos),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=False).count())
        self.assertEqual(1, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=True).count())
        self.assertEqual(
            "Line 1:Could not find target user.",
            AdditionalInfoUpdateTaskTarget.objects.get(history=self.history).message,
        )

    def test_additional_info_over_max_char_length(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        over_max_char_length = get_random_string(256)
        input_line = ['{},{},{}'.format(self.registers[0].user.email,
                                        self.additional_setting_value1,
                                        over_max_char_length)]
        self._create_targets(self.history, input_line)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            additional_info_update,
            'additionalinfo_update',
            task_entry=self._create_entry(
                contract=self.contract, history=self.history, additional_infos=self.additional_infos),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=False).count())
        self.assertEqual(1, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=True).count())
        self.assertEqual(
            "Line 1:Please enter the name of item within 255 characters.",
            AdditionalInfoUpdateTaskTarget.objects.get(history=self.history).message,
        )

    def test_number_of_args_does_not_match(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        input_line = ['{},{}'.format(self.registers[0].user.email,
                                     self.additional_setting_value1)]
        self._create_targets(self.history, input_line)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            additional_info_update,
            'additionalinfo_update',
            task_entry=self._create_entry(
                contract=self.contract, history=self.history, additional_infos=self.additional_infos),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=False).count())
        self.assertEqual(1, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=True).count())
        self.assertEqual(
            "Line 1:Number of [emails] and [new items] must be the same.",
            AdditionalInfoUpdateTaskTarget.objects.get(history=self.history).message,
        )

    def test_additional_info_changed(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        additional_info = ['setting3']
        additional_infos = [self._create_additional_info(contract=self.contract, display_name=d) for d in additional_info]
        input_line = ['{},{},{}'.format(self.registers[0].user.email,
                                        self.additional_setting_value1,
                                        self.additional_setting_value2)]
        self._create_targets(self.history, input_line)

        # ----------------------------------------------------------
        # Execute task, Assertion
        # ----------------------------------------------------------
        entry = self._create_entry(contract=self.contract, history=self.history, additional_infos=additional_infos)
        with self.assertRaises(ValueError) as cm:
            self._test_run_with_task(
                additional_info_update,
                'additionalinfo_update',
                task_entry=entry,
                expected_attempted=1,
                expected_num_failed=1,
                expected_total=1,
            )
        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual("Task {}: Additional item is changed".format(entry.task_id), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_contract_id_does_not_exist(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        input_line = ['{},{},{}'.format(self.registers[0].user.email,
                                        self.additional_setting_value1,
                                        self.additional_setting_value2)]
        self._create_targets(self.history, input_line)
        contract = self._create_contract()

        # ----------------------------------------------------------
        # Execute task, Assertion
        # ----------------------------------------------------------
        entry = self._create_entry(contract=contract, history=self.history, additional_infos=self.additional_infos)
        with self.assertRaises(ValueError):
            self._test_run_with_failure(
                additional_info_update,
                "Contract id conflict: submitted value {} does not match {}".format(self.contract.id, contract.id),
                task_entry=entry,
            )

    def test_unexpected_exception(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        input_line = ['{},{},{}'.format(self.registers[0].user.email,
                                        self.additional_setting_value1,
                                        self.additional_setting_value2)]
        self._create_targets(self.history, input_line)

        # ----------------------------------------------------------
        # Execute task, Assertion
        # ----------------------------------------------------------
        with patch('biz.djangoapps.ga_contract_operation.additionalinfo.AdditionalInfoSetting.save', side_effect=Exception):
            self._test_run_with_task(
                additional_info_update,
                'additionalinfo_update',
                task_entry=self._create_entry(
                    contract=self.contract, history=self.history, additional_infos=self.additional_infos),
                expected_attempted=1,
                expected_num_failed=1,
                expected_total=1,
            )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(1, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=False).count())
        self.assertEqual(0, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=True).count())
        self.assertEqual(
            "Line 1:Failed to register. Please operation again after a time delay.",
            AdditionalInfoUpdateTaskTarget.objects.get(history=self.history).message
        )

    def test_multiple_line_succeeded_skipped_failed(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        line1 = ''
        line2 = '{},{},{}'.format(self.registers[0].user.email,
                                  self.additional_setting_value1,
                                  self.additional_setting_value2)
        line3 = '{},{}'.format(self.registers[1].user.email,
                               self.additional_setting_value1)
        input_line = [line1, line2, line3]
        self._create_targets(self.history, input_line)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            additional_info_update,
            'additionalinfo_update',
            task_entry=self._create_entry(
                contract=self.contract, history=self.history, additional_infos=self.additional_infos),
            expected_attempted=3,
            expected_num_succeeded=1,
            expected_num_skipped=1,
            expected_num_failed=1,
            expected_total=3,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=False).count())
        self.assertEqual(3, AdditionalInfoUpdateTaskTarget.objects.filter(history=self.history, completed=True).count())
        self._assert_additional_info_setting(user=self.registers[0].user,
                                             display_name=ADDITIONAL_INFO[0],
                                             value=self.additional_setting_value1)
        self._assert_additional_info_setting(user=self.registers[0].user,
                                             display_name=ADDITIONAL_INFO[1],
                                             value=self.additional_setting_value2)

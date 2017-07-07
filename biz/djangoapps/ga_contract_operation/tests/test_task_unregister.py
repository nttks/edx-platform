"""Tests for task"""

from datetime import timedelta
import json
from mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from student.tests.factories import (
    UserFactory
)
from third_party_auth.tests.testutil import ThirdPartyAuthTestMixin
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from biz.djangoapps.ga_contract.models import CONTRACT_TYPE_GACCO_SERVICE, CONTRACT_TYPE_PF
from biz.djangoapps.ga_contract.tests.factories import AdditionalInfoFactory, ContractFactory, ContractDetailFactory
from biz.djangoapps.ga_contract_operation.models import StudentUnregisterTaskTarget
from biz.djangoapps.ga_contract_operation.tasks import student_unregister
from biz.djangoapps.ga_contract_operation.tests.factories import StudentUnregisterTaskTargetFactory
from biz.djangoapps.ga_contract_operation.tests.test_tasks import StudentsTaskTestMixin
from biz.djangoapps.ga_invitation.models import ContractRegister, UNREGISTER_INVITATION_CODE
from biz.djangoapps.util.datetime_utils import timezone_today
from biz.djangoapps.util.tests.testcase import BizTestBase
from openedx.core.djangoapps.ga_task.models import Task
from student.models import CourseEnrollment


class UnregisterTaskTest(BizTestBase, ModuleStoreTestCase, ThirdPartyAuthTestMixin, StudentsTaskTestMixin):

    def setUp(self):
        super(UnregisterTaskTest, self).setUp()

        patcher = patch('biz.djangoapps.ga_contract_operation.student_unregister.log')
        self.mock_log = patcher.start()
        self.addCleanup(patcher.stop)

    def _create_contract(self, contract_type=CONTRACT_TYPE_PF[0], courses=[], display_names=[]):
        start_date = timezone_today() - timedelta(days=1)

        contract = ContractFactory.create(
            contract_type=contract_type,
            contractor_organization=self.gacco_organization,
            owner_organization=self.gacco_organization,
            created_by=UserFactory.create(),
            start_date=start_date
        )

        for course in courses:
            ContractDetailFactory.create(contract=contract, course_id=course.id)

        for display_name in display_names:
            AdditionalInfoFactory.create(contract=contract, display_name=display_name)

        return contract

    def _create_task_unregister_target(self, history, inputdata_list):
        for inputdata in inputdata_list:
            StudentUnregisterTaskTargetFactory.create(history=history, inputdata=inputdata)

    def _assert_unenrolled_course(self, registers, courses):
        for register in registers:
            for course in courses:
                self.assertFalse(CourseEnrollment.is_enrolled(register.user, course.id))

    def _assert_enrolled_course(self, registers, courses):
        for register in registers:
            for course in courses:
                self.assertTrue(CourseEnrollment.is_enrolled(register.user, course.id))

    def _assert_success_message(self, registers):
        task = Task.objects.latest('id')
        for register in registers:
            self.mock_log.info.assert_any_call(
                'Task {}: Success to process of students unregistered to User {}'.format(task.task_id, register.user_id)
            )

    def _assert_failed_message(self, registers):
        task = Task.objects.latest('id')
        for register in registers:
            self.mock_log.exception.assert_any_call(
                'Task {}: Failed to process of the students unregistered to User {}'.format(task.task_id, register.user.username)
            )

    def test_missing_current_task(self):
        self._test_missing_current_task(student_unregister)

    def test_run_with_failure(self):
        contract = self._create_contract()
        history = self._create_task_history(contract)
        entry = self._create_input_entry(contract=contract, history=history)
        self._test_run_with_failure(student_unregister, 'We expected this to fail', entry)

    def test_run_with_long_error_msg(self):
        contract = self._create_contract()
        history = self._create_task_history(contract)
        entry = self._create_input_entry(contract=contract, history=history)
        self._test_run_with_long_error_msg(student_unregister, entry)

    def test_run_with_short_error_msg(self):
        contract = self._create_contract()
        history = self._create_task_history(contract)
        entry = self._create_input_entry(contract=contract, history=history)
        self._test_run_with_short_error_msg(student_unregister, entry)

    def test_missing_required_input_history(self):
        entry = self._create_input_entry(contract=self._create_contract())

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(student_unregister, entry.id, entry.task_id)

        self.assertEqual("Task {}: Missing required value {}".format(entry.task_id, json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_missing_required_input_contract(self):
        entry = self._create_input_entry(history=self._create_task_history(self._create_contract()))

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(student_unregister, entry.id, entry.task_id)

        self.assertEqual("Task {}: Missing required value {}".format(entry.task_id, json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_history_does_not_exists(self):
        contract = self._create_contract()
        history = self._create_task_history(contract)
        entry = self._create_input_entry(contract=contract, history=history)
        history.delete()

        with self.assertRaises(ObjectDoesNotExist):
            self._run_task_with_mock_celery(student_unregister, entry.id, entry.task_id)

        self._assert_task_failure(entry.id)

    def test_conflict_contract(self):
        contract = self._create_contract()
        # Create history with other contract
        history = self._create_task_history(self._create_contract())
        entry = self._create_input_entry(contract=contract, history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(student_unregister, entry.id, entry.task_id)

        self.assertEqual("Contract id conflict: submitted value {} does not match {}".format(history.contract_id, contract.id), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_successful(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self._configure_dummy_provider(enabled=True)
        self._setup_courses()
        display_names = ['settting1', 'setting2', ]
        contract = self._create_contract(courses=self.spoc_courses, display_names=display_names)
        history = self._create_task_history(contract=contract)

        # users: enrolled only target spoc courses
        registers = [self._create_user_and_register(contract, display_names=display_names) for _ in range(5)]
        inputdata_list = [register.user.username for register in registers]
        self._create_task_unregister_target(history, inputdata_list)
        self._create_enrollments(registers, self.spoc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(student_unregister, 'student_unregister', 5, 0, 0, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Assert all of target is unregistered
        self.assertEqual(5, ContractRegister.objects.filter(contract=contract, status=UNREGISTER_INVITATION_CODE).count())
        self._assert_unenrolled_course(registers, self.spoc_courses)

        self._assert_success_message(registers)
        self.mock_log.exception.assert_not_called()

    def test_successful_mooc(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self._configure_dummy_provider(enabled=True)
        self._setup_courses()
        display_names = ['settting1', 'setting2', ]
        contract = self._create_contract(
            contract_type=CONTRACT_TYPE_GACCO_SERVICE[0],
            courses=self.mooc_courses,
            display_names=display_names
        )
        history = self._create_task_history(contract=contract)

        # users: enrolled only target mooc courses
        registers = [self._create_user_and_register(contract, display_names=display_names) for _ in range(5)]
        inputdata_list = [register.user.username for register in registers]
        self._create_task_unregister_target(history, inputdata_list)
        self._create_enrollments(registers, self.mooc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(student_unregister, 'student_unregister', 5, 0, 0, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Assert all of target is unregistered
        self.assertEqual(5, ContractRegister.objects.filter(contract=contract, status=UNREGISTER_INVITATION_CODE).count())
        self._assert_enrolled_course(registers, self.mooc_courses)

        self._assert_success_message(registers)
        self.mock_log.exception.assert_not_called()

    def test_successful_spoc_staff(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self._configure_dummy_provider(enabled=True)
        self._setup_courses()
        display_names = ['settting1', 'setting2', ]
        contract = self._create_contract(courses=self.spoc_courses, display_names=display_names)
        history = self._create_task_history(contract=contract)

        # users: enrolled only target spoc courses
        registers = [self._create_user_and_register(contract, display_names=display_names) for _ in range(5)]
        # user set staff roll
        for register in registers:
            register.user.is_staff = True
            register.user.save()
        inputdata_list = [register.user.username for register in registers]
        self._create_task_unregister_target(history, inputdata_list)
        self._create_enrollments(registers, self.spoc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(student_unregister, 'student_unregister', 5, 0, 0, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Assert all of target is unregistered
        self.assertEqual(5, ContractRegister.objects.filter(contract=contract, status=UNREGISTER_INVITATION_CODE).count())
        self._assert_enrolled_course(registers, self.spoc_courses)

        self._assert_success_message(registers)
        self.mock_log.exception.assert_not_called()

    def test_successful_with_failed(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self._configure_dummy_provider(enabled=True)
        self._setup_courses()
        display_names = ['settting1', 'setting2', ]
        contract = self._create_contract(courses=self.spoc_courses, display_names=display_names)
        history = self._create_task_history(contract=contract)

        # users: enrolled only target spoc courses
        registers = [self._create_user_and_register(contract, display_names=display_names) for _ in range(5)]
        inputdata_list = [register.user.username for register in registers]
        self._create_task_unregister_target(history, inputdata_list)
        self._create_enrollments(registers, self.spoc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        with patch(
            'student.models.CourseEnrollment.is_enrolled'
        ) as mock_is_enrolled:
            # raise Exception at last call
            side_effect_param = []
            for regiseter in registers[:4]:
                for course in self.spoc_courses:
                    side_effect_param.append(True)
            side_effect_param.append(Exception)
            mock_is_enrolled.side_effect = side_effect_param
            self._test_run_with_task(student_unregister, 'student_unregister', 4, 0, 1, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Assert 4 target is completed
        self.assertEqual(4, ContractRegister.objects.filter(contract=contract, status=UNREGISTER_INVITATION_CODE).count())
        self._assert_unenrolled_course(registers[:4], self.spoc_courses)
        self._assert_success_message(registers[:4])
        self._assert_enrolled_course(registers[4:], self.spoc_courses)
        self._assert_failed_message(registers[4:])
        self.assertEqual("Line 5:Failed to unregistered student. Please operation again after a time delay.",
                         StudentUnregisterTaskTarget.objects.get(history=history, inputdata=inputdata_list[4]).message)

    def test_input_validation_failed(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self._configure_dummy_provider(enabled=True)
        self._setup_courses()
        display_names = ['settting1', 'setting2', ]
        contract = self._create_contract(courses=self.spoc_courses, display_names=display_names)

        # users: enrolled only target spoc courses
        registers = [self._create_user_and_register(contract, display_names=display_names) for _ in range(4)]
        registers.append(self._create_user_and_register(contract, display_names=display_names, status=UNREGISTER_INVITATION_CODE))
        registers.append(self._create_user_and_register(contract, display_names=display_names))
        history = self._create_task_history(contract=contract, requester=registers[3].user)

        inputdata_list = [
            "",
            "{},{}".format(registers[1].user.username, registers[1].user.id),
            "{}unknown".format(registers[2].user.username),
            registers[3].user.username,
            registers[4].user.username,
            registers[5].user.username,
        ]

        self._create_task_unregister_target(history, inputdata_list)
        self._create_enrollments(registers, self.spoc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(student_unregister, 'student_unregister', 1, 2, 3, 6, 6, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Assert 1 of target is unregistered
        self.assertEqual(2, ContractRegister.objects.filter(contract=contract, status=UNREGISTER_INVITATION_CODE).count())
        self._assert_unenrolled_course(registers[5:], self.spoc_courses)
        self._assert_success_message(registers[5:])

        # Assert 1st task is skip
        self.assertEqual(None,
                         StudentUnregisterTaskTarget.objects.get(history=history, inputdata=inputdata_list[0]).message)
        # Assert 2nd task is unmatch colunn
        self.assertEqual("Line 2:Data must have exactly one column: username.",
                         StudentUnregisterTaskTarget.objects.get(history=history, inputdata=inputdata_list[1]).message)
        # Assert 3rd task is register not found
        self.assertEqual("Line 3:username {username} is not registered student.".format(username=inputdata_list[2]),
                         StudentUnregisterTaskTarget.objects.get(history=history, inputdata=inputdata_list[2]).message)
        # Assert 4th task is select yourself
        self.assertEqual("Line 4:You can not change of yourself.",
                         StudentUnregisterTaskTarget.objects.get(history=history, inputdata=inputdata_list[3]).message)
        # Assert 5th task is already unregister
        self.assertEqual("Line 5:username {username} already unregistered student.".format(username=inputdata_list[4]),
                         StudentUnregisterTaskTarget.objects.get(history=history, inputdata=inputdata_list[4]).message)

        self.mock_log.exception.assert_not_called()

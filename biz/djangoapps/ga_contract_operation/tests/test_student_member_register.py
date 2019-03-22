"""Tests for student member register task"""

import ddt
import json
from mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.test.utils import override_settings

from bulk_email.models import Optout
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from biz.djangoapps.ga_contract_operation.models import StudentMemberRegisterTaskTarget
from biz.djangoapps.ga_contract_operation.tasks import student_member_register
from biz.djangoapps.ga_contract_operation.tests.factories import StudentMemberRegisterTaskTargetFactory
from biz.djangoapps.ga_invitation.models import ContractRegister, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_login.models import BizUser
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from biz.djangoapps.gx_username_rule.tests.factories import OrgUsernameRuleFactory
from biz.djangoapps.util.tests.testcase import BizViewTestBase
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin
from student.models import CourseEnrollment
from student.tests.factories import UserFactory


@ddt.ddt
class StudentMemberRegisterTaskTest(BizViewTestBase, ModuleStoreTestCase, TaskTestMixin):

    def setUp(self):
        super(StudentMemberRegisterTaskTest, self).setUp()
        self._create_contract_mail_default()

    def _create_targets(self, history, students, completed=False):
        for student in students:
            StudentMemberRegisterTaskTargetFactory.create(history=history, student=student, completed=completed)

    def _create_input_entry(self, contract=None, history=None):
        task_input = {}
        if contract is not None:
            task_input['contract_id'] = contract.id
        if history is not None:
            task_input['history_id'] = history.id
        task_input['sendmail_flg'] = 'on'
        return TaskTestMixin._create_input_entry(self, task_input=task_input)

    def _create_input_entry_not_sendmail(self, contract=None, history=None):
        task_input = {}
        if contract is not None:
            task_input['contract_id'] = contract.id
        if history is not None:
            task_input['history_id'] = history.id
        task_input['sendmail_flg'] = ''
        return TaskTestMixin._create_input_entry(self, task_input=task_input)

    def _assert_history_after_execute_task(self, history_id, result, message=None):
        """
        Check MemberTaskHistory data has updated
        :param history_id: MemberTaskHistory.id
        :param result: 0(False) or 1(True)
        :param message: str
        """
        history = StudentMemberRegisterTaskTarget.objects.get(id=history_id)
        self.assertEqual(result, history.completed)

    def setup_user(self, login_code=None):
        super(StudentMemberRegisterTaskTest, self).setup_user()
        self.login_code = login_code
        if login_code:
            BizUserFactory.create(user=self.user, login_code=login_code)

    def test_missing_required_input_history(self):
        entry = self._create_input_entry(contract=self._create_contract())

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(student_member_register, entry.id, entry.task_id)

        self.assertEqual("Task {}: Missing required value {}".format(
            entry.task_id, json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_missing_required_input_contract(self):
        entry = self._create_input_entry(history=self._create_task_history(self._create_contract()))

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(student_member_register, entry.id, entry.task_id)

        self.assertEqual("Task {}: Missing required value {}".format(
            entry.task_id, json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_history_does_not_exists(self):
        contract = self._create_contract()
        history = self._create_task_history(contract)
        entry = self._create_input_entry(contract=contract, history=history)
        history.delete()

        with self.assertRaises(ObjectDoesNotExist):
            self._run_task_with_mock_celery(student_member_register, entry.id, entry.task_id)

        self._assert_task_failure(entry.id)

    def test_conflict_contract(self):
        contract = self._create_contract()
        # Create history with other contract
        history = self._create_task_history(self._create_contract())
        entry = self._create_input_entry(contract=contract, history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(student_member_register, entry.id, entry.task_id)

        self.assertEqual("Contract id conflict: submitted value {} does not match {}".format(
            history.contract_id, contract.id), cm.exception.message)
        self._assert_task_failure(entry.id)

    @ddt.data(
        (None, ["Input,test_student1@example.com,t,t,t,,,,,,,,,,,,,,,,,,,,,,"]),
        ('contract-url-code', ["Input,test_student1@example.com,t,t,t,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,"]),
    )
    @ddt.unpack
    def test_register_validation(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            #"Line 1:" + ' '.join(["Username must be minimum of two characters long", "Your legal name must be a minimum of two characters long"]
            "Line 1:Username must be minimum of two characters long",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message,
        )

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    @ddt.data('t', 'Test@Student_1', 'Test_Student_1Test_Student_1Test_Student_1')
    def test_register_validation_login_code(self, login_code):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = ["Input,test_student@example.com,test_student_1,tester1,test1,{login_code},TestStudent1,,,,,,,,,,,,,,,,,,,,,,".format(login_code=login_code)]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            "Line 1:Invalid login code {login_code}.".format(login_code=login_code),
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message,
        )

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    @override_settings(
        PASSWORD_MIN_LENGTH=7,
        PASSWORD_COMPLEXITY={
            'DIGITS': 1, 
            'LOWER': 1, 
            'UPPER': 1,
        }
    )
    @ddt.data('abAB12', 'abcdABCD', 'abcd1234', 'ABCD1234')
    def test_register_validation_password(self, password):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = ["Input,test_student@example.com,test_student_1,tester1,test1,Test_Student_1,{password},,,,,,,,,,,,,,,,,,,,,,".format(password=password)]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            "Line 1:Invalid password {password}.".format(password=password),
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message,
        )

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    @ddt.data(
        (None, ["Input,test_student@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,"]),
        ('contract-url-code', ["Input,test_student@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,"]),
    )
    @ddt.unpack
    def test_register_account_creation(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        global_course_id = CourseFactory.create(org='global', course='course1', run='run').id

        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message)

        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(Optout.objects.filter(user=user, course_id=global_course_id).exists())
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=user).login_code)

    @ddt.data(
        (None, ["Input,test_student@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,"]),
        ('contract-url-code', ["Input,test_student@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,"]),
    )
    @ddt.unpack
    def test_register_account_creation_with_global_course(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        global_course_id = CourseFactory.create(org='global', course='course1', run='run').id
        CourseGlobalSettingFactory.create(course_id=global_course_id)

        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message)

        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertTrue(Optout.objects.filter(user=user, course_id=global_course_id).exists())
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=user).login_code)

    @ddt.data(
        (None, ["Input,", "Input,test_student@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,", "Register,", "Input,"]),
        ('contract-url-code', ["Input,", "Input,test_student@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,", "Register,", "Input,"]),
    )
    @ddt.unpack
    def test_register_account_creation_with_blank_lines(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=4,
            expected_num_succeeded=1,
            expected_num_skipped=3,
            expected_total=4,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(4, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(4, StudentMemberRegisterTaskTarget.objects.filter(history=history, message__isnull=True).count())

        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=user).login_code)

    @ddt.data(
        (None, [
            "Input,test_student@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student@example.com,test_student_1,tester2,test2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student@example.com,test_student_1,tester2,test2,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_email_and_username_already_exist(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_succeeded=2,
            expected_total=2,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(2, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(2, StudentMemberRegisterTaskTarget.objects.filter(history=history, message__isnull=True).count())

        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=user).login_code)

    @ddt.data(
        (
            None,
            ["Input,test_student@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,", "Input,"],
            "Line 1:Data must have exactly 26 columns: email, username, firstname and lastname."
        ),
        (
            'contract-url-code',
            ["Input,test_student@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,", "Input,"],
            "Line 1:Data must have exactly 28 columns: email, username, firstname, lastname, login code and password."
        ),
    )
    @ddt.unpack
    def test_register_insufficient_data(self, url_code, students, message):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_failed=1,
            expected_num_skipped=1,
            expected_total=2,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(2, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            message,
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[1]).message)

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    @ddt.data(
        (None, ["Input,test_student.example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,"]),
        ('contract-url-code', ["Input,test_student.example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,"]),
    )
    @ddt.unpack
    def test_register_invalid_email(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            "Line 1:Invalid email test_student.example.com.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    @ddt.data(
        (None, ["Input,{email},test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,"]),
        ('contract-url-code', ["Input,{email},test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,"]),
    )
    @ddt.unpack
    def test_register_user_with_already_existing_email(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        global_course_id = CourseFactory.create(org='global', course='course1', run='run').id
        CourseGlobalSettingFactory.create(course_id=global_course_id)

        self.setup_user()
        students = [s.format(email=self.email) for s in students]

        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIn(
            "Warning, an account with the e-mail {email} exists but the registered username {username} is different.".format(email=self.email, username=self.username),
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        if url_code:
            self.assertIn(
                "Warning, an account with the e-mail {email} exists but the registered password is different.".format(email=self.email),
                StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
            )

        self.assertEqual(ContractRegister.objects.get(user__email=self.email, contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(Optout.objects.filter(user=self.user, course_id=global_course_id).exists())
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=self.user).login_code)

    @ddt.data(
        (None, ["Input,{email},test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,"]),
        ('contract-url-code', ["Input,{email},test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,"]),
    )
    @ddt.unpack
    def test_register_user_with_already_existing_contract_register_input(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        global_course_id = CourseFactory.create(org='global', course='course1', run='run').id
        CourseGlobalSettingFactory.create(course_id=global_course_id)

        self.setup_user()
        students = [s.format(email=self.email) for s in students]

        contract = self._create_contract(url_code=url_code)
        ContractRegisterFactory.create(user=self.user, contract=contract, status=INPUT_INVITATION_CODE)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIn(
            "Warning, an account with the e-mail {email} exists but the registered username {username} is different.".format(email=self.email, username=self.username),
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        if url_code:
            self.assertIn(
                "Warning, an account with the e-mail {email} exists but the registered password is different.".format(email=self.email),
                StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
            )

        self.assertEqual(ContractRegister.objects.get(user__email=self.email, contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(Optout.objects.filter(user=self.user, course_id=global_course_id).exists())
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=self.user).login_code)

    @ddt.data(
        (None, ["Input,{email},test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,"]),
        ('contract-url-code', ["Input,{email},test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,"]),
    )
    @ddt.unpack
    def test_register_user_with_already_existing_contract_register_register(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        global_course_id = CourseFactory.create(org='global', course='course1', run='run').id
        CourseGlobalSettingFactory.create(course_id=global_course_id)

        self.setup_user()
        students = [s.format(email=self.email) for s in students]

        contract = self._create_contract(url_code=url_code)
        ContractRegisterFactory.create(user=self.user, contract=contract, status=REGISTER_INVITATION_CODE)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIn(
            "Warning, an account with the e-mail {email} exists but the registered username {username} is different.".format(email=self.email, username=self.username),
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        if url_code:
            self.assertIn(
                "Warning, an account with the e-mail {email} exists but the registered password is different.".format(email=self.email),
                StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
            )

        self.assertEqual(ContractRegister.objects.get(user__email=self.email, contract=contract).status, REGISTER_INVITATION_CODE)
        self.assertFalse(Optout.objects.filter(user=self.user, course_id=global_course_id).exists())
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=self.user).login_code)

    def test_register_user_with_already_existing_all_same(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user('Test_Student_1')
        students = ["Input,{email},{username},username,username,{login_code},{password},,,,,,,,,,,,,,,,,,,,,,".format(
            email=self.email,
            username=self.username,
            login_code=self.login_code,
            password=self.password,
        )]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())

        self.assertEqual(self.login_code, BizUser.objects.get(user=self.user).login_code)

    def test_register_user_with_already_existing_diff_login_code(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user('Test_Student_1')
        students = ["Input,{email},{username},username,username,{login_code},{password},,,,,,,,,,,,,,,,,,,,,,".format(
            email=self.email,
            username=self.username,
            login_code='Test_Student_12',
            password=self.password,
        )]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())

        self.assertIn(
            "Warning, an account with the e-mail {email} exists but the registered login code {login_code} is different.".format(email=self.email, login_code=self.login_code),
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertEqual(self.login_code, BizUser.objects.get(user=self.user).login_code)

    def test_register_user_with_already_existing_diff_password(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user('Test_Student_1')
        students = ["Input,{email},{username},username,username,{login_code},{password},,,,,,,,,,,,,,,,,,,,,,".format(
            email=self.email,
            username=self.username,
            login_code=self.login_code,
            password='Password123',
        )]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())

        self.assertIn(
            "Warning, an account with the e-mail {email} exists but the registered password is different.".format(email=self.email),
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertEqual(self.login_code, BizUser.objects.get(user=self.user).login_code)

    def test_register_user_with_already_existing_diff_login_code_password(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user('Test_Student_1')
        students = ["Input,{email},{username},username,username,{login_code},{password},,,,,,,,,,,,,,,,,,,,,,".format(
            email=self.email,
            username=self.username,
            login_code='Test_Student_12',
            password='Password123',
        )]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())

        self.assertIn(
            "Warning, an account with the e-mail {email} exists but the registered login code {login_code} is different.".format(email=self.email, login_code=self.login_code),
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        self.assertIn(
            "Warning, an account with the e-mail {email} exists but the registered password is different.".format(email=self.email),
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertEqual(self.login_code, BizUser.objects.get(user=self.user).login_code)

    def test_register_user_same_login_code(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user('Test_Student_1')
        students = [
            "Input,test_student1@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,{email},{username},tester2,test2,Test_Student_1,{password},,,,,,,,,,,,,,,,,,,,,,".format(email=self.email, username=self.username, password=self.password),
        ]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_succeeded=1,
            expected_num_failed=1,
            expected_total=2,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(2, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())

        self.assertEqual(
            "Line 2:Login code Test_Student_1 already exists.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

        self.assertEqual(2, BizUser.objects.filter(login_code=self.login_code).count())
        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email=self.email, contract=contract).exists())

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_1,tester2,test2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_1,tester2,test2,Test_Student_2,TestStudent2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_user_with_already_existing_username(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_succeeded=1,
            expected_num_failed=1,
            expected_total=2,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(2, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message)
        self.assertEqual(
            "Line 2:Username test_student_1 already exists.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())

    def test_register_user_with_already_existing_login_code(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students =  [
            "Input,test_student1@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_2,tester2,test2,Test_Student_1,TestStudent2,,,,,,,,,,,,,,,,,,,,,,",
        ]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_succeeded=1,
            expected_num_failed=1,
            expected_total=2,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(2, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message)
        self.assertEqual(
            "Line 2:Login code Test_Student_1 already exists.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_1,tester2,test2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_1,tester2,test2,Test_Student_2,TestStudent2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_raising_exception_in_auto_registration_case(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        with patch('biz.djangoapps.ga_contract_operation.student_member_register.validate_email', side_effect=[None, Exception]):
            self._test_run_with_task(
                student_member_register,
                'student_member_register',
                task_entry=self._create_input_entry(contract=contract, history=history),
                expected_attempted=2,
                expected_num_succeeded=1,
                expected_num_failed=1,
                expected_total=2,
            )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message)
        self.assertEqual(
            "Line 2:Failed to register. Please operation again after a time delay.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student3@example.com,test_student_1,tester3,test3,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_2,tester2,test2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student3@example.com,test_student_1,tester3,test3,Test_Student_3,TestStudent3,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_2,tester2,test2,Test_Student_2,TestStudent2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_users_created_successfully_if_others_fail(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=3,
            expected_num_succeeded=2,
            expected_num_failed=1,
            expected_total=3,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(3, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message)
        self.assertEqual(
            "Line 2:Username test_student_1 already exists.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[2]).message)

        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student2@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=contract).exists())

    @patch('biz.djangoapps.ga_contract_operation.student_member_register.log.error')
    @ddt.data(
        (None, [
            "Register,test_student1@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,",
            "Unregister,test_student3@example.com,test_student_3,tester3,test3,,,,,,,,,,,,,,,,,,,,,,",
            "Register,test_student2@example.com,test_student_2,tester2,test2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Register,test_student1@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
            "Unregister,test_student3@example.com,test_student_3,tester3,test3,Test_Student_3,TestStudent3,,,,,,,,,,,,,,,,,,,,,,",
            "Register,test_student2@example.com,test_student_2,tester2,test2,Test_Student_2,TestStudent2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_users_created_successfully_if_others_fail_register(self, url_code, students, error_log):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        course = CourseFactory.create()
        contract = self._create_contract(url_code=url_code, detail_courses=[course])
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=3,
            expected_num_succeeded=2,
            expected_num_failed=1,
            expected_total=3,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(3, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message)
        error_log.assert_any_call('Invalid status: Unregister.')
        self.assertEqual(
            "Line 2:Failed to register. Please operation again after a time delay.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[2]).message)

        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, REGISTER_INVITATION_CODE)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student2@example.com', contract=contract).status, REGISTER_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=contract).exists())

        self.assertTrue(CourseEnrollment.objects.get(user__email='test_student1@example.com', course_id=course.id).is_active)
        self.assertTrue(CourseEnrollment.objects.get(user__email='test_student2@example.com', course_id=course.id).is_active)
        self.assertFalse(CourseEnrollment.objects.filter(user__email='test_student3@example.com', course_id=course.id).exists())

    @ddt.data(
        (None, [
            "Input,test_student1test_student1test_student1test_student1test_student@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student3@example.com,test_student_1test_student_1test_stu,tester3,test3,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_2,tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2test,test2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student1test_student1test_student1test_student1test_student@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student3@example.com,test_student_1test_student_1test_stu,tester3,test3,Test_Student_3,TestStudent3,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_2,tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2test,test2,Test_Student_2,TestStudent2,,,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_over_max_char_length(self, url_code, students):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=3,
            expected_num_failed=3,
            expected_total=3,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(3, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            "Line 1:Email cannot be more than 75 characters long",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        self.assertEqual(
            "Line 2:Username cannot be more than 30 characters long",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )
        self.assertEqual(
            "Line 3:Name cannot be more than 255 characters long",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[2]).message
        )

        self.assertFalse(ContractRegister.objects.filter(user__email='test_student1@example.com', contract=contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=contract).exists())

    @ddt.data(
        (None, None, [
            "Input,test_student@example.com,test_student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,",
        ], 1),
        ("contract-url-code", True, [
            "Input,test_student@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
        ], 1),
        ("contract-url-code", False, [
            "Input,test_student@example.com,test_student_1,tester1,test1,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
        ], 0),
    )
    @ddt.unpack
    @patch('biz.djangoapps.ga_contract_operation.student_member_register.django_send_mail')
    def test_register_send_mail(self, url_code, send_mail, students, send_mail_call_count, send_mail_to_student):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code, send_mail=send_mail)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message)

        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=user).login_code)
        self.assertEqual(send_mail_call_count, send_mail_to_student.call_count)

    @ddt.data(
        (None, None, [
            "Input,test_student2@example.com,test_student_2,tester2,test2,,,,,,,,,,,,,,,,,,,,,,",
        ], 0),
        ("contract-url-code", True, [
            "Input,test_student2@example.com,test_student_2,tester2,test2,Test_Student_2,TestStudent2,,,,,,,,,,,,,,,,,,,,,,",
        ], 0),
        ("contract-url-code", False, [
            "Input,test_student2@example.com,test_student_2,tester2,test2,Test_Student_2,TestStudent2,,,,,,,,,,,,,,,,,,,,,,",
        ], 0),
    )
    @ddt.unpack
    @patch('biz.djangoapps.ga_contract_operation.student_member_register.django_send_mail')
    def test_register_not_send_mail(self, url_code, send_mail, students, send_mail_call_count, send_mail_to_student):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        contract = self._create_contract(url_code=url_code, send_mail=send_mail)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry_not_sendmail(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message)

        user = User.objects.get(email='test_student2@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student2@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        if url_code:
            self.assertEqual('Test_Student_2', BizUser.objects.get(user=user).login_code)
        self.assertEqual(send_mail_call_count, send_mail_to_student.call_count)

    # --------------------------------
    # StudentMemberRegisterAdditions
    # --------------------------------
    @ddt.data(
        (None, [
            "Input,test_student@example.com,test_student_1,tester1,,,,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student@example.com,test_student_1,tester1,,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_first_name_empty(self, url_code, students):
        # Setup test data
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)
        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )
        # Assertion
        self.assertEqual(0, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(1, StudentMemberRegisterTaskTarget.objects.filter(history=history, message__isnull=True).count())
        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)

    # --------------------------------
    # StudentMemberRegisterAdditions
    # --------------------------------
    @ddt.data(
        (None, [
            "Input,test_student@example.com,test_student_1,,,,,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student@example.com,test_student_1,,,Test_Student_1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_full_name_empty(self, url_code, students):
        # Setup test data
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)
        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_failed=1,
        )
        # Assertion
        self.assertEqual(
            "Line 1:Must provide full name",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

    @ddt.data(
        ('contract-url-code', [
            "Input,test_student@example.com,test_student_1,tester1,test1,,TestStudent1,,,,,,,,,,,,,,,,,,,,,,",
            "Input,test_student@example.com,test_student_1,tester1,test1,TestStudent1,,,,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_login_code_empty(self, url_code, students):
        # Setup test data
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)
        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_failed=2,
            expected_total=2,
        )
        # Assertion
        self.assertEqual(
            "Line 1:The Login Code is required.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        self.assertEqual(
            "Line 2:The Password is required.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1,test1,,," + ('a' * 200) + ",,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_2,tester2,test2,,,,,,,,,,,,," + ('a' * 200) + ",,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,test1,TestStudent1,TestStudent1,,," + ('a' * 200) + ",,,,,,,,,,,,,,,,,,,",
            "Input,test_student2@example.com,test_student_2,tester2,test2,TestStudent2,TestStudent2,,,,,,,,,,,,," + ('a' * 200) + ",,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_over_max_length_org_item(self, url_code, students):
        # Setup test data
        contract = self._create_contract(url_code=url_code)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)
        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_failed=2,
        )
        # Assertion
        self.assertEqual(
            "Line 1:Please enter of Organization within 100 characters.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        self.assertEqual(
            "Line 2:Please enter of Item within 100 characters.",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1,test1,00001,00001,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,test1,TestStudent1,TestStudent1,00001,00001,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_member_not_org_group(self, url_code, students):
        # Setup test data
        contract = self._create_contract(url_code=url_code, contractor_organization=self.gacco_organization)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)
        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_failed=1,
        )
        # Assertion
        self.assertEqual(
            "Line 1:Member registration failed. Specified Organization code does not exist",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

    @ddt.data(
        (None, [
            "Input,foo@test.com,test_student_1,tester1,test1,00001,00002,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,foo@test.com,test_student_1,tester1,test1,TestStudent1,TestStudent1,00001,00002,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_member_code_used_new(self, url_code, students):
        # Setup test data
        GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='not_found_group_name', org=self.gacco_organization,
            created_by=self.user, modified_by=self.user
        )
        GroupFactory.create(
            parent_id=0, level_no=0, group_code='00002', group_name='not_found_group_name2', org=self.gacco_organization,
            created_by=self.user, modified_by=self.user
        )
        MemberFactory.create(
            org=self.gacco_organization,
            group=None,
            user=self.user,
            code='00001',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            is_active=True,
            is_delete=False,
        )
        active_user = UserFactory.create()
        MemberFactory.create(
            org=self.gacco_organization,
            group=None,
            user=active_user,
            code='00002',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            is_active=True,
            is_delete=False,
        )

        contract = self._create_contract(url_code=url_code, contractor_organization=self.gacco_organization)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_failed=1,
        )
        # Assertion
        self.assertEqual(
            "Line 1:Failed member master update. Mail address, member code must unique",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

    @ddt.data(
        (None, [
            "Input,test+courses@edx.org,test_student_1,tester1,test1,00001,00002,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test+courses@edx.org,test_student_1,tester1,test1,TestStudent1,TestStudent1,00001,00002,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_member_code_used(self, url_code, students):
        # Setup test data
        GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='not_found_group_name', org=self.gacco_organization,
            created_by=self.user, modified_by=self.user
        )
        GroupFactory.create(
            parent_id=0, level_no=0, group_code='00002', group_name='not_found_group_name2', org=self.gacco_organization,
            created_by=self.user, modified_by=self.user
        )
        MemberFactory.create(
            org=self.gacco_organization,
            group=None,
            user=self.user,
            code='00001',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            is_active=True,
            is_delete=False,
        )
        active_user = UserFactory.create()
        MemberFactory.create(
            org=self.gacco_organization,
            group=None,
            user=active_user,
            code='00002',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            is_active=True,
            is_delete=False,
        )

        contract = self._create_contract(url_code=url_code, contractor_organization=self.gacco_organization)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_failed=1,
        )
        # Assertion
        self.assertEqual(
            "Line 1:Failed member master update. Mail address, member code must unique",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

    @ddt.data(
        (None, [
            "Input,test+courses@edx.org,test_student_1,tester1,test1,00001,00001,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test+courses@edx.org,test_student_1,tester1,test1,TestStudent1,TestStudent1,00001,00001,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_member_deleted_status(self, url_code, students):
        # Setup test data
        group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='not_found_group_name', org=self.gacco_organization,
            created_by=self.user, modified_by=self.user
        )
        MemberFactory.create(
            org=self.gacco_organization,
            group=group,
            user=self.user,
            code='00001',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            is_active=False,
            is_delete=True,
        )

        contract = self._create_contract(url_code=url_code, contractor_organization=self.gacco_organization)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_failed=1,
        )
        # Assertion
        self.assertEqual(
            "Line 1:This code member deleted. Please student re-register after the unregistration",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1,test1,00001,00001,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,test1,TestStudent1,TestStudent1,00001,00001,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_member_group_code_not_exists(self, url_code, students):
        # Setup test data
        contract = self._create_contract(url_code=url_code, contractor_organization=self.gacco_organization)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_failed=1,
        )
        # Assertion
        self.assertEqual(
            "Line 1:Member registration failed. Specified Organization code does not exist",
            StudentMemberRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1,test1,00001,00001,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,test1,TestStudent1,TestStudent1,00001,00001,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_member_new_group(self, url_code, students):
        # Setup test data
        group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='not_found_group_name', org=self.gacco_organization,
            created_by=self.user, modified_by=self.user
        )

        contract = self._create_contract(url_code=url_code, contractor_organization=self.gacco_organization)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_succeeded=1,
        )
        self._assert_history_after_execute_task(history.id, 1, None)
        # Active data
        active_members = Member.objects.filter(
            org=self.gacco_organization, group=group, is_active=True)
        self.assertEqual(1, active_members.count())
        # Backup data
        backup_members = Member.objects.filter(org=self.gacco_organization, is_active=False, is_delete=False)
        self.assertEqual(1, backup_members.count())

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1,test1,,00001,,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,test1,TestStudent1,TestStudent1,,00001,,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_member_new_empty_group(self, url_code, students):
        # Setup test data
        contract = self._create_contract(url_code=url_code, contractor_organization=self.gacco_organization)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_succeeded=1,
        )
        self._assert_history_after_execute_task(history.id, 1, None)
        # Active data
        active_members = Member.objects.filter(
            org=self.gacco_organization, group=None, is_active=True)
        self.assertEqual(1, active_members.count())
        # Backup data
        backup_members = Member.objects.filter(org=self.gacco_organization, is_active=False, is_delete=False)
        self.assertEqual(1, backup_members.count())

    @ddt.data(
        (None, [
            "Input,test+courses@edx.org,test_student_1,tester1,test1,00001,00001,org1a,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code', [
            "Input,test+courses@edx.org,test_student_1,tester1,test1,TestStudent1,TestStudent1,00001,00001,org1a,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_member_code_match_update(self, url_code, students):
        # Setup test data
        group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='not_found_group_name', org=self.gacco_organization,
            created_by=self.user, modified_by=self.user
        )
        MemberFactory.create(
            org=self.gacco_organization,
            group=group,
            user=self.user,
            code='00001',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        contract = self._create_contract(url_code=url_code, contractor_organization=self.gacco_organization)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_succeeded=1,
        )
        self._assert_history_after_execute_task(history.id, 1, None)
        # Active data
        active_members = Member.objects.filter(
            org=self.gacco_organization, group=group, is_active=True, org1="org1a")
        self.assertEqual(1, active_members.count())
        # Backup data
        backup_members = Member.objects.filter(org=self.gacco_organization, is_active=False, is_delete=False)
        self.assertEqual(1, backup_members.count())

    @ddt.data(
        (None, [
            "Input,test+courses@edx.org,test_student_1,tester1,test1,00001,00002,org1a,,,,,,,,,,,,,,,,,,,",
        ]),
        ('contract-url-code2', [
            "Input,test+courses@edx.org,test_student_1,tester1,test1,TestStudent1,TestStudent1,00001,00002,org1a,,,,,,,,,,,,,,,,,,,",
        ]),
    )
    @ddt.unpack
    def test_register_member_code_update(self, url_code, students):
        # Setup test data
        group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='not_found_group_name', org=self.gacco_organization,
            created_by=self.user, modified_by=self.user
        )
        MemberFactory.create(
            org=self.gacco_organization,
            group=group,
            user=self.user,
            code='00001',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        contract = self._create_contract(url_code=url_code, contractor_organization=self.gacco_organization)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_succeeded=1,
        )
        self._assert_history_after_execute_task(history.id, 1, None)
        # Active data
        active_members = Member.objects.filter(
            org=self.gacco_organization, group=group, is_active=True, org1="org1a")
        self.assertEqual(1, active_members.count())
        # Backup data
        backup_members = Member.objects.filter(org=self.gacco_organization, is_active=False, is_delete=False)
        self.assertEqual(1, backup_members.count())

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,abc__student1,tester1,test1,00001,10001,,,,,,,,,,,,,,,,,,,,"], 1),
        (None, [
            "Input,test_student2@example.com,abc__student2,tester1,test1,,,,,,,,,,,,,,,,,,,,,,"], 2),
    )
    @ddt.unpack
    def test_main_org_username_rule_true(self, url_code, students, num):
        # Setup test data
        main_org = self._create_organization(org_name='main_org_rule_name',
                                                org_code='main_org_rule_code')
        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=main_org)

        group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='group_name', org=main_org,
            created_by=self.user, modified_by=self.user
        )
        contract = self._create_contract(url_code=url_code, contractor_organization=main_org)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_succeeded=1,
            expected_num_skipped=0,
            expected_num_failed=0,
            expected_attempted=1,
            expected_total=1
        )
        self._assert_history_after_execute_task(history.id, 1, None)
        if num == 1:
            members = Member.objects.filter(
                org=main_org, code='10001', is_active=True)
            self.assertEqual(1, members.count())

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,bc__student,tester1,test1,00001,20001,,,,,,,,,,,,,,,,,,,,"]),
        (None, [
            "Input,test_student2@example.com,abc_student,tester1,test1,00001,20002,,,,,,,,,,,,,,,,,,,,"]),
        (None, [
            "Input,test_student3@example.com,xabc__student,tester1,test1,00001,20003,,,,,,,,,,,,,,,,,,,,"]),

    )
    
    @ddt.unpack
    def test_main_org_username_rule_false(self, url_code, students):
        # Setup test data
        main_org = self._create_organization(org_name='main_org_rule_name',
                                                org_code='main_org_rule_code')
        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=main_org)

        group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='group_name', org=main_org,
            created_by=self.user, modified_by=self.user
        )
        contract = self._create_contract(url_code=url_code, contractor_organization=main_org)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)
    
        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_num_succeeded=0,
            expected_num_skipped=0,
            expected_num_failed=1,
            expected_attempted=1,
            expected_total=1
        )
        self._assert_history_after_execute_task(history.id, 1, history)

        members = Member.objects.filter(
            org=main_org, code='20003', is_active=True)
        self.assertEqual(0, members.count())
    
    @ddt.data(
        (None, [
            "Input,test_student1@example.com,abc__student_1,tester1,test1,00001,30001,,,,,,,,,,,,,,,,,,,,"], 1),
        (None, [
            "Input,test_student1@example.com,abc__student_2,tester1,test1,00001,30002,,,,,,,,,,,,,,,,,,,,"], 2),
        (None, [
            "Input,test_student1@example.com,bc__student,tester1,test1,00001,30003,,,,,,,,,,,,,,,,,,,,"], 3),
        (None, [
            "Input,test_student1@example.com,abc_student,tester1,test1,00001,30004,,,,,,,,,,,,,,,,,,,,"], 4),
        (None, [
            "Input,test_student1@example.com,xabc__student,tester1,test1,00001,30005,,,,,,,,,,,,,,,,,,,,"], 5),
        (None, [
            "Input,test_student1@example.com,cde__student,tester1,test1,00001,30006,,,,,,,,,,,,,,,,,,,,"], 6),
    )
    @ddt.unpack
    def test_another_org_username_rule(self, url_code, students, num):
        # Setup test data
        main_org = self._create_organization(org_name='main_org_rule_name',
                                                org_code='main_org_rule_code')
        another_org1 = self._create_organization(org_name='another_org_rule_name', org_code='another_org_rule_code')
        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=main_org)
        username_rule2 = OrgUsernameRuleFactory.create(prefix='cde__', org=another_org1)

        group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='group_name', org=another_org1,
            created_by=self.user, modified_by=self.user
        )

        contract = self._create_contract(url_code=url_code, contractor_organization=another_org1)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)
        if num == 6:
            success = 1
            fail = 0
        else:
            success = 0
            fail = 1
        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=success,
            expected_num_failed=fail,
            expected_total=1,
            expected_num_skipped=0
        )
        if num == 6:
            self._assert_history_after_execute_task(history.id, 1, None)

            members = Member.objects.filter(
                org=another_org1, code='30006', is_active=True)
            self.assertEqual(1, members.count())
        else:
            self._assert_history_after_execute_task(history.id, 1, history)

        members = Member.objects.filter(
            org=another_org1, code='30005', is_active=True)
        self.assertEqual(0, members.count())



    @ddt.data(
        (None, [
            "Input,test_student1@example.com,abc__student_1,tester1,test1,00001,40001,,,,,,,,,,,,,,,,,,,,"], 1),
        (None, [
            "Input,test_student1@example.com,abc__student_2,tester1,test1,00001,40002,,,,,,,,,,,,,,,,,,,,"], 2),
        (None, [
            "Input,test_student1@example.com,bc__student,tester1,test1,00001,40003,,,,,,,,,,,,,,,,,,,,"], 3),
        (None, [
            "Input,test_student1@example.com,abc_student,tester1,test1,00001,40004,,,,,,,,,,,,,,,,,,,,"], 4),
        (None, [
            "Input,test_student1@example.com,xabc__student,tester1,test1,00001,40005,,,,,,,,,,,,,,,,,,,,"], 5),
        (None, [
            "Input,test_student1@example.com,cde__student,tester1,test1,00001,40006,,,,,,,,,,,,,,,,,,,,"], 6),
    )
    @ddt.unpack
    def test_another_org_not_username_rule(self, url_code, students, num):
        # Setup test data
        main_org = self._create_organization(org_name='main_org_rule_name', org_code='main_org_rule_code')
        another_org1 = self._create_organization(org_name='another_org_rule_name', org_code='another_org_rule_code')
        another_org2 = self._create_organization(org_name='not_rule_org_name', org_code='not_rule_org_code')
        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=main_org)
        username_rule2 = OrgUsernameRuleFactory.create(prefix='cde__', org=another_org1)

        group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='group_name', org=another_org2,
            created_by=self.user, modified_by=self.user
        )
        contract = self._create_contract(url_code=url_code, contractor_organization=another_org2)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)
        if num in [3,4,5]:
            success = 1
            fail = 0
        else:
            success = 0
            fail = 1
        # Execute task
        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=success,
            expected_num_failed=fail,
            expected_total=1,
            expected_num_skipped=0
        )
        if num in [3,4,5]:
            self._assert_history_after_execute_task(history.id, 1, None)
        else:
            self._assert_history_after_execute_task(history.id, 1, history)

    def test_username_rule_error_task_message(self):
        # Setup test data
        main_org = self._create_organization(org_name='main_org_rule_name', org_code='main_org_rule_code')
        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=main_org)


        student = ["Input,test_student1@example.com,bc__student_1,tester1,test1,,,,,,,,,,,,,,,,,,,,,,"]
        contract = self._create_contract(url_code=None, contractor_organization=main_org)
        history = self._create_task_history(contract=contract)
        self._create_targets(history, student)

        self._test_run_with_task(
            student_member_register,
            'student_member_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=0,
            expected_num_failed=1,
            expected_total=1,
            expected_num_skipped=0
        )
        task_message = ("Line {line_number}:{message}".format(
            line_number=1,
            message="Username {username} already exists.".format(username='bc__student_1')))
        self.assertEqual(
            task_message,
            StudentMemberRegisterTaskTarget.objects.get(id=1).message
        )

    def test_reflect_condition_execute_call_by_another_task(self):
        """ Note: Detail test is written to 'gx_save_register_condition/tests/test_utils.py'."""
        pass

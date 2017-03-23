"""Tests for student register task"""

import ddt
from mock import patch

from django.contrib.auth.models import User
from django.test.utils import override_settings

from bulk_email.models import Optout
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from biz.djangoapps.ga_contract_operation.models import StudentRegisterTaskTarget
from biz.djangoapps.ga_contract_operation.tasks import student_register
from biz.djangoapps.ga_contract_operation.tests.factories import StudentRegisterTaskTargetFactory
from biz.djangoapps.ga_invitation.models import ContractRegister, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_login.models import BizUser
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.util.tests.testcase import BizViewTestBase
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin
from student.models import CourseEnrollment


@ddt.ddt
class StudentRegisterTaskTest(BizViewTestBase, ModuleStoreTestCase, TaskTestMixin):

    def _create_targets(self, history, students, completed=False):
        for student in students:
            StudentRegisterTaskTargetFactory.create(history=history, student=student, completed=completed)

    def _create_input_entry(self, contract=None, history=None):
        task_input = {}
        if contract is not None:
            task_input['contract_id'] = contract.id
        if history is not None:
            task_input['history_id'] = history.id
        return TaskTestMixin._create_input_entry(self, task_input=task_input)

    def setup_user(self, login_code=None):
        super(StudentRegisterTaskTest, self).setup_user()
        self.login_code = login_code
        if login_code:
            BizUserFactory.create(user=self.user, login_code=login_code)

    @ddt.data(
        (None, ["Input,test_student1@example.com,t,t"]),
        ('contract-url-code', ["Input,test_student1@example.com,t,t,Test_Student_1,TestStudent1"]),
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            "Line 1:" + ' '.join(["Username must be minimum of two characters long", "Your legal name must be a minimum of two characters long"]),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message,
        )

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    @ddt.data('t', 'Test@Student_1', 'Test_Student_1Test_Student_1Test_Student_1')
    def test_register_validation_login_code(self, login_code):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = ["Input,test_student@example.com,test_student_1,tester1,{login_code},TestStudent1".format(login_code=login_code)]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            "Line 1:Invalid login code {login_code}.".format(login_code=login_code),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message,
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
        students = ["Input,test_student@example.com,test_student_1,tester1,Test_Student_1,{password}".format(password=password)]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            "Line 1:Invalid password {password}.".format(password=password),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message,
        )

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    @ddt.data(
        (None, ["Input,test_student@example.com,test_student_1,tester1"]),
        ('contract-url-code', ["Input,test_student@example.com,test_student_1,tester1,Test_Student_1,TestStudent1"]),
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message)

        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(Optout.objects.filter(user=user, course_id=global_course_id).exists())
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=user).login_code)

    @ddt.data(
        (None, ["Input,test_student@example.com,test_student_1,tester1"]),
        ('contract-url-code', ["Input,test_student@example.com,test_student_1,tester1,Test_Student_1,TestStudent1"]),
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message)

        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertTrue(Optout.objects.filter(user=user, course_id=global_course_id).exists())
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=user).login_code)

    @ddt.data(
        (None, ["Input,", "Input,test_student@example.com,test_student_1,tester1", "Register,", "Input,"]),
        ('contract-url-code', ["Input,", "Input,test_student@example.com,test_student_1,tester1,Test_Student_1,TestStudent1", "Register,", "Input,"]),
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=4,
            expected_num_succeeded=1,
            expected_num_skipped=3,
            expected_total=4,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(4, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(4, StudentRegisterTaskTarget.objects.filter(history=history, message__isnull=True).count())

        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=user).login_code)

    @ddt.data(
        (None, [
            "Input,test_student@example.com,test_student_1,tester1",
            "Input,test_student@example.com,test_student_1,tester2",
        ]),
        ('contract-url-code', [
            "Input,test_student@example.com,test_student_1,tester1,Test_Student_1,TestStudent1",
            "Input,test_student@example.com,test_student_1,tester2,Test_Student_1,TestStudent1",
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_succeeded=2,
            expected_total=2,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(2, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(2, StudentRegisterTaskTarget.objects.filter(history=history, message__isnull=True).count())

        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=user).login_code)

    @ddt.data(
        (
            None,
            ["Input,test_student@example.com,test_student_1,tester1,Test_Student_1,TestStudent1", "Input,"],
            "Line 1:Data must have exactly three columns: email, username, and full name."
        ),
        (
            'contract-url-code',
            ["Input,test_student@example.com,test_student_1,tester1", "Input,"],
            "Line 1:Data must have exactly five columns: email, username, full name, login code and password."
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_failed=1,
            expected_num_skipped=1,
            expected_total=2,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(2, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            message,
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message)

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    @ddt.data(
        (None, ["Input,test_student.example.com,test_student_1,tester1"]),
        ('contract-url-code', ["Input,test_student.example.com,test_student_1,tester1,Test_Student_1,TestStudent1"]),
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            "Line 1:Invalid email test_student.example.com.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    @ddt.data(
        (None, ["Input,{email},test_student_1,tester1"]),
        ('contract-url-code', ["Input,{email},test_student_1,tester1,Test_Student_1,TestStudent1"]),
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIn(
            "Warning, an account with email {email} exists but the registered username {username} is different.".format(email=self.email, username=self.username),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        if url_code:
            self.assertIn(
                "Warning, an account with email {email} exists but the registered password is different.".format(email=self.email),
                StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
            )

        self.assertEqual(ContractRegister.objects.get(user__email=self.email, contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(Optout.objects.filter(user=self.user, course_id=global_course_id).exists())
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=self.user).login_code)

    @ddt.data(
        (None, ["Input,{email},test_student_1,tester1"]),
        ('contract-url-code', ["Input,{email},test_student_1,tester1,Test_Student_1,TestStudent1"]),
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIn(
            "Warning, an account with email {email} exists but the registered username {username} is different.".format(email=self.email, username=self.username),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        if url_code:
            self.assertIn(
                "Warning, an account with email {email} exists but the registered password is different.".format(email=self.email),
                StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
            )

        self.assertEqual(ContractRegister.objects.get(user__email=self.email, contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(Optout.objects.filter(user=self.user, course_id=global_course_id).exists())
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=self.user).login_code)

    @ddt.data(
        (None, ["Input,{email},test_student_1,tester1"]),
        ('contract-url-code', ["Input,{email},test_student_1,tester1,Test_Student_1,TestStudent1"]),
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIn(
            "Warning, an account with email {email} exists but the registered username {username} is different.".format(email=self.email, username=self.username),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        if url_code:
            self.assertIn(
                "Warning, an account with email {email} exists but the registered password is different.".format(email=self.email),
                StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
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
        students = ["Input,{email},{username},username,{login_code},{password}".format(
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())

        self.assertEqual(self.login_code, BizUser.objects.get(user=self.user).login_code)

    def test_register_user_with_already_existing_diff_login_code(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user('Test_Student_1')
        students = ["Input,{email},{username},username,{login_code},{password}".format(
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())

        self.assertIn(
            "Warning, an account with email {email} exists but the registered login code {login_code} is different.".format(email=self.email, login_code=self.login_code),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertEqual(self.login_code, BizUser.objects.get(user=self.user).login_code)

    def test_register_user_with_already_existing_diff_password(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user('Test_Student_1')
        students = ["Input,{email},{username},username,{login_code},{password}".format(
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())

        self.assertIn(
            "Warning, an account with email {email} exists but the registered password is different.".format(email=self.email),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertEqual(self.login_code, BizUser.objects.get(user=self.user).login_code)

    def test_register_user_with_already_existing_diff_login_code_password(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user('Test_Student_1')
        students = ["Input,{email},{username},username,{login_code},{password}".format(
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())

        self.assertIn(
            "Warning, an account with email {email} exists but the registered login code {login_code} is different.".format(email=self.email, login_code=self.login_code),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        self.assertIn(
            "Warning, an account with email {email} exists but the registered password is different.".format(email=self.email),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertEqual(self.login_code, BizUser.objects.get(user=self.user).login_code)

    def test_register_user_same_login_code(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user('Test_Student_1')
        students = [
            "Input,test_student1@example.com,test_student_1,tester1,Test_Student_1,TestStudent1",
            "Input,{email},{username},tester2,Test_Student_1,{password}".format(email=self.email, username=self.username, password=self.password),
        ]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_succeeded=1,
            expected_num_failed=1,
            expected_total=2,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(2, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())

        self.assertEqual(
            "Line 2:Login code Test_Student_1 already exists.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

        self.assertEqual(2, BizUser.objects.filter(login_code=self.login_code).count())
        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email=self.email, contract=contract).exists())

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1",
            "Input,test_student2@example.com,test_student_1,tester2",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,Test_Student_1,TestStudent1",
            "Input,test_student2@example.com,test_student_1,tester2,Test_Student_2,TestStudent2",
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_succeeded=1,
            expected_num_failed=1,
            expected_total=2,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(2, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message)
        self.assertEqual(
            "Line 2:Username test_student_1 already exists.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())

    def test_register_user_with_already_existing_login_code(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students =  [
            "Input,test_student1@example.com,test_student_1,tester1,Test_Student_1,TestStudent1",
            "Input,test_student2@example.com,test_student_2,tester2,Test_Student_1,TestStudent2",
        ]

        contract = self._create_contract(url_code='contract-url-code')
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=2,
            expected_num_succeeded=1,
            expected_num_failed=1,
            expected_total=2,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(2, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message)
        self.assertEqual(
            "Line 2:Login code Test_Student_1 already exists.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1",
            "Input,test_student2@example.com,test_student_1,tester2",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,Test_Student_1,TestStudent1",
            "Input,test_student2@example.com,test_student_1,tester2,Test_Student_2,TestStudent2",
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
        with patch('biz.djangoapps.ga_contract_operation.student_register.validate_email', side_effect=[None, Exception]):
            self._test_run_with_task(
                student_register,
                'student_register',
                task_entry=self._create_input_entry(contract=contract, history=history),
                expected_attempted=2,
                expected_num_succeeded=1,
                expected_num_failed=1,
                expected_total=2,
            )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message)
        self.assertEqual(
            "Line 2:Failed to register. Please operation again after a time delay.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())

    @ddt.data(
        (None, [
            "Input,test_student1@example.com,test_student_1,tester1",
            "Input,test_student3@example.com,test_student_1,tester3",
            "Input,test_student2@example.com,test_student_2,tester2",
        ]),
        ('contract-url-code', [
            "Input,test_student1@example.com,test_student_1,tester1,Test_Student_1,TestStudent1",
            "Input,test_student3@example.com,test_student_1,tester3,Test_Student_3,TestStudent3",
            "Input,test_student2@example.com,test_student_2,tester2,Test_Student_2,TestStudent2",
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=3,
            expected_num_succeeded=2,
            expected_num_failed=1,
            expected_total=3,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(3, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message)
        self.assertEqual(
            "Line 2:Username test_student_1 already exists.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[2]).message)

        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student2@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=contract).exists())

    @patch('biz.djangoapps.ga_contract_operation.student_register.log.error')
    @ddt.data(
        (None, [
            "Register,test_student1@example.com,test_student_1,tester1",
            "Unregister,test_student3@example.com,test_student_3,tester3",
            "Register,test_student2@example.com,test_student_2,tester2",
        ]),
        ('contract-url-code', [
            "Register,test_student1@example.com,test_student_1,tester1,Test_Student_1,TestStudent1",
            "Unregister,test_student3@example.com,test_student_3,tester3,Test_Student_3,TestStudent3",
            "Register,test_student2@example.com,test_student_2,tester2,Test_Student_2,TestStudent2",
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=3,
            expected_num_succeeded=2,
            expected_num_failed=1,
            expected_total=3,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(3, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message)
        error_log.assert_any_call('Invalid status: Unregister.')
        self.assertEqual(
            "Line 2:Failed to register. Please operation again after a time delay.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[2]).message)

        self.assertEqual(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, REGISTER_INVITATION_CODE)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student2@example.com', contract=contract).status, REGISTER_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=contract).exists())

        self.assertTrue(CourseEnrollment.objects.get(user__email='test_student1@example.com', course_id=course.id).is_active)
        self.assertTrue(CourseEnrollment.objects.get(user__email='test_student2@example.com', course_id=course.id).is_active)
        self.assertFalse(CourseEnrollment.objects.filter(user__email='test_student3@example.com', course_id=course.id).exists())

    @ddt.data(
        (None, [
            "Input,test_student1test_student1test_student1test_student1test_student@example.com,test_student_1,tester1",
            "Input,test_student3@example.com,test_student_1test_student_1test_stu,tester3",
            "Input,test_student2@example.com,test_student_2,tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2test",
        ]),
        ('contract-url-code', [
            "Input,test_student1test_student1test_student1test_student1test_student@example.com,test_student_1,tester1,Test_Student_1,TestStudent1",
            "Input,test_student3@example.com,test_student_1test_student_1test_stu,tester3,Test_Student_3,TestStudent3",
            "Input,test_student2@example.com,test_student_2,tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2test,Test_Student_2,TestStudent2",
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=3,
            expected_num_failed=3,
            expected_total=3,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(3, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(
            "Line 1:Email cannot be more than 75 characters long",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        self.assertEqual(
            "Line 2:Username cannot be more than 30 characters long",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )
        self.assertEqual(
            "Line 3:Name cannot be more than 255 characters long",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[2]).message
        )

        self.assertFalse(ContractRegister.objects.filter(user__email='test_student1@example.com', contract=contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=contract).exists())

    @ddt.data(
        (None, None, [
            "Input,test_student@example.com,test_student_1,tester1",
        ], 1),
        ("contract-url-code", True, [
            "Input,test_student@example.com,test_student_1,tester1,Test_Student_1,TestStudent1",
        ], 1),
        ("contract-url-code", False, [
            "Input,test_student@example.com,test_student_1,tester1,Test_Student_1,TestStudent1",
        ], 0),
    )
    @ddt.unpack
    @patch('biz.djangoapps.ga_contract_operation.student_register.send_mail_to_student')
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
            student_register,
            'student_register',
            task_entry=self._create_input_entry(contract=contract, history=history),
            expected_attempted=1,
            expected_num_succeeded=1,
            expected_total=1,
        )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        self.assertEqual(0, StudentRegisterTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, StudentRegisterTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message)

        user = User.objects.get(email='test_student@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        if url_code:
            self.assertEqual('Test_Student_1', BizUser.objects.get(user=user).login_code)
        self.assertEqual(send_mail_call_count, send_mail_to_student.call_count)

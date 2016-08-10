"""Tests for task"""

from datetime import timedelta
import json
from mock import patch

from social.apps.django_app.default.models import UserSocialAuth
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from bulk_email.models import Optout
from certificates.models import GeneratedCertificate
from certificates.tests.factories import GeneratedCertificateFactory
from student.models import CourseEnrollmentAllowed, ManualEnrollmentAudit, PendingEmailChange
from student.tests.factories import (
    CourseEnrollmentFactory, CourseEnrollmentAllowedFactory, PendingEmailChangeFactory, UserFactory
)
from third_party_auth.tests.testutil import ThirdPartyAuthTestMixin
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from biz.djangoapps.ga_contract.models import CONTRACT_TYPE_PF, CONTRACT_TYPE_GACCO_SERVICE
from biz.djangoapps.ga_contract.tests.factories import AdditionalInfoFactory, ContractFactory, ContractDetailFactory
from biz.djangoapps.ga_contract_operation.models import ContractTaskTarget, StudentRegisterTaskTarget
from biz.djangoapps.ga_contract_operation.personalinfo import _hash
from biz.djangoapps.ga_contract_operation.tasks import personalinfo_mask, student_register
from biz.djangoapps.ga_contract_operation.tests.factories import ContractTaskTargetFactory, StudentRegisterTaskTargetFactory
from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting, ContractRegister, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import AdditionalInfoSettingFactory, ContractRegisterFactory
from biz.djangoapps.util.datetime_utils import timezone_today
from biz.djangoapps.util.tests.testcase import BizTestBase, BizViewTestBase
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin


class PersonalinfoMaskTaskTest(BizTestBase, ModuleStoreTestCase, ThirdPartyAuthTestMixin, TaskTestMixin):

    random_value = ''

    def _setup_courses(self):
        # Setup courses. Some tests does not need course data. Therefore, call this function if need course data.
        self.spoc_courses = [
            CourseFactory.create(org='spoc', course='course1', run='run'),
            CourseFactory.create(org='spoc', course='course2', run='run'),
        ]
        self.other_enabled_spoc_courses = [
            CourseFactory.create(org='other_spoc', course='course1', run='run'),
            CourseFactory.create(org='other_spoc', course='course2', run='run'),
        ]
        self.other_not_enabled_spoc_courses = [
            CourseFactory.create(org='other_not_spoc', course='course1', run='run'),
            CourseFactory.create(org='other_not_spoc', course='course2', run='run'),
        ]
        self.global_courses = [
            CourseFactory.create(org='global', course='course1', run='run'),
            CourseFactory.create(org='global', course='course2', run='run'),
        ]
        for course in self.global_courses:
            CourseGlobalSettingFactory.create(course_id=course.id)
        self.mooc_courses = [
            CourseFactory.create(org='mooc', course='course1', run='run'),
            CourseFactory.create(org='mooc', course='course2', run='run'),
        ]

    @classmethod
    def _configure_dummy_provider(cls, **kwargs):
        kwargs.setdefault("name", "Dummy")
        kwargs.setdefault("backend_name", "dummy")
        kwargs.setdefault("key", "testkey")
        kwargs.setdefault("secret", "testsecret")
        return cls.configure_oauth_provider(**kwargs)

    def _create_input_entry(self, contract=None, history=None):
        task_input = {}
        if contract is not None:
            task_input['contract_id'] = contract.id
        if history is not None:
            task_input['history_id'] = history.id
        return TaskTestMixin._create_input_entry(self, task_input=task_input)

    def _create_contract(self, contract_type=CONTRACT_TYPE_PF[0], courses=[], display_names=[], enabled=True):
        if enabled:
            start_date = timezone_today() - timedelta(days=1)
        else:
            start_date = timezone_today() + timedelta(days=1)

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

    def _create_user_and_register(self, contract, status=INPUT_INVITATION_CODE, display_names=[], email=None):
        if email is not None:
            user = UserFactory.create(email=email)
        else:
            user = UserFactory.create()
        user.profile.set_meta({'old_emails': [[user.email, '2016-01-01T00:00:00.000000+00:00']]})
        user.profile.save()
        if hasattr(self, 'global_courses'):
            for course in self.global_courses:
                CourseEnrollmentAllowedFactory.create(email=user.email, course_id=course.id)
                enrollment = CourseEnrollmentFactory.create(user=user, course_id=course.id)
                ManualEnrollmentAudit.create_manual_enrollment_audit(
                    user, user.email, "test enrollment", "test reason", enrollment
                )
        PendingEmailChangeFactory.create(user=user, activation_key=user.id)
        # create thirt_party_auth
        UserSocialAuth.objects.create(user=user, provider='dummy', uid=user.email)
        register = ContractRegisterFactory.create(user=user, contract=contract, status=status)
        for display_name in display_names:
            AdditionalInfoSettingFactory.create(
                user=user, contract=contract, display_name=display_name, value='value_of_{}'.format(display_name)
            )
        return register

    def _create_enrollments(self, registers, courses):
        for course in courses:
            for register in registers:
                user = register.user
                CourseEnrollmentFactory.create(user=user, course_id=course.id)
                GeneratedCertificateFactory.create(user=user, course_id=course.id, name=user.profile.name)

    def _create_targets(self, history, registers, completed=False):
        for register in registers:
            ContractTaskTargetFactory.create(history=history, register=register, completed=completed)

    def _create_user_info(self, user):
        return {
            'email': user.email,
            'name': user.profile.name,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }

    def _assert_user_info(self, user_info, user, masked=True):
        _email, _name = (user_info[user.id]['email'], user_info[user.id]['name'])
        expected_email = _hash(_email + self.random_value) if masked else _email
        expected_name = _hash(_name) if masked else _name
        expected_first_name = '' if masked else user_info[user.id]['first_name']
        expected_last_name = '' if masked else user_info[user.id]['last_name']

        # re-acquire the data
        user = User.objects.get(pk=user.id)
        self.assertEqual(expected_email, user.email)
        self.assertEqual(expected_name, user.profile.name)
        self.assertEqual(expected_first_name, user.first_name)
        self.assertEqual(expected_last_name, user.last_name)
        if masked:
            self.assertEqual('', user.profile.meta)
        else:
            self.assertIn(user.email, user.profile.meta)
        for pec in PendingEmailChange.objects.filter(user_id=user.id):
            if masked:
                self.assertEqual(expected_email, pec.new_email)
            else:
                self.assertNotEqual(expected_email, pec.new_email)
        if masked:
            self.assertFalse(UserSocialAuth.objects.filter(user_id=user.id).exists())
        else:
            self.assertTrue(UserSocialAuth.objects.filter(user_id=user.id).exists())

    def _assert_cert_info(self, user_info, user, courses, masked=True):
        _name = user_info[user.id]['name']
        expected_name = _hash(_name) if masked else _name

        for course in courses:
            cert = GeneratedCertificate.objects.get(user_id=user.id, course_id=course.id)
            self.assertEqual(expected_name, cert.name)

    def _assert_global_courses(self, user_info, user, courses, masked=True):
        _email = user_info[user.id]['email']
        expected_email = _hash(_email + self.random_value) if masked else _email

        for course in courses:
            self.assertTrue(
                CourseEnrollmentAllowed.objects.filter(email=expected_email, course_id=course.id).exists()
            )
            manual_enrollment_autit = ManualEnrollmentAudit.objects.get(
                enrollment__user=user, enrollment__course_id=course.id
            )
            self.assertEqual(expected_email, manual_enrollment_autit.enrolled_email)
            optout = Optout.objects.filter(user=user, course_id=course.id)
            if masked:
                self.assertTrue(optout.filter(force_disabled=True).exists())
            else:
                self.assertFalse(optout.exists())

    def _assert_additional_info(self, user, contract, display_names, masked=True):
        additional_infos = AdditionalInfoSetting.find_by_user_and_contract(user, contract)
        self.assertEqual(len(additional_infos), len(display_names))

        for display_name in display_names:
            expected_value = 'value_of_{}'.format(display_name)
            if masked:
                expected_value = _hash(expected_value)
            self.assertEqual(expected_value, AdditionalInfoSetting.get_value_by_display_name(user, contract, display_name))

    def test_missing_current_task(self):
        self._test_missing_current_task(personalinfo_mask)

    def test_run_with_failure(self):
        contract = self._create_contract()
        history = self._create_task_history(contract)
        entry = self._create_input_entry(contract=contract, history=history)
        self._test_run_with_failure(personalinfo_mask, 'We expected this to fail', entry)

    def test_run_with_long_error_msg(self):
        contract = self._create_contract()
        history = self._create_task_history(contract)
        entry = self._create_input_entry(contract=contract, history=history)
        self._test_run_with_long_error_msg(personalinfo_mask, entry)

    def test_run_with_short_error_msg(self):
        contract = self._create_contract()
        history = self._create_task_history(contract)
        entry = self._create_input_entry(contract=contract, history=history)
        self._test_run_with_short_error_msg(personalinfo_mask, entry)

    def test_missing_required_input_history(self):
        entry = self._create_input_entry(contract=self._create_contract())

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(personalinfo_mask, entry.id, entry.task_id)

        self.assertEqual("Task {}: Missing required value {}".format(entry.task_id, json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_missing_required_input_contract(self):
        entry = self._create_input_entry(history=self._create_task_history(self._create_contract()))

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(personalinfo_mask, entry.id, entry.task_id)

        self.assertEqual("Task {}: Missing required value {}".format(entry.task_id, json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_history_does_not_exists(self):
        contract = self._create_contract()
        history = self._create_task_history(contract)
        entry = self._create_input_entry(contract=contract, history=history)
        history.delete()

        with self.assertRaises(ObjectDoesNotExist):
            self._run_task_with_mock_celery(personalinfo_mask, entry.id, entry.task_id)

        self._assert_task_failure(entry.id)

    def test_conflict_contract(self):
        contract = self._create_contract()
        # Create history with other contract
        history = self._create_task_history(self._create_contract())
        entry = self._create_input_entry(contract=contract, history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(personalinfo_mask, entry.id, entry.task_id)

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
        self._create_targets(history, registers)
        self._create_enrollments(registers, self.spoc_courses)
        # This is `NOT` the target contract
        other_contract = self._create_contract(courses=self.other_enabled_spoc_courses, display_names=display_names)
        other_registers = [self._create_user_and_register(other_contract, display_names=display_names) for _ in range(5)]
        self._create_contract(courses=self.other_not_enabled_spoc_courses, display_names=display_names, enabled=False)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers + other_registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self.random_value = 'test1'
        with patch('biz.djangoapps.ga_contract_operation.personalinfo.get_random_string', return_value=self.random_value):
            self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 5, 0, 0, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for register in registers:
            self._assert_additional_info(register.user, contract, display_names)
            self._assert_user_info(user_info, register.user)
            self._assert_cert_info(user_info, register.user, self.spoc_courses)
            self._assert_global_courses(user_info, register.user, self.global_courses)
        for register in other_registers:
            self._assert_additional_info(register.user, other_contract, display_names, masked=False)
            self._assert_user_info(user_info, register.user, masked=False)
            self._assert_global_courses(user_info, register.user, self.global_courses, masked=False)
        # Assert all of target is completed
        self.assertEqual(5, ContractTaskTarget.objects.filter(history=history, completed=True).count())

    def test_successful_reuse_email(self):
        """
        Scenario:
            1. Create userA
            2. Execute mask to userA
            3. Create userB with same email addrses as userA
            4. Excute mask to userB
        """
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
        self._create_targets(history, registers)
        self._create_enrollments(registers, self.spoc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self.random_value = 'test1'
        with patch('biz.djangoapps.ga_contract_operation.personalinfo.get_random_string', return_value=self.random_value):
            self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 5, 0, 0, 5, 5, entry)
        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for register in registers:
            self._assert_additional_info(register.user, contract, display_names)
            self._assert_user_info(user_info, register.user)
            self._assert_cert_info(user_info, register.user, self.spoc_courses)
            self._assert_global_courses(user_info, register.user, self.global_courses)
        # Assert all of target is completed
        self.assertEqual(5, ContractTaskTarget.objects.filter(history=history, completed=True).count())

        # ----------------------------------------------------------
        # Setup test data for 2nd
        # ----------------------------------------------------------
        history = self._create_task_history(contract=contract)
        # users: enrolled only target spoc courses
        # Use email of 1st users
        _user_info_of_1st = user_info.values()
        registers = [
            self._create_user_and_register(contract, display_names=display_names, email=_user_info_of_1st[i]['email'])
            for i in range(5)
        ]
        self._create_targets(history, registers)
        self._create_enrollments(registers, self.spoc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers}

        # ----------------------------------------------------------
        # Execute task for 2nd
        # ----------------------------------------------------------
        self.random_value = 'test2'
        with patch('biz.djangoapps.ga_contract_operation.personalinfo.get_random_string', return_value=self.random_value):
            self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 5, 0, 0, 5, 5, entry)
        # ----------------------------------------------------------
        # Assertion for 2nd
        # ----------------------------------------------------------
        for register in registers:
            self._assert_additional_info(register.user, contract, display_names)
            self._assert_user_info(user_info, register.user)
            self._assert_cert_info(user_info, register.user, self.spoc_courses)
            self._assert_global_courses(user_info, register.user, self.global_courses)
        # Assert all of target is completed
        self.assertEqual(5, ContractTaskTarget.objects.filter(history=history, completed=True).count())

    def test_successful_with_gacco_service(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self._setup_courses()
        display_names = ['settting1', 'setting2', ]
        contract = self._create_contract(
            contract_type=CONTRACT_TYPE_GACCO_SERVICE[0],
            courses=self.mooc_courses,
            display_names=display_names
        )
        history = self._create_task_history(contract)
        # users: enrolled only target mooc courses
        registers = [self._create_user_and_register(contract, display_names=display_names) for _ in range(5)]
        # 3 target is not completed
        self._create_targets(history, registers[:3])
        # 2 target is completed
        self._create_targets(history, registers[3:], completed=True)
        self._create_enrollments(registers, self.mooc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self.random_value = 'test1'
        with patch('biz.djangoapps.ga_contract_operation.personalinfo.get_random_string', return_value=self.random_value):
            self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 3, 2, 0, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for i, register in enumerate(registers):
            masked = i < 3
            if masked:
                self._assert_additional_info(register.user, contract, display_names, masked=True)
            else:
                self._assert_additional_info(register.user, contract, display_names, masked=False)
            self._assert_user_info(user_info, register.user, masked=False)
            self._assert_cert_info(user_info, register.user, self.mooc_courses, masked=False)
            self._assert_global_courses(user_info, register.user, self.global_courses, masked=False)
        # Assert all of target is completed
        self.assertEqual(5, ContractTaskTarget.objects.filter(history=history, completed=True).count())

    def test_successful_with_completed_target(self):
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
        # 3 target is not completed
        self._create_targets(history, registers[:3])
        # 2 target is completed
        self._create_targets(history, registers[3:], completed=True)
        self._create_enrollments(registers, self.spoc_courses)
        # This is `NOT` the target contract
        other_contract = self._create_contract(courses=self.other_enabled_spoc_courses, display_names=display_names)
        other_registers = [self._create_user_and_register(other_contract, display_names=display_names) for _ in range(5)]
        self._create_contract(courses=self.other_not_enabled_spoc_courses, display_names=display_names, enabled=False)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers + other_registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self.random_value = 'test1'
        with patch('biz.djangoapps.ga_contract_operation.personalinfo.get_random_string', return_value=self.random_value):
            self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 3, 2, 0, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for i, register in enumerate(registers):
            masked = i < 3
            self._assert_additional_info(register.user, contract, display_names, masked=masked)
            self._assert_user_info(user_info, register.user, masked=masked)
            self._assert_cert_info(user_info, register.user, self.spoc_courses, masked=masked)
            self._assert_global_courses(user_info, register.user, self.global_courses, masked=masked)
        for register in other_registers:
            self._assert_additional_info(register.user, other_contract, display_names, masked=False)
            self._assert_user_info(user_info, register.user, masked=False)
            self._assert_global_courses(user_info, register.user, self.global_courses, masked=False)
        # Assert all of target is completed
        self.assertEqual(5, ContractTaskTarget.objects.filter(history=history, completed=True).count())

    def test_successful_with_other_course(self):
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
        self._create_targets(history, registers)
        self._create_enrollments(registers, self.spoc_courses)
        # This is `NOT` the target contract
        self._create_contract(courses=self.other_enabled_spoc_courses, display_names=display_names)
        self._create_contract(courses=self.other_not_enabled_spoc_courses, display_names=display_names, enabled=False)

        # user4: enroll other courses of enabled contract
        self._create_enrollments([registers[4]], self.other_enabled_spoc_courses)
        # user3: enroll other course of not enabled contract
        self._create_enrollments([registers[3]], self.other_not_enabled_spoc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self.random_value = 'test1'
        with patch('biz.djangoapps.ga_contract_operation.personalinfo.get_random_string', return_value=self.random_value):
            self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 4, 1, 0, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for register in registers[:4]:
            self._assert_additional_info(register.user, contract, display_names)
            self._assert_user_info(user_info, register.user)
            self._assert_cert_info(user_info, register.user, self.spoc_courses)
            self._assert_global_courses(user_info, register.user, self.global_courses)
        # additional info should be masked
        self._assert_additional_info(registers[4].user, contract, display_names)
        # user info should not be masked
        self._assert_user_info(user_info, registers[4].user, masked=False)
        self._assert_cert_info(user_info, registers[4].user, self.spoc_courses, masked=False)
        self._assert_global_courses(user_info, registers[4].user, self.global_courses, masked=False)
        # Assert 4 target is completed, and 1 target is not completed
        for target in ContractTaskTarget.objects.filter(history=history):
            if target.register_id == registers[4].id:
                self.assertFalse(target.completed)
            else:
                self.assertTrue(target.completed)

    def test_successful_with_mooc_course(self):
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
        self._create_targets(history, registers)
        self._create_enrollments(registers, self.spoc_courses)
        # This is `NOT` the target contract
        self._create_contract(courses=self.other_enabled_spoc_courses, display_names=display_names)
        self._create_contract(courses=self.other_not_enabled_spoc_courses, display_names=display_names, enabled=False)

        # user4: enroll mooc courses
        self._create_enrollments([registers[4]], self.mooc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self.random_value = 'test1'
        with patch('biz.djangoapps.ga_contract_operation.personalinfo.get_random_string', return_value=self.random_value):
            self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 4, 1, 0, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for register in registers[:4]:
            self._assert_additional_info(register.user, contract, display_names)
            self._assert_user_info(user_info, register.user)
            self._assert_cert_info(user_info, register.user, self.spoc_courses)
            self._assert_global_courses(user_info, register.user, self.global_courses)
        # additional info should be masked
        self._assert_additional_info(registers[4].user, contract, display_names)
        # user info should not be masked
        self._assert_user_info(user_info, registers[4].user, masked=False)
        self._assert_cert_info(user_info, registers[4].user, self.spoc_courses, masked=False)
        self._assert_global_courses(user_info, registers[4].user, self.global_courses, masked=False)
        # Assert 4 target is completed, and 1 target is not completed
        for target in ContractTaskTarget.objects.filter(history=history):
            if target.register_id == registers[4].id:
                self.assertFalse(target.completed)
            else:
                self.assertTrue(target.completed)

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
        self._create_targets(history, registers)
        self._create_enrollments(registers, self.spoc_courses)
        # This is `NOT` the target contract
        other_contract = self._create_contract(courses=self.other_enabled_spoc_courses, display_names=display_names)
        other_registers = [self._create_user_and_register(other_contract, display_names=display_names) for _ in range(5)]
        self._create_contract(courses=self.other_not_enabled_spoc_courses, display_names=display_names, enabled=False)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers + other_registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self.random_value = 'test1'
        with patch(
            'biz.djangoapps.ga_contract_operation.personalinfo._PersonalinfoMaskExecutor.check_enrollment'
        ) as mock_check_enrollment, patch(
            'biz.djangoapps.ga_contract_operation.personalinfo.get_random_string', return_value=self.random_value
        ):
            # raise Exception at last call
            mock_check_enrollment.side_effect = [True, True, True, True, Exception]
            self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 4, 0, 1, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for i, register in enumerate(registers):
            masked = i != 4
            self._assert_additional_info(register.user, contract, display_names, masked=masked)
            self._assert_user_info(user_info, register.user, masked=masked)
            self._assert_cert_info(user_info, register.user, self.spoc_courses, masked=masked)
            self._assert_global_courses(user_info, register.user, self.global_courses, masked=masked)
        for register in other_registers:
            self._assert_additional_info(register.user, other_contract, display_names, masked=False)
            self._assert_user_info(user_info, register.user, masked=False)
            self._assert_global_courses(user_info, register.user, self.global_courses, masked=False)
        # Assert 4 target is completed
        self.assertEqual(4, ContractTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertFalse(ContractTaskTarget.objects.get(history=history, register=registers[4]).completed)


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

    def test_register_validation(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = ["test_student1@example.com,t,t"]

        contract = self._create_contract()
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
            ' '.join(['Username must be minimum of two characters long', 'Your legal name must be a minimum of two characters long']),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message,
        )

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    def test_register_account_creation(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = ["test_student@example.com,test_student_1,tester1"]

        contract = self._create_contract()
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

        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)
        self.assertEquals(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)

    def test_register_account_creation_with_blank_lines(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = ["", "test_student@example.com,test_student_1,tester1", "", ""]

        contract = self._create_contract()
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

        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)
        self.assertEquals(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)

    def test_register_email_and_username_already_exist(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = ["test_student@example.com,test_student_1,tester1", "test_student@example.com,test_student_1,tester2"]

        contract = self._create_contract()
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

        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)
        self.assertEquals(ContractRegister.objects.get(user__email='test_student@example.com', contract=contract).status, INPUT_INVITATION_CODE)

    def test_register_insufficient_data(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = ["test_student@example.com,test_student_1", ""]

        contract = self._create_contract()
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
            "Data must have exactly three columns: email, username, and full name.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message)

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    def test_register_invalid_email(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = ["test_student.example.com,test_student_1,tester1"]

        contract = self._create_contract()
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
            "Invalid email test_student.example.com.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertFalse(ContractRegister.objects.filter(contract=contract).exists())

    def test_register_user_with_already_existing_email(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user()
        students = ["{email},test_student_1,tester1".format(email=self.email)]

        contract = self._create_contract()
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
        self.assertEqual(
            "Warning, an account with email {email} exists but the registered username {username} is different.".format(email=self.email, username=self.username),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=contract).status, INPUT_INVITATION_CODE)

    def test_register_user_with_already_existing_contract_register_input(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user()
        students = ["{email},test_student_1,tester1".format(email=self.email)]

        contract = self._create_contract()
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
        self.assertEqual(
            "Warning, an account with email {email} exists but the registered username {username} is different.".format(email=self.email, username=self.username),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=contract).status, INPUT_INVITATION_CODE)

    def test_register_user_with_already_existing_contract_register_register(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self.setup_user()
        students = ["{email},test_student_1,tester1".format(email=self.email)]

        contract = self._create_contract()
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
        self.assertEqual(
            "Warning, an account with email {email} exists but the registered username {username} is different.".format(email=self.email, username=self.username),
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )

        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=contract).status, REGISTER_INVITATION_CODE)

    def test_register_user_with_already_existing_username(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = [
            "test_student1@example.com,test_student_1,tester1",
            "test_student2@example.com,test_student_1,tester2",
        ]

        contract = self._create_contract()
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
            "Username test_student_1 already exists.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

        self.assertEquals(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())

    def test_register_raising_exception_in_auto_registration_case(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = [
            "test_student1@example.com,test_student_1,tester1",
            "test_student2@example.com,test_student_2,tester2",
        ]

        contract = self._create_contract()
        history = self._create_task_history(contract=contract)
        self._create_targets(history, students)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        with patch('biz.djangoapps.ga_contract_operation.student_register.generate_unique_password', side_effect=['hoge', Exception]):
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
            "Failed to register. Please operation again after a time delay.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )

        self.assertEquals(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())

    def test_register_users_created_successfully_if_others_fail(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = [
            "test_student1@example.com,test_student_1,tester1",
            "test_student3@example.com,test_student_1,tester3",
            "test_student2@example.com,test_student_2,tester2",
        ]

        contract = self._create_contract()
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
            "Username test_student_1 already exists.",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )
        self.assertIsNone(StudentRegisterTaskTarget.objects.get(history=history, student=students[2]).message)

        self.assertEquals(ContractRegister.objects.get(user__email='test_student1@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertEquals(ContractRegister.objects.get(user__email='test_student2@example.com', contract=contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=contract).exists())

    def test_register_over_max_char_length(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        students = [
            "test_student1test_student1test_student1test_student1test_student@example.com,test_student_1,tester1",
            "test_student3@example.com,test_student_1test_student_1test_stu,tester3",
            "test_student2@example.com,test_student_2,tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2tester2test",
        ]

        contract = self._create_contract()
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
            "Email cannot be more than 75 characters long",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[0]).message
        )
        self.assertEqual(
            "Username cannot be more than 30 characters long",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[1]).message
        )
        self.assertEqual(
            "Name cannot be more than 255 characters long",
            StudentRegisterTaskTarget.objects.get(history=history, student=students[2]).message
        )

        self.assertFalse(ContractRegister.objects.filter(user__email='test_student1@example.com', contract=contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=contract).exists())

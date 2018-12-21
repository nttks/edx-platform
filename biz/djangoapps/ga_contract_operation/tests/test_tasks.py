"""Tests for task"""

import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from mock import patch
from social.apps.django_app.default.models import UserSocialAuth
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from biz.djangoapps.ga_contract.models import CONTRACT_TYPE_PF, CONTRACT_TYPE_GACCO_SERVICE
from biz.djangoapps.ga_contract.tests.factories import AdditionalInfoFactory, ContractFactory, ContractDetailFactory
from biz.djangoapps.ga_contract_operation.models import ContractTaskTarget
from biz.djangoapps.ga_contract_operation.tasks import personalinfo_mask
from biz.djangoapps.ga_contract_operation.tests.factories import ContractTaskTargetFactory
from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting, INPUT_INVITATION_CODE, \
    UNREGISTER_INVITATION_CODE, ContractRegister
from biz.djangoapps.ga_invitation.tests.factories import AdditionalInfoSettingFactory, ContractRegisterFactory
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.util import mask_utils
from biz.djangoapps.util.datetime_utils import timezone_today
from biz.djangoapps.util.tests.testcase import BizTestBase
from bulk_email.models import Optout
from certificates.models import CertificateStatuses, GeneratedCertificate
from certificates.tests.factories import GeneratedCertificateFactory
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin
from student.models import CourseEnrollmentAllowed, ManualEnrollmentAudit, PendingEmailChange, CourseEnrollment
from student.tests.factories import (
    CourseEnrollmentFactory, CourseEnrollmentAllowedFactory, PendingEmailChangeFactory, UserFactory
)
from third_party_auth.tests.testutil import ThirdPartyAuthTestMixin


class StudentsTaskTestMixin(TaskTestMixin):
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

    def _create_user_and_register(self, contract, status=INPUT_INVITATION_CODE, display_names=[], email=None, login_code=None):
        if email is not None:
            user = UserFactory.create(email=email)
        else:
            user = UserFactory.create()
        user.profile.set_meta({'old_emails': [[user.email, '2016-01-01T00:00:00.000000+00:00']]})
        user.profile.save()
        if login_code is not None:
            BizUserFactory.create(user=user, login_code=login_code)
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
                GeneratedCertificateFactory.create(
                    user=user, course_id=course.id, name=user.profile.name,
                    status=CertificateStatuses.downloadable, key='key', download_url='http://dummy'
                )


class PersonalinfoMaskTaskTest(BizTestBase, ModuleStoreTestCase, ThirdPartyAuthTestMixin, StudentsTaskTestMixin):
    def setUp(self):
        super(PersonalinfoMaskTaskTest, self).setUp()

        self.random_value = 'test1'

        patcher1 = patch('biz.djangoapps.util.mask_utils.get_random_string')
        self.mock_get_random_string = patcher1.start()
        self.mock_get_random_string.return_value = self.random_value
        self.addCleanup(patcher1.stop)

        patcher2 = patch('pdfgen.certificate.delete_cert_pdf')
        self.mock_delete_cert_pdf = patcher2.start()
        self.mock_delete_cert_pdf.return_value = '{}'
        self.addCleanup(patcher2.stop)

        patcher3 = patch('biz.djangoapps.ga_contract_operation.personalinfo.log')
        self.mock_log = patcher3.start()
        self.addCleanup(patcher3.stop)

        patcher4 = patch('biz.djangoapps.util.mask_utils.log')
        self.mock_util_log = patcher4.start()
        self.addCleanup(patcher4.stop)

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

    def _create_targets(self, history, registers, completed=False):
        for register in registers:
            ContractTaskTargetFactory.create(history=history, register=register, completed=completed)

    def _create_targets_from_bulk(self, history, inputdata_list, completed=False):
        for inputdata in inputdata_list:
            ContractTaskTargetFactory.create(history=history, register=None, inputdata=inputdata, completed=completed)

    def _create_user_info(self, user):
        return {
            'email': user.email,
            'name': user.profile.name,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'login_code': user.bizuser.login_code if hasattr(user, 'bizuser') else None,
        }

    def _assert_user_info(self, user_info, user, masked=True):
        _email, _name, _login_code = (user_info[user.id]['email'], user_info[user.id]['name'], user_info[user.id]['login_code'])
        expected_email = mask_utils.hash(_email + self.random_value) if masked else _email
        expected_name = mask_utils.hash(_name) if masked else _name
        expected_first_name = '' if masked else user_info[user.id]['first_name']
        expected_last_name = '' if masked else user_info[user.id]['last_name']
        expected_login_code = self.random_value if _login_code and masked else _login_code

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

        self.assertEqual(bool(_login_code), hasattr(user, 'bizuser'))
        if _login_code:
            self.assertEqual(expected_login_code, user.bizuser.login_code)
        else:
            self.assertIsNone(expected_login_code)

    def _assert_cert_info(self, user_info, user, courses, masked=True):
        _name = user_info[user.id]['name']
        expected_name = mask_utils.hash(_name) if masked else _name
        # default values set in _create_enrollments.
        expected_status = CertificateStatuses.deleted if masked else CertificateStatuses.downloadable
        expected_key = '' if masked else 'key'
        expected_download_url = '' if masked else 'http://dummy'

        for course in courses:
            cert = GeneratedCertificate.objects.get(user_id=user.id, course_id=course.id)
            self.assertEqual(expected_name, cert.name)
            self.assertEqual(expected_status, cert.status)
            self.assertEqual(expected_key, cert.key)
            self.assertEqual(expected_download_url, cert.download_url)

    def _assert_global_courses(self, user_info, user, courses, masked=True):
        _email = user_info[user.id]['email']
        expected_email = mask_utils.hash(_email + self.random_value) if masked else _email

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
                expected_value = mask_utils.hash(expected_value)
            self.assertEqual(expected_value, AdditionalInfoSetting.get_value_by_display_name(user, contract, display_name))

    def _assert_success_message(self, registers):
        task = Task.objects.latest('id')
        for register in registers:
            self.mock_log.info.assert_any_call(
                'Task {}: Success to process of mask to User {}'.format(task.task_id, register.user_id)
            )

    def _assert_failed_message(self, registers):
        task = Task.objects.latest('id')
        for register in registers:
            self.mock_log.exception.assert_any_call(
                'Task {}: Failed to process of the personal information mask to User {}'.format(task.task_id, register.user_id)
            )

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

        self._assert_success_message(registers)
        self.mock_log.exception.assert_not_called()

    def test_successful_from_bulk(self):
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
        self._create_targets_from_bulk(history, inputdata_list)
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

        self._assert_success_message(registers)
        self.mock_log.exception.assert_not_called()

    def test_successful_login_code(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self._configure_dummy_provider(enabled=True)
        self._setup_courses()
        display_names = ['settting1', 'setting2', ]
        contract = self._create_contract(courses=self.spoc_courses, display_names=display_names)
        history = self._create_task_history(contract=contract)
        # users: enrolled only target spoc courses
        registers = [self._create_user_and_register(contract, display_names=display_names, login_code='LoginCode{}'.format(i)) for i in range(5)]
        self._create_targets(history, registers)
        self._create_enrollments(registers, self.spoc_courses)
        # This is `NOT` the target contract
        other_contract = self._create_contract(courses=self.other_enabled_spoc_courses, display_names=display_names)
        other_registers = [self._create_user_and_register(other_contract, display_names=display_names, login_code='LoginCode{}'.format(i)) for i in range(5)]
        self._create_contract(courses=self.other_not_enabled_spoc_courses, display_names=display_names, enabled=False)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers + other_registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
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

        self._assert_success_message(registers)
        self.mock_log.exception.assert_not_called()

    def test_successful_login_code_from_bulk(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self._configure_dummy_provider(enabled=True)
        self._setup_courses()
        display_names = ['settting1', 'setting2', ]
        contract = self._create_contract(courses=self.spoc_courses, display_names=display_names)
        history = self._create_task_history(contract=contract)
        # users: enrolled only target spoc courses
        registers = [self._create_user_and_register(contract, display_names=display_names, login_code='LoginCode{}'.format(i)) for i in range(5)]
        inputdata_list = [register.user.username for register in registers]
        self._create_targets_from_bulk(history, inputdata_list)
        self._create_enrollments(registers, self.spoc_courses)
        # This is `NOT` the target contract
        other_contract = self._create_contract(courses=self.other_enabled_spoc_courses, display_names=display_names)
        other_registers = [self._create_user_and_register(other_contract, display_names=display_names, login_code='LoginCode{}'.format(i)) for i in range(5)]
        self._create_contract(courses=self.other_not_enabled_spoc_courses, display_names=display_names, enabled=False)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers + other_registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
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

        self._assert_success_message(registers)
        self.mock_log.exception.assert_not_called()

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
        self.mock_get_random_string.return_value = self.random_value
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

        self._assert_success_message(registers)
        self.mock_log.exception.assert_not_called()

    def test_successful_reuse_email_from_bulk(self):
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
        inputdata_list = [register.user.username for register in registers]
        self._create_targets_from_bulk(history, inputdata_list)
        self._create_enrollments(registers, self.spoc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
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
        inputdata_list = [register.user.username for register in registers]
        self._create_targets_from_bulk(history, inputdata_list)
        self._create_enrollments(registers, self.spoc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers}

        # ----------------------------------------------------------
        # Execute task for 2nd
        # ----------------------------------------------------------
        self.random_value = 'test2'
        self.mock_get_random_string.return_value = self.random_value
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

        self._assert_success_message(registers)
        self.mock_log.exception.assert_not_called()

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
        self._create_targets(history, [registers[3]], completed=True)
        self._create_targets_from_bulk(history, [registers[4].user.username], completed=True)

        self._create_enrollments(registers, self.mooc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
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
        # Assert 3 of target is completed
        self.assertEqual(3, ContractTaskTarget.objects.filter(history=history, completed=True).count())
        self._assert_success_message(registers[:3])

        # Assert 2 of target is already personalinfo masked
        self.assertEqual("Line 4:username {username} already personal information masked.".format(username=registers[3].user.username),
                         ContractTaskTarget.objects.get(history=history, register=registers[3]).message)
        self.assertEqual("Line 5:username {username} already personal information masked.".format(username=registers[4].user.username),
                         ContractTaskTarget.objects.get(history=history, inputdata=registers[4].user.username).message)

        self.mock_log.exception.assert_not_called()

    def test_successful_with_gacco_service_from_bulk(self):
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
        inputdata_list = [register.user.username for register in registers[:3]]
        self._create_targets_from_bulk(history, inputdata_list)
        # 2 target is completed
        self._create_targets_from_bulk(history, [registers[3].user.username], completed=True)
        self._create_targets(history, [registers[4]], completed=True)
        self._create_enrollments(registers, self.mooc_courses)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers}

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
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
        # Assert 3 of target is completed
        self.assertEqual(3, ContractTaskTarget.objects.filter(history=history, completed=True).count())
        self._assert_success_message(registers[:3])

        # Assert 2 of target is already personalinfo masked
        self.assertEqual("Line 4:username {username} already personal information masked.".format(username=registers[3].user.username),
                         ContractTaskTarget.objects.get(history=history, inputdata=registers[3].user.username).message)
        self.assertEqual("Line 5:username {username} already personal information masked.".format(username=registers[4].user.username),
                         ContractTaskTarget.objects.get(history=history, register=registers[4]).message)

        self.mock_log.exception.assert_not_called()

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
        self._create_targets(history, [registers[3]], completed=True)
        self._create_targets_from_bulk(history, [registers[4].user.username], completed=True)
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
        # Assert 3 of target is completed
        self.assertEqual(3, ContractTaskTarget.objects.filter(history=history, completed=True).count())
        self._assert_success_message(registers[:3])

        # Assert 2 of target is already personalinfo masked
        self.assertEqual("Line 4:username {username} already personal information masked.".format(username=registers[3].user.username),
                         ContractTaskTarget.objects.get(history=history, register=registers[3]).message)
        self.assertEqual("Line 5:username {username} already personal information masked.".format(username=registers[4].user.username),
                         ContractTaskTarget.objects.get(history=history, inputdata=registers[4].user.username).message)

        self.mock_log.exception.assert_not_called()

    def test_successful_with_completed_target_from_bulk(self):
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
        inputdata_list = [register.user.username for register in registers[:3]]
        self._create_targets_from_bulk(history, inputdata_list)
        # 2 target is completed
        self._create_targets_from_bulk(history, [registers[3].user.username], completed=True)
        self._create_targets(history, [registers[4]], completed=True)
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
        # Assert 3 of target is completed
        self.assertEqual(3, ContractTaskTarget.objects.filter(history=history, completed=True).count())
        self._assert_success_message(registers[:3])

        # Assert 2 of target is already personalinfo masked
        self.assertEqual("Line 4:username {username} already personal information masked.".format(username=registers[3].user.username),
                         ContractTaskTarget.objects.get(history=history, inputdata=registers[3].user.username).message)
        self.assertEqual("Line 5:username {username} already personal information masked.".format(username=registers[4].user.username),
                         ContractTaskTarget.objects.get(history=history, register=registers[4]).message)

        self.mock_log.exception.assert_not_called()

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

        self._assert_success_message(registers[:4])
        self.mock_log.exception.assert_not_called()

    def test_successful_with_other_course_from_bulk(self):
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
        self._create_targets_from_bulk(history, inputdata_list)
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
            if target.inputdata == registers[4].user.username:
                self.assertFalse(target.completed)
            else:
                self.assertTrue(target.completed)

        self._assert_success_message(registers[:4])
        self.mock_log.exception.assert_not_called()

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

        self._assert_success_message(registers[:4])
        self.mock_log.exception.assert_not_called()

    def test_successful_with_mooc_course_from_bulk(self):
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
        self._create_targets_from_bulk(history, inputdata_list)
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
            if target.inputdata == registers[4].user.username:
                self.assertFalse(target.completed)
            else:
                self.assertTrue(target.completed)

        self._assert_success_message(registers[:4])
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
        ) as mock_check_enrollment:
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

        self._assert_success_message(registers[:4])
        self._assert_failed_message([registers[4]])
        self.assertEqual("Line 5:Failed to personal information masked. Please operation again after a time delay.",
                         ContractTaskTarget.objects.get(history=history, register=registers[4]).message)

    def test_successful_with_failed_from_bulk(self):
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
        self._create_targets_from_bulk(history, inputdata_list)
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
        ) as mock_check_enrollment:
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
        self.assertFalse(ContractTaskTarget.objects.get(history=history, inputdata=registers[4].user.username).completed)

        self._assert_success_message(registers[:4])
        self._assert_failed_message([registers[4]])
        self.assertEqual("Line 5:Failed to personal information masked. Please operation again after a time delay.",
                         ContractTaskTarget.objects.get(history=history, inputdata=registers[4].user.username).message)

    def test_successful_with_failed_cert_deletion(self):
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

        # Make the deletion of second user failed, otherwise it makes successful.
        self.mock_delete_cert_pdf.side_effect = [
            '{}', '{}',  # user1's deletion
            '{"error": "error"}', '{}',  # user2's deletion
            '{}', '{}',  # user3's deletion
            '{}', '{}',  # user4's deletion
            '{}', '{}',  # user5's deletion
        ]

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 4, 0, 1, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for i, register in enumerate(registers):
            masked = i != 1
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
        self.assertFalse(ContractTaskTarget.objects.get(history=history, register=registers[1]).completed)

        # delete_cert_pdf should be called 10 times even if previous process had been failed.
        self.assertEqual(10, self.mock_delete_cert_pdf.call_count)

        self.mock_util_log.error.assert_called_once_with(
            'Failed to delete certificate. user={}, course_id=spoc/course1/run'.format(registers[1].user_id)
        )
        self._assert_success_message([registers[0], registers[2], registers[3], registers[4]])
        self._assert_failed_message([registers[1]])
        self.assertEqual("Line 2:Failed to personal information masked. Please operation again after a time delay.",
                         ContractTaskTarget.objects.get(history=history, register=registers[1]).message)

    def test_successful_with_failed_cert_deletion_from_bulk(self):
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
        self._create_targets_from_bulk(history, inputdata_list)
        self._create_enrollments(registers, self.spoc_courses)
        # This is `NOT` the target contract
        other_contract = self._create_contract(courses=self.other_enabled_spoc_courses, display_names=display_names)
        other_registers = [self._create_user_and_register(other_contract, display_names=display_names) for _ in range(5)]
        self._create_contract(courses=self.other_not_enabled_spoc_courses, display_names=display_names, enabled=False)

        entry = self._create_input_entry(contract=contract, history=history)

        user_info = {register.user.id: self._create_user_info(register.user) for register in registers + other_registers}

        # Make the deletion of second user failed, otherwise it makes successful.
        self.mock_delete_cert_pdf.side_effect = [
            '{}', '{}',  # user1's deletion
            '{"error": "error"}', '{}',  # user2's deletion
            '{}', '{}',  # user3's deletion
            '{}', '{}',  # user4's deletion
            '{}', '{}',  # user5's deletion
        ]

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 4, 0, 1, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for i, register in enumerate(registers):
            masked = i != 1
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
        self.assertFalse(ContractTaskTarget.objects.get(history=history, inputdata=registers[1].user.username).completed)

        # delete_cert_pdf should be called 10 times even if previous process had been failed.
        self.assertEqual(10, self.mock_delete_cert_pdf.call_count)

        self.mock_util_log.error.assert_called_once_with(
            'Failed to delete certificate. user={}, course_id=spoc/course1/run'.format(registers[1].user_id)
        )
        self._assert_success_message([registers[0], registers[2], registers[3], registers[4]])
        self._assert_failed_message([registers[1]])
        self.assertEqual("Line 2:Failed to personal information masked. Please operation again after a time delay.",
                         ContractTaskTarget.objects.get(history=history, inputdata=registers[1].user.username).message)

    def test_input_validation_failed_from_bulk(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        self._configure_dummy_provider(enabled=True)
        self._setup_courses()
        display_names = ['settting1', 'setting2', ]
        contract = self._create_contract(courses=self.spoc_courses, display_names=display_names)
        registers = [self._create_user_and_register(contract, display_names=display_names) for _ in range(5)]
        history = self._create_task_history(contract=contract, requester=registers[3].user)
        # users: enrolled only target spoc courses
        inputdata_list = [
            "",
            "{},{}".format(registers[1].user.username, registers[1].user.id),
            "{}unknown".format(registers[2].user.username),
            registers[3].user.username,
            registers[4].user.username
        ]
        self._create_targets_from_bulk(history, inputdata_list)
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
        self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 1, 1, 3, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for i, register in enumerate(registers):
            masked = i == 4
            self._assert_additional_info(register.user, contract, display_names, masked=masked)
            self._assert_user_info(user_info, register.user, masked=masked)
            self._assert_cert_info(user_info, register.user, self.spoc_courses, masked=masked)
            self._assert_global_courses(user_info, register.user, self.global_courses, masked=masked)
        for register in other_registers:
            self._assert_additional_info(register.user, other_contract, display_names, masked=False)
            self._assert_user_info(user_info, register.user, masked=False)
            self._assert_global_courses(user_info, register.user, self.global_courses, masked=False)
        # Assert 1 of target is completed
        self.assertEqual(1, ContractTaskTarget.objects.filter(history=history, completed=True).count())
        for inputdata in inputdata_list[:4]:
            self.assertFalse(ContractTaskTarget.objects.get(history=history, inputdata=inputdata).completed)
        self._assert_success_message(registers[4:])

        # Assert 1st task is skip
        self.assertEqual(None,
                         ContractTaskTarget.objects.get(history=history, inputdata=inputdata_list[0]).message)
        # Assert 2nd task is unmatch colunn
        self.assertEqual("Line 2:Data must have exactly one column: username.",
                         ContractTaskTarget.objects.get(history=history, inputdata=inputdata_list[1]).message)
        # Assert 3rd task is register not found
        self.assertEqual("Line 3:username {username} is not registered student.".format(username=inputdata_list[2]),
                         ContractTaskTarget.objects.get(history=history, inputdata=inputdata_list[2]).message)
        # Assert 4th task is select yourself
        self.assertEqual("Line 4:You can not change of yourself.",
                         ContractTaskTarget.objects.get(history=history, inputdata=inputdata_list[3]).message)

        self.mock_log.exception.assert_not_called()

    def test_unregister(self):
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

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        self._test_run_with_task(personalinfo_mask, 'personalinfo_mask', 5, 0, 0, 5, 5, entry)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        for register in registers:
            user = User.objects.get(pk=register.user.id)
            self.assertFalse('@' in user.email)
            contract_register = ContractRegister.objects.get(pk=register.id)
            self.assertEquals(UNREGISTER_INVITATION_CODE, contract_register.status)
            for course_key in [detail.course_id for detail in contract.details.all()]:
                self.assertFalse(CourseEnrollment.is_enrolled(register.user, course_key))

        for register in other_registers:
            user = User.objects.get(pk=register.user.id)
            self.assertTrue('@' in user.email)
            contract_register = ContractRegister.objects.get(pk=register.id)
            self.assertNotEqual(UNREGISTER_INVITATION_CODE, contract_register.status)

        # Assert all of target is completed
        self.assertEqual(5, ContractTaskTarget.objects.filter(history=history, completed=True).count())

        self._assert_success_message(registers)
        self.mock_log.exception.assert_not_called()

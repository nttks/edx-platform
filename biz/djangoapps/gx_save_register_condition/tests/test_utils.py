# -*- coding: utf-8 -*-
"""
Test for save_register_condition feature
"""
import json
import ddt
from mock import patch
from biz.djangoapps.ga_organization.models import OrganizationOption
from biz.djangoapps.ga_contract.tests.factories import ContractOptionFactory
from biz.djangoapps.ga_invitation.models import ContractRegister, UNREGISTER_INVITATION_CODE, REGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase, AdditionalInfoSettingFactory
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_reservation_mail.models import ReservationMail
from biz.djangoapps.gx_save_register_condition.utils import (
    get_members_by_child_conditions, get_members_by_all_parents_conditions, ReflectConditionExecutor,
    reflect_condition_execute_call_by_another_task)
from biz.djangoapps.gx_save_register_condition.models import ChildCondition, ReflectConditionTaskHistory
from biz.djangoapps.gx_save_register_condition.tests.factories import ParentConditionFactory, ChildConditionFactory
from biz.djangoapps.util.tests.testcase import BizTestBase
from lms.djangoapps.courseware.courses import get_course_by_id
from openedx.core.djangoapps.ga_task.models import Task
from student.models import CourseEnrollment
from student.tests.factories import UserFactory, CourseEnrollmentFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@ddt.ddt
class SearchByConditionsTest(BizContractTestBase):

    def setUp(self):
        super(SearchByConditionsTest, self).setUp()

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

    def _assert_get_members_by_child_conditions(self, org, contract, child_conditions, expect_num):
        members = get_members_by_child_conditions(org, contract, child_conditions)
        self.assertEqual(len(members), expect_num)

    """
    Test get_members_by_all_parents_conditions
    """
    def test_get_members_by_all_parents_conditions(self):
        parent1 = ParentConditionFactory.create(
            contract=self.contract, parent_condition_name='parent_1', setting_type=1,
            created_by=self.user, modified_by=self.user
        )
        ChildConditionFactory.create(
            contract=self.contract,
            parent_condition=parent1, parent_condition_name=parent1.parent_condition_name,
            comparison_target=ChildCondition.COMPARISON_TARGET_EMAIL,
            comparison_type=ChildCondition.COMPARISON_TYPE_CONTAINS_NO,
            comparison_string='sample001'
        )
        parent2 = ParentConditionFactory.create(
            contract=self.contract, parent_condition_name='parent_2', setting_type=2,
            created_by=self.user, modified_by=self.user
        )
        ChildConditionFactory.create(
            contract=self.contract,
            parent_condition=parent2, parent_condition_name=parent1.parent_condition_name,
            comparison_target=ChildCondition.COMPARISON_TARGET_USERNAME,
            comparison_type=ChildCondition.COMPARISON_TYPE_CONTAINS_NO,
            comparison_string='sample002'
        )
        parent3 = ParentConditionFactory.create(
            contract=self.contract, parent_condition_name='parent_3', setting_type=2,
            created_by=self.user, modified_by=self.user
        )

        self._create_member(
            org=self.contract_org, group=None, user=UserFactory.create(email='sample001@example.com'), code='xxx1')
        self._create_member(
            org=self.contract_org, group=None, user=UserFactory.create(username='sample002'), code='xxx2')

        self.assertEqual(2, len(get_members_by_all_parents_conditions(self.contract_org, self.contract)))

    """
    Test get_members_by_child_conditions
    """
    def test_get_members_by_child_conditions_when_is_none(self):
        self.assertEqual([], get_members_by_child_conditions(self.contract_org, self.contract, []))

    @ddt.unpack
    @ddt.data(
        (ChildCondition.COMPARISON_TYPE_EQUAL_NO, 'sample_code_001', 1),
        (ChildCondition.COMPARISON_TYPE_NOT_EQUAL_NO, 'sample_code_001', 3),
        (ChildCondition.COMPARISON_TYPE_CONTAINS_NO, 'sample_code', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_CONTAINS_NO, 'sample_code', 2),
        (ChildCondition.COMPARISON_TYPE_STARTSWITH_NO, 'sample', 3),
        (ChildCondition.COMPARISON_TYPE_ENDSWITH_NO, '001', 1),
        (ChildCondition.COMPARISON_TYPE_IN_NO, 'sample_code_001,sample_code_002', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_IN_NO, 'sample_code_001,sample_code_002', 2),
    )
    def test_get_members_by_child_conditions_when_column_is_code(self, type_no, string, result):
        for code in ['sample_code_001', 'sample_code_002', 'sample_for_not_contains_code', 'not_startswith']:
            self._create_member(org=self.contract_org, group=None, user=UserFactory.create(), code=code)

        self._assert_get_members_by_child_conditions(self.contract_org, self.contract, [
            ChildCondition(
                contract=self.contract, comparison_target=ChildCondition.COMPARISON_TARGET_CODE,
                comparison_type=type_no, comparison_string=string)
        ], result)

    @ddt.unpack
    @ddt.data(
        (ChildCondition.COMPARISON_TYPE_EQUAL_NO, 'sample_username_001', 1),
        (ChildCondition.COMPARISON_TYPE_NOT_EQUAL_NO, 'sample_username_001', 3),
        (ChildCondition.COMPARISON_TYPE_CONTAINS_NO, 'sample_username', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_CONTAINS_NO, 'sample_username', 2),
        (ChildCondition.COMPARISON_TYPE_STARTSWITH_NO, 'sample', 3),
        (ChildCondition.COMPARISON_TYPE_ENDSWITH_NO, '001', 1),
        (ChildCondition.COMPARISON_TYPE_IN_NO, 'sample_username_001,sample_username_002', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_IN_NO, 'sample_username_001,sample_username_002', 2),
    )
    def test_get_members_by_child_conditions_when_column_is_username(self, type_no, string, result):
        for i, username in enumerate(
                ['sample_username_001', 'sample_username_002', 'sample_for_not_contains_username', 'not_startswith']):
            self._create_member(
                org=self.contract_org, group=None, user=UserFactory.create(username=username), code='sample_' + str(i))

        self._assert_get_members_by_child_conditions(self.contract_org, self.contract, [
            ChildCondition(
                contract=self.contract, comparison_target=ChildCondition.COMPARISON_TARGET_USERNAME,
                comparison_type=type_no, comparison_string=string)
        ], result)

    @ddt.unpack
    @ddt.data(
        (ChildCondition.COMPARISON_TYPE_EQUAL_NO, 'sample_email_001@example.com', 1),
        (ChildCondition.COMPARISON_TYPE_NOT_EQUAL_NO, 'sample_email_001@example.com', 3),
        (ChildCondition.COMPARISON_TYPE_CONTAINS_NO, 'sample_email', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_CONTAINS_NO, 'sample_email', 2),
        (ChildCondition.COMPARISON_TYPE_STARTSWITH_NO, 'sample', 3),
        (ChildCondition.COMPARISON_TYPE_ENDSWITH_NO, '001@example.com', 1),
        (ChildCondition.COMPARISON_TYPE_IN_NO, 'sample_email_001@example.com,sample_email_002@example.com', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_IN_NO, 'sample_email_001@example.com,sample_email_002@example.com', 2),
    )
    def test_get_members_by_child_conditions_when_column_is_email(self, type_no, string, result):
        for i, email in enumerate(
                ['sample_email_001@example.com', 'sample_email_002@example.com',
                 'sample_for_not_contains_email@example.com', 'not_startswith@example.com']):
            self._create_member(
                org=self.contract_org, group=None, user=UserFactory.create(email=email), code='sample_' + str(i))

        self._assert_get_members_by_child_conditions(self.contract_org, self.contract, [
            ChildCondition(
                contract=self.contract, comparison_target=ChildCondition.COMPARISON_TARGET_EMAIL,
                comparison_type=type_no, comparison_string=string)
        ], result)

    @ddt.unpack
    @ddt.data(
        (ChildCondition.COMPARISON_TYPE_EQUAL_NO, 'sample_login_code_001', 1),
        (ChildCondition.COMPARISON_TYPE_NOT_EQUAL_NO, 'sample_login_code_001', 3),
        (ChildCondition.COMPARISON_TYPE_CONTAINS_NO, 'sample_login_code', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_CONTAINS_NO, 'sample_login_code', 2),
        (ChildCondition.COMPARISON_TYPE_STARTSWITH_NO, 'sample', 3),
        (ChildCondition.COMPARISON_TYPE_ENDSWITH_NO, '001', 1),
        (ChildCondition.COMPARISON_TYPE_IN_NO, 'sample_login_code_001,sample_login_code_002', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_IN_NO, 'sample_login_code_001,sample_login_code_002', 2),
    )
    def test_get_members_by_child_conditions_when_column_is_login_code(self, type_no, string, result):
        for i, login_code in enumerate([
            'sample_login_code_001', 'sample_login_code_002', 'sample_for_not_contains_login_code', 'not_startswith']):
            member = self._create_member(
                org=self.contract_org, group=None, user=UserFactory.create(), code='sample_' + str(i))
            BizUserFactory(user=member.user, login_code=login_code)

        self._assert_get_members_by_child_conditions(self.contract_org, self.contract, [
            ChildCondition(
                contract=self.contract, comparison_target=ChildCondition.COMPARISON_TARGET_LOGIN_CODE,
                comparison_type=type_no, comparison_string=string)
        ], result)

    @ddt.unpack
    @ddt.data(
        (ChildCondition.COMPARISON_TYPE_EQUAL_NO, 'sample_group_name_001', 1),
        (ChildCondition.COMPARISON_TYPE_NOT_EQUAL_NO, 'sample_group_name_001', 2),
        (ChildCondition.COMPARISON_TYPE_CONTAINS_NO, 'sample', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_CONTAINS_NO, 'sample', 1),
        (ChildCondition.COMPARISON_TYPE_STARTSWITH_NO, 'sample', 2),
        (ChildCondition.COMPARISON_TYPE_ENDSWITH_NO, '001', 1),
        (ChildCondition.COMPARISON_TYPE_IN_NO, 'sample_group_name_001,sample_group_name_002', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_IN_NO, 'sample_group_name_001,sample_group_name_002', 1),
    )
    def test_get_members_by_child_conditions_when_column_is_group_name(self, type_no, string, result):
        for i, group_name in enumerate(['sample_group_name_001', 'sample_group_name_002', 'not_startswith']):
            group = Group.objects.create(
                org=self.contract_org,
                group_code=group_name, group_name=group_name,
                level_no=0, parent_id=0, created_by=self.user, modified_by=self.user
            )
            self._create_member(
                org=self.contract_org, group=group, user=UserFactory.create(), code='sample_' + str(i))

        self._assert_get_members_by_child_conditions(self.contract_org, self.contract, [
            ChildCondition(
                contract=self.contract, comparison_target=ChildCondition.COMPARISON_TARGET_GROUP_NAME,
                comparison_type=type_no, comparison_string=string)
        ], result)

    @ddt.unpack
    @ddt.data(
        (ChildCondition.COMPARISON_TYPE_EQUAL_NO, 'sample_001', 1),
        (ChildCondition.COMPARISON_TYPE_NOT_EQUAL_NO, 'sample_001', 59),
        (ChildCondition.COMPARISON_TYPE_CONTAINS_NO, 'sample', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_CONTAINS_NO, 'sample', 58),
        (ChildCondition.COMPARISON_TYPE_STARTSWITH_NO, 'sample', 2),
        (ChildCondition.COMPARISON_TYPE_ENDSWITH_NO, '001', 1),
        (ChildCondition.COMPARISON_TYPE_IN_NO, 'sample_001,sample_002', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_IN_NO, 'sample_001,sample_002', 58),
    )
    def test_get_members_by_child_conditions_when_column_is_ogr_item(self, type_no, string, result):
        for i in range(0, 10):
            for j, value in enumerate(['sample_001', 'sample_002', 'not_startswith'], start=1):
                # org1
                self._create_member(
                    org=self.contract_org, group=None, user=UserFactory.create(),
                    code='sample_org_' + str(i) + str(j), **dict({ChildCondition.COMPARISON_TARGET_ORG_LIST[i]: value}))
                # item1
                self._create_member(
                    org=self.contract_org, group=None, user=UserFactory.create(),
                    code='sample_item_' + str(i) + str(j), **dict({ChildCondition.COMPARISON_TARGET_ITEM_LIST[i]: value}))

        for i in range(0, 10):
            self._assert_get_members_by_child_conditions(self.contract_org, self.contract, [
                ChildCondition(
                    contract=self.contract, comparison_target=ChildCondition.COMPARISON_TARGET_ORG_LIST[i],
                    comparison_type=type_no, comparison_string=string)
            ], result)
            self._assert_get_members_by_child_conditions(self.contract_org, self.contract, [
                ChildCondition(
                    contract=self.contract, comparison_target=ChildCondition.COMPARISON_TARGET_ITEM_LIST[i],
                    comparison_type=type_no, comparison_string=string)
            ], result)

    @ddt.unpack
    @ddt.data(
        (ChildCondition.COMPARISON_TYPE_EQUAL_NO, 'sample_001', 1),
        (ChildCondition.COMPARISON_TYPE_NOT_EQUAL_NO, 'sample_001', 2),
        (ChildCondition.COMPARISON_TYPE_CONTAINS_NO, 'sample', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_CONTAINS_NO, 'sample', 1),
        (ChildCondition.COMPARISON_TYPE_STARTSWITH_NO, 'sample', 2),
        (ChildCondition.COMPARISON_TYPE_ENDSWITH_NO, '001', 1),
        (ChildCondition.COMPARISON_TYPE_IN_NO, 'sample_001,sample_002', 2),
        (ChildCondition.COMPARISON_TYPE_NOT_IN_NO, 'sample_001,sample_002', 1),
    )
    def test_get_members_by_child_conditions_when_column_is_additional_info(self, type_no, string, result):
        for i, value in enumerate(['sample_001', 'sample_002', 'not_startswith'], start=1):
            member = self._create_member(
                org=self.contract_org, group=None, user=UserFactory.create(), code='sample_' + str(i))
            AdditionalInfoSettingFactory.create(
                user=member.user, contract=self.contract, display_name='country', value=value)

        self._assert_get_members_by_child_conditions(self.contract_org, self.contract, [
            ChildCondition(
                contract=self.contract, comparison_target='country',
                comparison_type=type_no, comparison_string=string)
        ], result)

    def test_get_members_by_child_conditions_when_column_is_none(self):
        self._assert_get_members_by_child_conditions(self.contract_org, self.contract, [
            ChildCondition(
                contract=self.contract, comparison_target='undefiled_target',
                comparison_type=9999, comparison_string='')
        ], 0)


@ddt.ddt
class ReflectConditionExecutorTest(BizTestBase, ModuleStoreTestCase):
    def setUp(self):
        super(ReflectConditionExecutorTest, self).setUp()
        # Create default mail
        self._create_contract_mail_default()
        # Create org, contract, course
        self.org = self._create_organization(org_code='sample1', org_name='sample1')
        self.course_spoc1 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc1', run='run1')
        self.course_spoc2 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc2', run='run2')
        self.course_spoc3 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc3', run='run3')
        self.contract = self._create_contract(
            contract_name='sample1', contractor_organization=self.org, owner_organization=self.gacco_organization,
            detail_courses=[self.course_spoc1, self.course_spoc2], additional_display_names=['country', 'dept'],
            send_mail=True)
        self.contract_auth = self._create_contract(
            contract_name='sample2', contractor_organization=self.org, owner_organization=self.gacco_organization,
            url_code='testAuth', detail_courses=[self.course_spoc3], additional_display_names=['country', 'dept'],
            send_mail=True)

        self.org_other = self._create_organization(org_code='sample2', org_name='sample2')

        # Setting mock log
        patcher = patch('biz.djangoapps.gx_save_register_condition.utils.log')
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
    def _create_contract_register(self, user, contract, status=REGISTER_INVITATION_CODE):
        register = ContractRegisterFactory.create(user=user, contract=contract, status=status)
        for detail in contract.details.all():
            course = get_course_by_id(detail.course_id)
            CourseEnrollmentFactory.create(user=user, course_id=course.id)
        return register

    @ddt.data(True, False)
    def test_execute(self, contract_has_auth):
        contract = self.contract_auth if contract_has_auth else self.contract
        # Create condition
        parent1 = ParentConditionFactory.create(
            contract=contract, parent_condition_name='parent_1', setting_type=1,
            created_by=self.user, modified_by=self.user
        )
        ChildConditionFactory.create(
            contract=contract,
            parent_condition=parent1,
            parent_condition_name='parent_1',
            comparison_target=ChildCondition.COMPARISON_TARGET_EMAIL,
            comparison_type=ChildCondition.COMPARISON_TYPE_CONTAINS_NO,
            comparison_string='sample001'
        )

        # Create member for register
        register_member = self._create_member(
            org=self.org, group=None, user=UserFactory.create(email='sample001@example.com'), code='register')

        # Create member for unregister
        unregister_members = []
        for i in range(0, 3):
            user = UserFactory.create()
            unregister_members.append(self._create_member(
                org=self.org, group=None, user=user, code='unregister_' + str(i)))
            self._create_contract_register(user=user, contract=contract)

        # Create member for not target
        self._create_member(
            org=self.org_other, group=None,
            user=UserFactory.create(email='sample001_other@example.com'), code='register')

        # Execute
        executor = ReflectConditionExecutor(org=self.org, contract=contract, send_mail_flg=True)
        executor.execute()

        # Check Unregister
        unregisters = ContractRegister.objects.filter(contract=contract, status=UNREGISTER_INVITATION_CODE)
        self.assertEqual(3, len(unregisters))
        for unregister in unregisters:
            # Check unenroll
            for detail in contract.details.all():
                self.assertFalse(CourseEnrollment.is_enrolled(unregister.user, detail.course_id))

        # Check Register
        registers = ContractRegister.objects.filter(contract=contract, status=REGISTER_INVITATION_CODE)
        self.assertEqual(1, len(registers))
        for register in registers:
            # Check enrolled
            for detail in contract.details.all():
                self.assertTrue(CourseEnrollment.is_enrolled(register.user, detail.course_id))
            # Check mail
            reservation_mails = ReservationMail.objects.filter(user=register.user, org=self.org)
            self.assertEqual(1, len(reservation_mails))
            reservation_mail = reservation_mails[0]
            if contract_has_auth:
                self.assertEqual(reservation_mail.mail_subject, 'Test Subject Exists User With Logincode')
                self.assertEqual(reservation_mail.mail_body, 'Test Body Exists User With Logincode')
            else:
                self.assertEqual(reservation_mail.mail_subject, 'Test Subject Exists User Without Logincode')
                self.assertEqual(reservation_mail.mail_body, 'Test Body Exists User Without Logincode')

        self.mock_log.info.assert_any_call('Register user id:{register}'.format(register=str(register_member.user.id)))
        self.mock_log.info.assert_any_call('Unregister user id:{unregister}'.format(
            unregister=",".join([str(member.user.id) for member in unregister_members])))
        self.mock_log.info.assert_any_call('Masked user id:{masked}'.format(masked=''))

    @ddt.data(True, False)
    def test_execute_delete_target_unregister_and_mask(self, auto_mask_flg):
        # Create delete member
        user = UserFactory.create(email='sample001@example.com')
        self._create_member(
            org=self.org, group=None, user=user, code='mask', is_active=False, is_delete=True)
        self._create_contract_register(user=user, contract=self.contract)
        options = OrganizationOption.objects.filter(org=self.org)
        option = OrganizationOption.objects.create(
            org=self.org, modified_by=self.user) if len(options) == 0 else options[0]
        option.auto_mask_flg = auto_mask_flg
        option.save()

        # Execute
        executor = ReflectConditionExecutor(org=self.org, contract=self.contract, send_mail_flg=False)
        executor.execute()

        # Check unregister
        unregisters = ContractRegister.objects.filter(
            contract=self.contract, user=user, status=UNREGISTER_INVITATION_CODE)
        self.assertEqual(1, len(unregisters))
        unregister = unregisters[0]
        for detail in self.contract.details.all():
            self.assertFalse(CourseEnrollment.is_enrolled(user, detail.course_id))
        if auto_mask_flg:
            # Check mask and Delete member
            self.assertTrue('@' not in unregister.user.email)
            # Delete member
            self.assertEqual(0, Member.objects.filter(
                org=self.org, is_active=False, is_delete=True, user=user).count())
            self.mock_log.info.assert_any_call('Register user id:{register}'.format(register=''))
            self.mock_log.info.assert_any_call('Unregister user id:{unregister}'.format(unregister=str(user.id)))
            self.mock_log.info.assert_any_call('Masked user id:{masked}'.format(masked=str(user.id)))
        else:
            # Check mask and not delete member
            self.assertTrue('@' in unregister.user.email)
            self.assertEqual(1, Member.objects.filter(
                org=self.org, is_active=False, is_delete=True, user=user).count())
            self.mock_log.info.assert_any_call('Register user id:{register}'.format(register=''))
            self.mock_log.info.assert_any_call('Unregister user id:{unregister}'.format(unregister=str(user.id)))
            self.mock_log.info.assert_any_call('Masked user id:{masked}'.format(masked=''))

    def test_execute_when_exception_register(self):
        parent1 = ParentConditionFactory.create(
            contract=self.contract, parent_condition_name='parent_1', setting_type=1,
            created_by=self.user, modified_by=self.user
        )
        ChildConditionFactory.create(
            contract=self.contract,
            parent_condition=parent1,
            parent_condition_name='parent_1',
            comparison_target=ChildCondition.COMPARISON_TARGET_CODE,
            comparison_type=ChildCondition.COMPARISON_TYPE_CONTAINS_NO,
            comparison_string='register'
        )

        # Create member for register
        self._create_member(
            org=self.org, group=None, user=UserFactory.create(username='sample001'), code='register')

        # Execute
        with patch('biz.djangoapps.gx_save_register_condition.utils.ContractRegister.objects.get_or_create', side_effect=Exception()):
            executor = ReflectConditionExecutor(org=self.org, contract=self.contract, send_mail_flg=True)
            executor.execute()

        # Check error result
        self.assertEqual(1, executor.count_error)
        self.assertEqual(["Failed to register of sample001."], executor.errors)

    def test_execute_when_exception_unregister(self):
        parent1 = ParentConditionFactory.create(
            contract=self.contract, parent_condition_name='parent_1', setting_type=1,
            created_by=self.user, modified_by=self.user
        )
        ChildConditionFactory.create(
            contract=self.contract,
            parent_condition=parent1,
            parent_condition_name='parent_1',
            comparison_target=ChildCondition.COMPARISON_TARGET_CODE,
            comparison_type=ChildCondition.COMPARISON_TYPE_CONTAINS_NO,
            comparison_string='xxx'
        )

        # Create member for register
        user = UserFactory.create(username='sample001')
        self._create_member(org=self.org, group=None, user=user, code='unregister')
        self._create_contract_register(user=user, contract=self.contract)

        # Execute
        with patch('biz.djangoapps.gx_save_register_condition.utils.CourseEnrollment.is_enrolled', side_effect=Exception()):
            executor = ReflectConditionExecutor(org=self.org, contract=self.contract, send_mail_flg=True)
            executor.execute()

        # Check error result
        self.assertEqual(1, executor.count_error)
        self.assertEqual(["Failed to unregister of sample001."], executor.errors)

    def test_reflect_condition_execute_call_by_another_task_when_not_expected_task(self):
        # Execute
        try:
            reflect_condition_execute_call_by_another_task(
                task_id='', org=self.org, user=self.user, action_name='other_test_task')
        except ValueError:
            self.assertTrue(True)

    @ddt.data('reflect_conditions_member_register', 'reflect_conditions_student_member_register')
    def test_reflect_condition_execute_call_by_another_task(self, action_name):
        # Create contract option : auto_register_students_flg = True
        ContractOptionFactory.create(contract=self.contract, auto_register_students_flg=True)
        ContractOptionFactory.create(contract=self.contract_auth, auto_register_students_flg=True)
        # Create condition
        parent1 = ParentConditionFactory.create(
            contract=self.contract, parent_condition_name='parent_1', setting_type=1,
            created_by=self.user, modified_by=self.user
        )
        ChildConditionFactory.create(
            contract=self.contract,
            parent_condition=parent1,
            parent_condition_name='parent_1',
            comparison_target=ChildCondition.COMPARISON_TARGET_CODE,
            comparison_type=ChildCondition.COMPARISON_TYPE_CONTAINS_NO,
            comparison_string='sample001'
        )

        # Create member for register
        self._create_member(org=self.org, group=None, user=UserFactory.create(), code='sample001')

        # Execute
        reflect_condition_execute_call_by_another_task(
            task_id='', org=self.org, user=self.user, action_name=action_name)

        # Check log
        self.mock_log.info.assert_any_call('can_immediate_reflection is True.')
        # Check task
        task_history1 = ReflectConditionTaskHistory.objects.get(organization=self.org, contract=self.contract)
        self.assertTrue(task_history1.result)
        self.assertEqual('', task_history1.messages)
        task_list1 = Task.objects.filter(task_id=task_history1.task_id)
        self.assertEqual(1, len(task_list1))
        task1 = task_list1[0]
        self.assertEqual(task1.task_type, action_name)
        self.assertEqual(task1.task_state, 'SUCCESS')
        task_output1 = json.loads(task1.task_output)
        self.assertTrue(all(key in task_output1 for key in [
            'total','failed','student_register', 'student_unregister', 'personalinfo_mask']))
        self.assertEqual(1, task_output1['total'])
        self.assertEqual(1, task_output1['student_register'])
        self.assertEqual(0, task_output1['student_unregister'])
        self.assertEqual(0, task_output1['personalinfo_mask'])
        self.assertEqual(0, task_output1['failed'])

        task_history2 = ReflectConditionTaskHistory.objects.get(organization=self.org, contract=self.contract_auth)
        self.assertTrue(task_history2.result)
        self.assertEqual('', task_history2.messages)
        task_list2 = Task.objects.filter(task_id=task_history2.task_id)
        self.assertEqual(1, len(task_list2))
        task2 = task_list2[0]
        self.assertEqual(task2.task_type, action_name)
        self.assertEqual(task2.task_state, 'SUCCESS')
        task_output2 = json.loads(task2.task_output)
        self.assertTrue(all(key in task_output2 for key in [
            'total','failed','student_register', 'student_unregister', 'personalinfo_mask']))
        self.assertEqual(1, task_output2['total'])
        self.assertEqual(0, task_output2['student_register'])
        self.assertEqual(0, task_output2['student_unregister'])
        self.assertEqual(0, task_output2['personalinfo_mask'])
        self.assertEqual(0, task_output2['failed'])

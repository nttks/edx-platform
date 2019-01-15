# -*- coding: utf-8 -*-
"""
Test for contract_operation students feature
"""
from collections import OrderedDict
import ddt
import hashlib
import json
from mock import patch

from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.http import HttpResponse

from biz.djangoapps.ga_contract.models import AdditionalInfo
from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.ga_invitation.models import ContractRegister, AdditionalInfoSetting,\
    INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory, RightFactory, GroupUtil

from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.tests.factories import TaskFactory

from student.models import CourseEnrollment
from student.tests.factories import UserFactory, RegistrationFactory


ERROR_MSG = "Test Message"


@ddt.ddt
class ContractOperationViewTestStudents(BizContractTestBase):

    @property
    def _url_index(self):
        return reverse('biz:contract_operation:students')

    @property
    def _url_search_students_ajax(self):
        return reverse('biz:contract_operation:students_search_students_ajax')

    @property
    def _url_students_download(self):
        return reverse('biz:contract_operation:students_students_download')

    @property
    def _director_manager(self):
        return self._create_manager(
            org=self.contract_org, user=self.user, created=self.contract_org, permissions=[self.director_permission])

    @property
    def _manager_manager(self):
        return self._create_manager(
            org=self.contract_org, user=self.user, created=self.contract_org, permissions=[self.manager_permission])

    def _assert_search_ajax_successful(self, data, total, show_list):
        self.assertEquals(data['info'], 'Success')
        self.assertEqual(data['total_count'], total)
        self.assertEqual(len(json.loads(data['show_list'])), show_list)

    def _create_param_search_students_ajax(
            self, contract_id=None, offset=0, limit=1000, status='',
            is_unregister='contains', member_is_delete='exclude', is_masked='contains', group_name='', free_word=''):
        param = {
            'contract_id': contract_id or self.contract.id,
            'offset': str(offset),
            'limit': str(limit),
            'status': status,
            'is_unregister': is_unregister,
            'member_is_delete': member_is_delete,
            'is_masked': is_masked,
            'group_name': group_name,
            'free_word': free_word
        }
        for i in range(1, 11):
            param['org_item_field_select_' + str(i)] = ''
            param['org_item_field_text_' + str(i)] = ''
        return param

    def _create_user_and_contract_register(self, status=None, **kwargs):
        user = UserFactory.create(**kwargs)
        if status is None:
            register = self.create_contract_register(user=user, contract=self.contract)
        else:
            register = self.create_contract_register(user=user, contract=self.contract, status=status)
        return register

    def _create_member(self, org, group, user, code, is_active=True, is_delete=False, **kwargs):
        return MemberFactory.create(
            org=org,
            group=group,
            user=user,
            code=code,
            created_by=self.user,
            creator_org=org,
            updated_by=self.user,
            updated_org=org,
            is_active=is_active,
            is_delete=is_delete,
            **kwargs
        )

    def test_index_director(self):
        self.setup_user()
        director_manager = self._director_manager
        for i in range(1050):
            self._create_user_and_contract_register()
        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            with patch('biz.djangoapps.ga_contract_operation.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.assert_request_status_code(200, self._url_index)

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_contract_operation/students.html')
        self.assertEqual(render_to_response_args[1]['total_count'], 1050)
        self.assertEqual(len(json.loads(render_to_response_args[1]['show_list'])), 1000)
        self.assertEqual(render_to_response_args[1]['max_show_num_on_page'], 1000)
        self.assertDictEqual(render_to_response_args[1]['status_list'], {
            'Input': 'Input Invitation',
            'Register': 'Register Invitation',
            'Unregister': 'Unregister Invitation'
        })
        self.assertDictEqual(render_to_response_args[1]['member_org_item_list'], OrderedDict([
            ('org1', 'Organization1'), ('org2', 'Organization2'), ('org3', 'Organization3'), ('org4', 'Organization4'),
            ('org5', 'Organization5'), ('org6', 'Organization6'), ('org7', 'Organization7'), ('org8', 'Organization8'),
            ('org9', 'Organization9'), ('org10', 'Organization10'),
            ('item1', 'Item1'), ('item2', 'Item2'), ('item3', 'Item3'), ('item4', 'Item4'), ('item5', 'Item5'),
            ('item6', 'Item6'), ('item7', 'Item7'), ('item8', 'Item8'), ('item9', 'Item9'), ('item10', 'Item10')
        ]))
        self.assertEqual(json.loads(render_to_response_args[1]['additional_columns']), [
            {'field': 'country', 'caption': 'country', 'sortable': True, 'hidden': True, 'size': 5},
            {'field': 'dept', 'caption': 'dept', 'sortable': True, 'hidden': True, 'size': 5}
        ])

    @ddt.unpack
    @ddt.data(("", 0), ("G03", 0), ("G02", 5), ("G01-01", 3), ("G02-01-02", 1))
    def test_index_manager(self, param_group_code, expect_num):
        self.setup_user()
        manager_manager = self._manager_manager
        # Create groups
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        groups = Group.objects.filter(org=self.contract_org)
        # Create member in group
        for i, group in enumerate(groups):
            register = self._create_user_and_contract_register()
            self._create_member(
                org=self.contract_org, group=group, user=register.user, code='code' + str(i))
        # Create member not belong to group
        register = self._create_user_and_contract_register()
        self._create_member(
            org=self.contract_org, group=None, user=register.user, code='code_not_group')
        try:
            group = Group.objects.get(org=self.contract_org, group_code=param_group_code)
            RightFactory.create(org=self.contract_org, group=group, user=manager_manager.user, created_by=self.user,
                                creator_org=self.contract_org)
        except Group.DoesNotExist:
            pass

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=manager_manager):
            with patch('biz.djangoapps.ga_contract_operation.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.assert_request_status_code(200, self._url_index)

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_contract_operation/students.html')
        self.assertEqual(render_to_response_args[1]['total_count'], expect_num)
        self.assertEqual(len(json.loads(render_to_response_args[1]['show_list'])), expect_num)


    @ddt.data(0, 1, 10)
    def test_search_students_ajax(self, test_num):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_param_search_students_ajax()
        for i in range(test_num):
            self._create_user_and_contract_register(username='username' + str(i))

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, test_num, test_num)

    def test_search_students_ajax_no_user_profile(self):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_param_search_students_ajax()
        register = self._create_user_and_contract_register()
        register.user.profile.delete()

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 1, 1)

    def test_students_search_students_ajax_error_authorize(self):
        self.setup_user()
        director_manager = self._director_manager

        param = self._create_param_search_students_ajax()
        param.pop('contract_id', None)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_students_search_students_ajax_conflict_conditions(self):
        self.setup_user()
        director_manager = self._director_manager
        # Create contract registers
        for status in [INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE]:
            self._create_user_and_contract_register(status=status)

        # Set conflict conditions
        params = [
            self._create_param_search_students_ajax(is_unregister='only', status=INPUT_INVITATION_CODE),
            self._create_param_search_students_ajax(is_unregister='exclude', status=UNREGISTER_INVITATION_CODE)
        ]

        for param in params:
            with self.skip_check_course_selection(current_organization=self.contract_org,
                                                  current_contract=self.contract, current_manager=director_manager):
                response = self.client.post(self._url_search_students_ajax, param)

            self.assertEqual(200, response.status_code)
            data = json.loads(response.content)
            self._assert_search_ajax_successful(data, 0, 0)

    @ddt.data('org', 'item')
    def test_students_search_students_ajax_detail(self, key):
        self.setup_user()
        director_manager = self._director_manager

        # Create students have only one in key(org or item)1-10
        for i in range(1, 11):
            register = self._create_user_and_contract_register(username='username' + str(key) + str(i))
            self._create_member(
                org=self.contract_org, group=None, user=register.user, code='code' + str(i),
                **dict({key + str(i): 'search_key_word' + str(key) + str(i)})
            )

        for i in range(1, 11):
            param = self._create_param_search_students_ajax()
            param['org_item_field_select_' + str(i)] = key + str(i)
            param['org_item_field_text_' + str(i)] = 'search_key_word' + key + str(i)
            with self.skip_check_course_selection(current_organization=self.contract_org,
                                                  current_contract=self.contract, current_manager=director_manager):
                response = self.client.post(self._url_search_students_ajax, param)

            self.assertEqual(200, response.status_code)
            data = json.loads(response.content)
            self._assert_search_ajax_successful(data, 1, 1)
            show_list = json.loads(data['show_list'])
            self.assertEqual(show_list[0][key + str(i)], 'search_key_word' + str(key) + str(i))
            self.assertEqual(show_list[0]['user_name'], 'username' + str(key) + str(i))

    @ddt.unpack
    @ddt.data(
        (INPUT_INVITATION_CODE, ['Input Invitation'], 'exclude', 1),
        (REGISTER_INVITATION_CODE, ['Register Invitation'], 'exclude', 1),
        ('', ['Input Invitation', 'Register Invitation'], 'exclude', 2),
        (UNREGISTER_INVITATION_CODE, ['Unregister Invitation'], 'contains', 1),
        (UNREGISTER_INVITATION_CODE, ['Unregister Invitation'], 'only', 1),
        ('', ['Unregister Invitation'], 'only', 1)
    )
    def test_students_search_students_ajax_status_and_is_unregister(
            self, param_status, status_list, is_unregister, expect):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_param_search_students_ajax(status=param_status, is_unregister=is_unregister)
        # Create contract registers
        for status in [INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE]:
            self._create_user_and_contract_register(status=status)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, expect, expect)
        show_list = json.loads(data['show_list'])
        for i in range(expect):
            self.assertEqual(show_list[i]['contract_register_status'], status_list[i])

    @ddt.unpack
    @ddt.data(("G3", 0), ("G2-1-1", 1), ("G1-1", 3))
    def test_students_search_students_ajax_group_name(self, param_group_name, expect_num):
        self.setup_user()
        director_manager = self._director_manager
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        groups = Group.objects.filter(org=self.contract_org)
        param = self._create_param_search_students_ajax(group_name=param_group_name)

        for i, group in enumerate(groups):
            register = self._create_user_and_contract_register()
            self._create_member(org=self.contract_org, user=register.user, group=group, code='code' + str(i))

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, expect_num, expect_num)

    @ddt.data('q', 'Query_Length_Sample_123_Query_Length_Sample_123_Query_Length_Sample_123')
    def test_students_search_students_ajax_free_word_user_data(self, param_free_word):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_param_search_students_ajax(free_word=param_free_word)
        self._create_user_and_contract_register(username='username' + param_free_word),
        self._create_user_and_contract_register(email='email' + param_free_word + '@example.com'),
        self._create_user_and_contract_register(first_name='first_name' + param_free_word)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 3, 3)

    @ddt.data('q', 'Query_Length_Sample_123_Query_Length_Sample_123_Query_Length_Sample_123')
    def test_students_search_students_ajax_free_word_member_data(self, param_free_word):
        self.setup_user()
        director_manager = self._director_manager
        search_result_num = 0
        param = self._create_param_search_students_ajax(free_word=param_free_word)
        columns = ['org' + str(i) for i in range(1, 11)]
        columns.extend(['item' + str(i) for i in range(1, 11)])
        for i, column in enumerate(columns):
            search_result_num += 1
            register = self._create_user_and_contract_register()
            self._create_member(
                org=self.contract_org, group=None, code='code' + str(i), user=register.user,
                **dict({column: 'search_' + param_free_word})
            )

            with self.skip_check_course_selection(current_organization=self.contract_org,
                                                  current_contract=self.contract, current_manager=director_manager):
                response = self.client.post(self._url_search_students_ajax, param)

            self.assertEqual(200, response.status_code)
            data = json.loads(response.content)
            self._assert_search_ajax_successful(data, search_result_num, search_result_num)

    @ddt.data('q', 'Query_Length_Sample')
    def test_students_search_students_ajax_free_word_biz_user_data(self, param_free_word):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_param_search_students_ajax(free_word=param_free_word)
        register = self._create_user_and_contract_register()
        BizUserFactory.create(user=register.user, login_code='code' + param_free_word)
        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 1, 1)

    @ddt.data('sample1', 'Sample_123')
    def test_students_search_students_ajax_free_word_group_name(self, param_free_word):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_param_search_students_ajax(free_word=param_free_word)
        register = self._create_user_and_contract_register()
        group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='group_code', group_name='test_group_name' + param_free_word,
            org=self.contract_org, created_by=self.user, modified_by=self.user)
        self._create_member(org=self.contract_org, group=group, code='code_group_name', user=register.user)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 1, 1)

    @ddt.data('', 'exclude', 'only', 'contains')
    def test_students_search_students_ajax_is_delete(self, param_is_delete):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_param_search_students_ajax(member_is_delete=param_is_delete)
        group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='group_code', group_name='test_group_name',
            org=self.contract_org, created_by=self.user, modified_by=self.user)
        # Delete target member
        register1 = self._create_user_and_contract_register(username='username_only_delete_target')
        self._create_member(org=self.contract_org, group=group, code='code_delete_target_member', user=register1.user,
                            is_active=False, is_delete=True)
        self._create_member(org=self.contract_org, group=group, code='code_delete_target_member_backup', user=register1.user,
                            is_active=False, is_delete=False)

        # Active member
        register2 = self._create_user_and_contract_register(username='username_active_and_delete_target')
        self._create_member(org=self.contract_org, group=group, code='code_active_member', user=register2.user)
        self._create_member(org=self.contract_org, group=group, code='code_active_member_old', user=register2.user,
                            is_active=False, is_delete=True)
        self._create_member(org=self.contract_org, group=group, code='code_active_member_backup', user=register2.user,
                            is_active=False, is_delete=False)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        show_list = json.loads(data['show_list'])
        if param_is_delete in ['', 'exclude']:
            self._assert_search_ajax_successful(data, 1, 1)
            self.assertEqual(show_list[0]['user_name'], 'username_active_and_delete_target')
        elif param_is_delete == 'contains':
            self._assert_search_ajax_successful(data, 3, 3)
            self.assertEqual(show_list[0]['user_name'], 'username_only_delete_target')
            self.assertEqual(show_list[1]['user_name'], 'username_active_and_delete_target')
            self.assertEqual(show_list[2]['user_name'], 'username_active_and_delete_target')
        elif param_is_delete == 'only':
            self._assert_search_ajax_successful(data, 2, 2)
            self.assertEqual(show_list[0]['user_name'], 'username_only_delete_target')
            self.assertEqual(show_list[1]['user_name'], 'username_active_and_delete_target')

    @ddt.data('', 'exclude', 'only', 'contains')
    def test_students_search_students_ajax_is_masked(self, param_is_masked):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_param_search_students_ajax(is_masked=param_is_masked)
        # Create masked user(not contains '@' in email)
        self._create_user_and_contract_register(username="username_is_masked", email='Sample_Mask_Email_123')
        # Create not masked user
        self._create_user_and_contract_register(username="username_is_not_masked")

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        show_list = json.loads(data['show_list'])
        if param_is_masked == 'exclude':
            self._assert_search_ajax_successful(data, 1, 1)
            self.assertEqual(show_list[0]['user_name'], 'username_is_not_masked')
        elif param_is_masked in ['', 'contains']:
            self._assert_search_ajax_successful(data, 2, 2)
            self.assertEqual(show_list[0]['user_name'], 'username_is_masked')
            self.assertEqual(show_list[1]['user_name'], 'username_is_not_masked')
        elif param_is_masked == 'only':
            self._assert_search_ajax_successful(data, 1, 1)
            self.assertEqual(show_list[0]['user_name'], 'username_is_masked')

    @ddt.data('sample', 'Sample_Additional_Info_Settings_123')
    def test_students_search_students_ajax_additional_info(self, param_additional_info):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_param_search_students_ajax(free_word=param_additional_info)
        # Create dummy data
        for i in range(10):
            self._create_user_and_contract_register()
        # Create Target data
        register = self._create_user_and_contract_register()
        additional_info = AdditionalInfo.find_by_contract_id(
            contract_id=self.contract.id).filter(display_name='country').first()
        additional_info_setting = AdditionalInfoSetting.objects.get(
            user=register.user, contract=self.contract, display_name=additional_info.display_name)
        additional_info_setting.value = 'search_key_word_' + param_additional_info
        additional_info_setting.save()

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 1, 1)
        show_list = json.loads(data['show_list'])
        self.assertEqual(show_list[0][additional_info.display_name], 'search_key_word_' + param_additional_info)

    @ddt.unpack
    @ddt.data(("", 0), ("G03", 0), ("G02", 5), ("G01-01", 3), ("G02-01-02", 1))
    def test_students_search_students_ajax_manager_right(self, param_group_code, expect_num):
        self.setup_user()
        manager_manager = self._manager_manager
        param = self._create_param_search_students_ajax()
        # Create groups
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        groups = Group.objects.filter(org=self.contract_org)
        # Create member in group
        for i, group in enumerate(groups):
            register = self._create_user_and_contract_register()
            self._create_member(
                org=self.contract_org, group=group, user=register.user, code='code' + str(i))
        # Create member not belong to group
        register = self._create_user_and_contract_register()
        self._create_member(
            org=self.contract_org, group=None, user=register.user, code='code_not_group')

        try:
            group = Group.objects.get(org=self.contract_org, group_code=param_group_code)
            RightFactory.create(org=self.contract_org, group=group, user=manager_manager.user, created_by=self.user,
                                creator_org=self.contract_org)
        except Group.DoesNotExist:
            pass

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=manager_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, expect_num, expect_num)

    @ddt.unpack
    @ddt.data((0, 30), (30, 60), (60, 90))
    def test_students_search_students_ajax_paging(self, param_offset, param_limit):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_param_search_students_ajax(offset=param_offset, limit=param_limit)
        for i in range(100):
            self._create_user_and_contract_register()

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        expect_num = 100
        self._assert_search_ajax_successful(data, expect_num, 30)

    def test_students_download_user(self):
        self.setup_user()
        director_manager = self._director_manager
        for i in range(100):
            self._create_user_and_contract_register()
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        group = Group.objects.get(org=self.contract_org, group_code="G01")
        manager_manager = self._manager_manager
        RightFactory.create(org=self.contract_org, group=group, user=manager_manager.user, created_by=self.user,
                            creator_org=self.contract_org)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            param = self._create_param_search_students_ajax()
            param['current_organization_visible_group_ids'] = group.pk
            response = self.client.post(self._url_students_download, param)
        self.assertEqual(200, response.status_code)

    def test_students_download_member(self):
        self.setup_user()
        # Create groups
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        groups = Group.objects.filter(org=self.contract_org)
        # Create member in group
        for i, group in enumerate(groups):
            register = self._create_user_and_contract_register()
            self._create_member(
                org=self.contract_org, group=group, user=register.user, code='code' + str(i))
        # Create member belong to group
        register = self._create_user_and_contract_register()
        self._create_member(
            org=self.contract_org, group=None, user=register.user, code='code_not_group')
        director_manager = self._director_manager
        manager_manager = self._manager_manager
        right_group = Group.objects.filter(org=self.contract_org).get(group_code='G01')
        RightFactory.create(org=self.contract_org, group=right_group, user=manager_manager.user, created_by=self.user,
                            creator_org=self.contract_org)
        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract, current_manager=director_manager):
            param = self._create_param_search_students_ajax()
            response = self.client.post(self._url_students_download, param)
        self.assertEqual(200, response.status_code)

    def test_another_organization_member(self):
        self.setup_user()
        orgs = [self._create_organization(org_name='org' + str(i)) for i in range(2)]
        user = UserFactory.create()
        contracts = [self._create_contract(contractor_organization=orgs[i]) for i in range(2)]
        registers = [self.create_contract_register(user=user, contract=contracts[i]) for i in range(2)]
        managers = [self._create_manager(org=orgs[i], user=self.user, created=self.contract_org,
                                        permissions=[self.director_permission]) for i in range(2)]
        member = self._create_member(org=orgs[0], user=user, group=None, code='code')

        param = self._create_param_search_students_ajax(contract_id=contracts[0].id)
        with self.skip_check_course_selection(current_organization=orgs[0],
                                              current_contract=contracts[0], current_manager=managers[0]):
            response = self.client.post(self._url_search_students_ajax, param)
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        show_list = json.loads(data['show_list'])
        self._assert_search_ajax_successful(data, 1, 1)
        self.assertEqual(member.code, show_list[0]['code'])

        with self.skip_check_course_selection(current_organization=orgs[1],
                                              current_contract=contracts[1], current_manager=managers[1]):
            response = self.client.post(self._url_search_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        show_list = json.loads(data['show_list'])
        self._assert_search_ajax_successful(data, 1, 1)
        self.assertFalse(hasattr(show_list[0], 'code'))

    def test_students_search_users_belonging_multiple_organizations(self):
        self.setup_user()
        # user1 has member data.
        user1 = UserFactory.create()
        # user1 has not member data.
        user2 = UserFactory.create()

        # create two org and contract
        orgs = [self._create_organization(org_name='org' + str(i)) for i in range(2)]
        contracts = [self._create_contract(contractor_organization=orgs[i]) for i in range(2)]

        # create contract register for user1 and user2
        contract_registers = []
        for _user in [user1, user2]:
            for _contract in contracts:
                contract_registers.append(self.create_contract_register(user=_user, contract=_contract))

        # create member for user1
        user1_members = [self._create_member(org=_org, user=user1, group=None, code='code' + str(i)) for i, _org in enumerate(orgs)]

        managers = [self._create_manager(org=org, user=self.user, created=self.contract_org,
                                        permissions=[self.director_permission]) for org in orgs]

        for i in range(2):
            param = self._create_param_search_students_ajax(contract_id=contracts[i].id)
            with self.skip_check_course_selection(current_organization=orgs[i],
                                                  current_contract=contracts[i], current_manager=managers[i]):
                response = self.client.post(self._url_search_students_ajax, param)

            self.assertEqual(200, response.status_code)
            data = json.loads(response.content)
            show_list = json.loads(data['show_list'])
            self._assert_search_ajax_successful(data, 2, 2)
            for show_item in show_list:
                if show_item['user_email'] == user1.email:
                    self.assertEqual(show_item['code'], user1_members[i].code)
                else:
                    self.assertFalse(show_item['code'])


class ContractOperationViewTestUnregisterStudents(BizContractTestBase):
    @property
    def _director_manager(self):
        return self._create_manager(
            org=self.contract_org, user=self.user, created=self.contract_org, permissions=[self.director_permission])

    def _url_unregister_students_ajax(self):
        return reverse('biz:contract_operation:unregister_students_ajax')

    def test_unregister_get(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=INPUT_INVITATION_CODE)

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.get(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 405)

    def test_unregister_no_param(self):
        self.setup_user()

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {})

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_unregister_contract_unmatch(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=INPUT_INVITATION_CODE)

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract_mooc.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Current contract is changed. Please reload this page.')

    def test_unregister_validate_not_found_register(self):
        self.setup_user()
        register_mooc = ContractRegisterFactory.create(user=self.user, contract=self.contract_mooc, status=INPUT_INVITATION_CODE)

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org,
                                              current_contract=self.contract), patch(
            'biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register_mooc.id]})
            warning_log.assert_called_with('Not found register in contract_id({}) contract_register_id({}), user_id({})'.format(self.contract.id, register_mooc.id, self.user.id))

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_unregister_validate_warning(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=UNREGISTER_INVITATION_CODE)

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['info'], 'Succeed to unregister 0 users.Already unregisterd 1 users.')

    def test_unregister_spoc(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['info'], 'Succeed to unregister 1 users.')

        self.assertEquals(ContractRegister.objects.get(user=self.user, contract=self.contract).status, UNREGISTER_INVITATION_CODE)
        self.assertFalse(CourseEnrollment.is_enrolled(self.user, self.course_spoc1.id))
        self.assertFalse(CourseEnrollment.is_enrolled(self.user, self.course_spoc2.id))

    def test_unregister_mooc(self):
        self.setup_user()
        register_mooc = ContractRegisterFactory.create(user=self.user, contract=self.contract_mooc, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_mooc1.id)

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org,
                                              current_contract=self.contract_mooc):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract_mooc.id, 'target_list': [register_mooc.id]})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['info'], 'Succeed to unregister 1 users.')

        self.assertEquals(ContractRegister.objects.get(user=self.user, contract=self.contract_mooc).status, UNREGISTER_INVITATION_CODE)
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_mooc1.id))

    def test_personalinfo_mask_validate_task_error(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)

        with self.skip_check_course_selection(
                current_manager=self._director_manager, current_organization=self.contract_org,
                current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEquals(ERROR_MSG, data['error'])

    def test_unregister_spoc_staff(self):
        self.setup_user()
        # to be staff
        self.user.is_staff = True
        self.user.save()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['info'], 'Succeed to unregister 1 users.')

        self.assertEquals(ContractRegister.objects.get(user=self.user, contract=self.contract).status, UNREGISTER_INVITATION_CODE)
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc1.id))
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc2.id))

    def test_unregister_db_error(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org, current_contract=self.contract), \
            patch('biz.djangoapps.ga_contract_operation.views.log.exception') as exception_log, \
            patch('biz.djangoapps.ga_contract_operation.views.ContractRegister.save', side_effect=IntegrityError()):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})
            exception_log.assert_called_with('Can not unregister. contract_id({}), unregister_list({})'.format(self.contract.id, [register.id]))

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Failed to batch unregister. Please operation again after a time delay.')

        self.assertEquals(ContractRegister.objects.get(user=self.user, contract=self.contract).status, REGISTER_INVITATION_CODE)
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc1.id))
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc2.id))


@ddt.ddt
class ContractOperationViewTestPersonalInfoMask(BizContractTestBase):
    @property
    def _director_manager(self):
        return self._create_manager(
            org=self.contract_org, user=self.user, created=self.contract_org, permissions=[self.director_permission])

    @property
    def _url_personalinfo_mask(self):
        return reverse('biz:contract_operation:personalinfo_mask')

    def test_personalinfo_mask_not_allowed_method(self):
        response = self.client.get(self._url_personalinfo_mask)
        self.assertEqual(405, response.status_code)

    def test_personalinfo_mask_submit_successful(self):
        """
        Tests success to submit. Processing of task is tested in test_tasks.py
        """
        registers = [
            self.create_contract_register(UserFactory.create(), self.contract),
            self.create_contract_register(UserFactory.create(), self.contract),
        ]
        params = {'target_list': [register.id for register in registers], 'contract_id': self.contract.id}

        self.setup_user()

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_personalinfo_mask, params)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Personal Information Mask.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('personalinfo_mask', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)
        self.assertItemsEqual(registers, [target.register for target in history.contracttasktarget_set.all()])

    def test_personalinfo_mask_submit_duplicated(self):
        registers = [
            self.create_contract_register(UserFactory.create(), self.contract),
            self.create_contract_register(UserFactory.create(), self.contract),
        ]
        params = {'target_list': [register.id for register in registers], 'contract_id': self.contract.id}
        TaskFactory.create(task_type='personalinfo_mask', task_key=hashlib.md5(str(self.contract.id)).hexdigest())

        self.setup_user()

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org,
                                              current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = None
            response = self.client.post(self._url_personalinfo_mask, params)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Processing of Personal Information Mask is running.Execution status, please check from the task history.", data['error'])
        # assert not to be created new Task instance.
        self.assertEqual(1, Task.objects.count())

    def test_personalinfo_mask_validate_task_error(self):
        registers = [
            self.create_contract_register(UserFactory.create(), self.contract),
            self.create_contract_register(UserFactory.create(), self.contract),
        ]
        params = {'target_list': [register.id for register in registers], 'contract_id': self.contract.id}
        TaskFactory.create(task_type='personalinfo_mask', task_key=hashlib.md5(str(self.contract.id)).hexdigest())

        self.setup_user()

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org,
                                              current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            response = self.client.post(self._url_personalinfo_mask, params)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(ERROR_MSG, data['error'])

    @ddt.data('target_list', 'contract_id')
    def test_personalinfo_mask_missing_params(self, param):
        params = {'target_list': [1, 2], 'contract_id': 1, }
        del params[param]

        self.setup_user()
        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_personalinfo_mask, params)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Unauthorized access.", data['error'])

    def test_personalinfo_mask_contract_unmatch(self):
        params = {'target_list': [1, 2], 'contract_id': self.contract_mooc.id, }

        self.setup_user()
        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_personalinfo_mask, params)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Current contract is changed. Please reload this page.", data['error'])

    def test_personalinfo_mask_register_unmatch(self):
        registers = [
            self.create_contract_register(UserFactory.create(), self.contract),
            self.create_contract_register(UserFactory.create(), self.contract_mooc),
        ]
        params = {'target_list': [register.id for register in registers], 'contract_id': self.contract.id, }

        self.setup_user()

        with self.skip_check_course_selection(current_manager=self._director_manager,
                                              current_organization=self.contract_org,
                                              current_contract=self.contract), patch(
            'biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_personalinfo_mask, params)

        warning_log.assert_called_with(
            "Not found register in contract_id({}) contract_register_id({}), user_id({})".format(
                self.contract.id, registers[1].id, registers[1].user_id
            )
        )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

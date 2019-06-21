# -*- coding: utf-8 -*-
"""
Test for save_register_condition feature
"""
import freezegun
import ddt
import json
from mock import patch
from collections import OrderedDict
from datetime import datetime, timedelta
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils.translation import ugettext as _
from biz.djangoapps.ga_contract.models import ContractOption
from biz.djangoapps.ga_contract.tests.factories import ContractOptionFactory, AdditionalInfoFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from biz.djangoapps.gx_save_register_condition.tests.factories import (
    ParentConditionFactory, ChildConditionFactory, ReflectConditionTaskHistory)
from biz.djangoapps.gx_save_register_condition.models import ParentCondition, ChildCondition
from biz.djangoapps.gx_save_register_condition.tests.factories import ReflectConditionTaskHistoryFactory
from openedx.core.djangoapps.ga_task.tests.factories import TaskFactory
from openedx.core.lib.ga_datetime_utils import to_timezone
from student.tests.factories import UserFactory


@ddt.ddt
class SaveRegisterConditionViewTest(BizContractTestBase):

    def _create_member(self, org, group, user, code, is_active=True, is_delete=False, **kwargs):
        return MemberFactory.create(
            org=org, group=group, user=user, code=code,
            created_by=user, creator_org=org,
            updated_by=user, updated_org=org,
            is_active=is_active,
            is_delete=is_delete,
            **kwargs
        )

    def _create_one_condition(self):
        parent = ParentConditionFactory.create(
            contract_id=self.contract.id,
            parent_condition_name='test parent name',
            setting_type='1',
            created=datetime.now(),
            created_by_id=self.user.id
        )
        child = ChildConditionFactory.create(
            contract=self.contract,
            parent_condition_id=parent.id,
            parent_condition_name='test parent name',
            comparison_target='test',
            comparison_type=1,
            comparison_string='test')
        return parent, child

    def _create_parent_condition(self, parent_name):
        return ParentConditionFactory.create(
            contract_id=self.contract.id,
            parent_condition_name=parent_name,
            setting_type='1',
            created=datetime.now(),
            created_by_id=self.user.id
        )

    def _create_child_condition(self, contract_id, parent_condition_id, condition_name, comparison_list):
        for condition in comparison_list:
            ChildConditionFactory.create(
                contract_id=contract_id,
                parent_condition_id=parent_condition_id,
                parent_condition_name=condition_name,
                comparison_target=condition['target'],
                comparison_type=int(condition['type']),
                comparison_string=condition['string']
            )

    def _get_setting_type_list(self):
        return [1, 1, 2, 2, 2, 2, 2, 2]

    def _get_comparison_list(self):
        comparison_list = [
            [
                {'target': 'username', 'type': 1, 'string': 'test_string1-1'}
            ], [
                {'target': 'username', 'type': 1, 'string': 'test_string2-1'},
                {'target': 'email', 'type': 1, 'string': 'test_string2-2'}
            ], [
                {'target': 'username', 'type': 2, 'string': 'test_string3-1'},
                {'target': 'email', 'type': 3, 'string': 'test_string3-2'},
                {'target': 'code', 'type': 4, 'string': 'test_string3-3'}
            ], [
                {'target': 'username', 'type': 1, 'string': 'test_string4-1'},
                {'target': 'email', 'type': 2, 'string': 'test_string4-2'},
                {'target': 'code', 'type': 3, 'string': 'test_string4-3'},
                {'target': 'other1', 'type': 4, 'string': 'test_string4-4'}
            ], [
                {'target': 'username', 'type': 2, 'string': 'test_string5-1'},
                {'target': 'email', 'type': 3, 'string': 'test_string5-2'},
                {'target': 'code', 'type': 4, 'string': 'test_string5-3'},
                {'target': 'login_code', 'type': 5, 'string': 'test_string5-4'},
                {'target': 'group_name', 'type': 6, 'string': 'test_string5-5'}
            ], [
                {'target': 'org1', 'type': 1, 'string': 'test_string6-1'},
                {'target': 'org2', 'type': 2, 'string': 'test_string6-2'},
                {'target': 'org3', 'type': 3, 'string': 'test_string6-3'},
                {'target': 'org4', 'type': 4, 'string': 'test_string6-4'},
                {'target': 'org5', 'type': 5, 'string': 'test_string6-5'},
                {'target': 'org6', 'type': 6, 'string': 'test_string6-6'},
                {'target': 'org7', 'type': 1, 'string': 'test_string6-7'},
                {'target': 'org8', 'type': 1, 'string': 'test_string6-8'},
                {'target': 'org9', 'type': 7, 'string': 'a,b,c,d,e'},
                {'target': 'org10', 'type': 8, 'string': 'f,g,h,i,j'}
            ], [
                {'target': 'item1', 'type': 1, 'string': 'test_string7-1'},
                {'target': 'item2', 'type': 2, 'string': 'test_string7-2'},
                {'target': 'item3', 'type': 3, 'string': 'test_string7-2'},
                {'target': 'item4', 'type': 4, 'string': 'test_string7-2'},
                {'target': 'item5', 'type': 5, 'string': 'test_string7-2'},
                {'target': 'item6', 'type': 6, 'string': 'test_string7-2'},
                {'target': 'item7', 'type': 1, 'string': 'test_string7-2'},
                {'target': 'item8', 'type': 1, 'string': 'test_string7-2'},
                {'target': 'item9', 'type': 7, 'string': 'k,l,m,n,o'},
                {'target': 'item10', 'type': 8, 'string': 'p,q,r,s,t'}
            ], [
                {'target': 'other2', 'type': 1, 'string': 'test_string8-1'}
            ]
        ]
        return comparison_list

    @property
    def _url_index(self):
        return reverse("biz:save_register_condition:index")

    @property
    def _search_target(self):
        return reverse("biz:save_register_condition:search_target_ajax")

    @property
    def _add_condition_view(self):
        return reverse("biz:save_register_condition:add_condition_ajax")

    @property
    def _delete_condition(self):
        return reverse("biz:save_register_condition:delete_condition_ajax")

    @property
    def _get_active_condition_num_without_one(self):
        return reverse("biz:save_register_condition:get_active_condition_num_without_one_ajax")

    @property
    def _copy_condition(self):
        return reverse("biz:save_register_condition:copy_condition_ajax")

    @property
    def _url_detail(self):
        return reverse("biz:save_register_condition:detail")

    @property
    def _reflect_condition(self):
        return reverse("biz:save_register_condition:reflect_condition_ajax")

    @property
    def _task_history(self):
        return reverse("biz:save_register_condition:task_history_ajax")

    @property
    def _update_auto_register_students_flg(self):
        return reverse("biz:save_register_condition:update_auto_register_students_flg")

    @property
    def _reservation_date(self):
        return reverse("biz:save_register_condition:reservation_date_ajax")

    @property
    def _cancel_reservation_date(self):
        return reverse("biz:save_register_condition:cancel_reservation_date_ajax")

    def _detail_view(self, condition_id):
        return reverse('biz:save_register_condition:detail', kwargs={'condition_id': condition_id})

    @property
    def _detail_search_target(self):
        return reverse("biz:save_register_condition:detail_search_target_ajax")

    @property
    def _detail_simple_save_condition(self):
        return reverse("biz:save_register_condition:detail_simple_save_condition_ajax")

    @property
    def _detail_advanced_save_condition(self):
        return reverse("biz:save_register_condition:detail_advanced_save_condition_ajax")

    def setUp(self):
        """
        Set up for test
        """
        super(SaveRegisterConditionViewTest, self).setUp()
        self.setup_user()

        self._director_manager = self._create_manager(
            org=self.contract_org,
            user=self.user,
            created=self.contract_org,
            permissions=[self.director_permission]
        )

    """
    index
    """

    def test_index(self):
        # Create parent condition
        for i in range(0, 10):
            self._create_parent_condition('test parent name' + str(i + 1))

        # Request
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            with patch('biz.djangoapps.gx_save_register_condition.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                response = self.client.get(self._url_index)

        # Assertion
        self.assertEqual(200, response.status_code)
        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'gx_save_register_condition/index.html')
        self.assertEqual(render_to_response_args[1]['show_p_condition_list'], json.dumps([
            {"id": 1, "parent_condition_name": "test parent name1"},
            {"id": 2, "parent_condition_name": "test parent name2"},
            {"id": 3, "parent_condition_name": "test parent name3"},
            {"id": 4, "parent_condition_name": "test parent name4"},
            {"id": 5, "parent_condition_name": "test parent name5"},
            {"id": 6, "parent_condition_name": "test parent name6"},
            {"id": 7, "parent_condition_name": "test parent name7"},
            {"id": 8, "parent_condition_name": "test parent name8"},
            {"id": 9, "parent_condition_name": "test parent name9"},
            {"id": 10, "parent_condition_name": "test parent name10"}
        ]))
        self.assertEqual(7, render_to_response_args[1]['search_other_condition_list'].count())
        self.assertEqual(render_to_response_args[1]['auto_register_students_flag'], False)
        self.assertEqual(render_to_response_args[1]['auto_register_reservation_date'], '')

    @ddt.data(False, True)
    def test_index_auto_register_students_flag(self, default_param):
        ContractOptionFactory.create(contract=self.contract, auto_register_students_flg=default_param)

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            with patch('biz.djangoapps.gx_save_register_condition.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                response = self.client.get(self._url_index)

        self.assertEqual(200, response.status_code)
        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(
            render_to_response_args[1]['auto_register_students_flag'], default_param)

    @ddt.unpack
    @ddt.data((None, ''), ('2000/02/02', datetime.strptime('2000/02/02', '%Y/%m/%d')))
    def test_index_auto_register_reservation_date(self, default_param, expected):
        if default_param is None:
            ContractOptionFactory.create(
                contract=self.contract, auto_register_reservation_date=default_param)
        else:
            ContractOptionFactory.create(
                contract=self.contract, auto_register_reservation_date=datetime.strptime(default_param, '%Y/%m/%d'))

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            with patch('biz.djangoapps.gx_save_register_condition.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                response = self.client.get(self._url_index)

        self.assertEqual(200, response.status_code)
        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[1]['auto_register_reservation_date'], expected)

    def test_index_no_condition(self):
        # Request
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.get(self._url_index)

        # Assertion
        parent_condition = ParentCondition.objects.filter(contract=self.contract)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, parent_condition.count())

    def test_detail_unauthorized_access_no_record(self):
        condition_id = '0'
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            with patch('biz.djangoapps.gx_save_register_condition.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                path = self._detail_view(condition_id)
                response = self.client.get(path)

        self.assertEqual(200, response.status_code)
        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'static_templates/404.html')

    """
    detail
    """

    def test_detail(self):
        # Create User
        test_user_list = []
        for i in range(1, 14):
            test_user = UserFactory.create()
            test_user_list.append(test_user)

        # Create Member
        member_list = [
                {'org1': '', 'org2': '', 'org3': '', 'org4': '', 'org5': '', 'org6': '', 'org7': '', 'org8': '', 'org9': '', 'org10': '',
                 'item1': '', 'item2': '', 'item3': '', 'item4': '', 'item5': '', 'item6': '', 'item7': '', 'item8': '', 'item9': '', 'item10': ''},
                {'org1': 'testorg1_1', 'org2': 'testorg2_1', 'org3': 'testorg3_1', 'item1': 'testitem1_1', 'item2': 'testitem2_1', 'item3': 'testitem3_1'},
                {'org1': 'testorg1_1', 'org2': 'testorg2_1', 'org3': 'testorg3_1', 'item1': 'testitem1_1', 'item2': 'testitem2_1', 'item3': 'testitem3_1'},
                {'org1': 'testorg1_2', 'org2': 'testorg2_2', 'org3': 'testorg3_2', 'item1': 'testitem1_2', 'item2': 'testitem2_2', 'item3': 'testitem3_2'},
                {'org1': 'testorg1_3', 'org2': 'testorg2_3', 'org3': 'testorg3_3', 'item1': 'testitem1_3', 'item2': 'testitem2_3', 'item3': 'testitem3_3'},
                {'org4': 'testorg4_1', 'org5': 'testorg5_1', 'org6': 'testorg6_1', 'item4': 'testitem4_1', 'item5': 'testitem5_1', 'item6': 'testitem6_1'},
                {'org4': 'testorg4_1', 'org5': 'testorg5_1', 'org6': 'testorg6_1', 'item4': 'testitem4_1', 'item5': 'testitem5_1', 'item6': 'testitem6_1'},
                {'org4': 'testorg4_2', 'org5': 'testorg5_2', 'org6': 'testorg6_2', 'item4': 'testitem4_2', 'item5': 'testitem5_2', 'item6': 'testitem6_2'},
                {'org4': 'testorg4_3', 'org5': 'testorg5_3', 'org6': 'testorg6_3', 'item4': 'testitem4_3', 'item5': 'testitem5_3', 'item6': 'testitem6_3'},
                {'org7': 'testorg7_1', 'org8': 'testorg8_1', 'org9': 'testorg9_1', 'org10': 'testorg10_1', 'item7': 'testitem7_1', 'item8': 'testitem8_1', 'item9': 'testitem9_1', 'item10': 'testitem10_1'},
                {'org7': 'testorg7_1', 'org8': 'testorg8_1', 'org9': 'testorg9_1', 'org10': 'testorg10_1', 'item7': 'testitem7_1', 'item8': 'testitem8_1', 'item9': 'testitem9_1', 'item10': 'testitem10_1'},
                {'org7': 'testorg7_2', 'org8': 'testorg8_2', 'org9': 'testorg9_2', 'org10': 'testorg10_2', 'item7': 'testitem7_2', 'item8': 'testitem8_2', 'item9': 'testitem9_2', 'item10': 'testitem10_2'},
                {'org7': 'testorg7_3', 'org8': 'testorg8_3', 'org9': 'testorg9_3', 'org10': 'testorg10_3', 'item7': 'testitem7_3', 'item8': 'testitem8_3', 'item9': 'testitem9_3', 'item10': 'testitem10_3'}
        ]
        for i, member in enumerate(member_list):
            self._create_member(
                org=self.contract_org, group=None, user=test_user_list[i],
                code='sample', **dict(member)
            )

        # Create Group
        group_list = ['test_group_name1', 'test_group_name1', 'test_group_name2', 'test_group_name3', '']
        for value in group_list:
            GroupFactory.create(
                parent_id=0, level_no=0, group_code='0', group_name=value,
                notes='0', created=datetime.now(), created_by_id=self.user.id, org_id=self.contract_org.id
            )

        # Create self parent and child condition
        setting_type_list = self._get_setting_type_list()
        all_comparison_list = self._get_comparison_list()

        parent_condition_id = ''
        for i, parent in enumerate(setting_type_list):
            created_parent_condition = ParentConditionFactory.create(
                contract=self.contract,
                parent_condition_name='test parent name' + str(i + 1),
                setting_type=parent,
                created_by_id=self.user.id)

            if i == 5:
                parent_condition_id = created_parent_condition.id
                parent_condition_name = created_parent_condition.parent_condition_name

            self._create_child_condition(
                self.contract.id,
                created_parent_condition.id,
                created_parent_condition.parent_condition_name,
                all_comparison_list[i])

        # Create additionalinfo
        additionalinfo_list = ['test_additionalinfo1', 'test_additionalinfo2', 'test_additionalinfo3']
        for value in additionalinfo_list:
            AdditionalInfoFactory.create(display_name=value, contract_id=self.contract.id)

        # Request
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            with patch('biz.djangoapps.gx_save_register_condition.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                path = self._detail_view(parent_condition_id)
                response = self.client.get(path)

        ans_org_selection_list = [
            [u'testorg1_1', u'testorg1_2', u'testorg1_3'],
            [u'testorg2_1', u'testorg2_2', u'testorg2_3'],
            [u'testorg3_1', u'testorg3_2', u'testorg3_3'],
            [u'testorg4_1', u'testorg4_2', u'testorg4_3'],
            [u'testorg5_1', u'testorg5_2', u'testorg5_3'],
            [u'testorg6_1', u'testorg6_2', u'testorg6_3'],
            [u'testorg7_1', u'testorg7_2', u'testorg7_3'],
            [u'testorg8_1', u'testorg8_2', u'testorg8_3'],
            [u'testorg9_1', u'testorg9_2', u'testorg9_3'],
            [u'testorg10_1', u'testorg10_2', u'testorg10_3']]

        ans_item_selection_list = [
            [u'testitem1_1', u'testitem1_2', u'testitem1_3'],
            [u'testitem2_1', u'testitem2_2', u'testitem2_3'],
            [u'testitem3_1', u'testitem3_2', u'testitem3_3'],
            [u'testitem4_1', u'testitem4_2', u'testitem4_3'],
            [u'testitem5_1', u'testitem5_2', u'testitem5_3'],
            [u'testitem6_1', u'testitem6_2', u'testitem6_3'],
            [u'testitem7_1', u'testitem7_2', u'testitem7_3'],
            [u'testitem8_1', u'testitem8_2', u'testitem8_3'],
            [u'testitem9_1', u'testitem9_2', u'testitem9_3'],
            [u'testitem10_1', u'testitem10_2', u'testitem10_3']]

        ans_target_list = (('username', u'Username'), ('email', u'Email Address'), ('login_code', u'Login Code'),
                           ('code', u'Member Code'), ('group_name', u'Organization Group Name'), ('org1', u'Organization1'),
                           ('org2', u'Organization2'), ('org3', u'Organization3'), ('org4', u'Organization4'),
                           ('org5', u'Organization5'), ('org6', u'Organization6'), ('org7', u'Organization7'),
                           ('org8', u'Organization8'), ('org9', u'Organization9'), ('org10', u'Organization10'),
                           ('item1', u'Item1'), ('item2', u'Item2'), ('item3', u'Item3'), ('item4', u'Item4'),
                           ('item5', u'Item5'), ('item6', u'Item6'), ('item7', u'Item7'), ('item8', u'Item8'),
                           ('item9', u'Item9'), ('item10', u'Item10'))

        # Name
        expect_comparison_type_name = OrderedDict()
        expect_comparison_type_name[1] = _('Comparison Equal')
        expect_comparison_type_name[2] = _('Comparison Not Equal')
        expect_comparison_type_name[3] = _('Comparison Contains')
        expect_comparison_type_name[4] = _('Comparison Not Contains')
        expect_comparison_type_name[5] = _('Comparison Starts With')
        expect_comparison_type_name[6] = _('Comparison Ends With')
        expect_comparison_type_name[7] = _('Comparison Equal In')
        expect_comparison_type_name[8] = _('Comparison Not Equal In')

        ans_additional_info_list = [
            u'country', u'dept', u'test_additionalinfo1', u'test_additionalinfo2', u'test_additionalinfo3']

        # Assertion
        self.assertEqual(200, response.status_code)
        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], "gx_save_register_condition/detail.html")
        self.assertEqual(render_to_response_args[1]['condition_id'], parent_condition_id)
        self.assertEqual(render_to_response_args[1]['parent_condition_name'], parent_condition_name)
        self.assertEqual(render_to_response_args[1]['setting_type'], 2)
        self.assertEqual((render_to_response_args[1]['group_list']).count(), 5)
        self.assertEqual(render_to_response_args[1]['org_selection_list'], ans_org_selection_list)
        self.assertEqual(render_to_response_args[1]['item_selection_list'], ans_item_selection_list)
        self.assertEqual(render_to_response_args[1]['target_list'], ans_target_list)
        self.assertEqual(render_to_response_args[1]['comparison_type_list'], expect_comparison_type_name)
        self.assertEqual(render_to_response_args[1]['additional_info_list'], ans_additional_info_list)
        self.assertEqual(10, ChildCondition.objects.filter(parent_condition_id=parent_condition_id).count())

    """
    add_condition_ajax
    """
    def test_add_condition_unauthorized_access_null(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._add_condition_view, {})

        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_add_condition(self):
        # Create parent condition
        max_condition = 5
        for i in range(0, max_condition):
            self._create_parent_condition('test parent name' + str(i + 1))

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._add_condition_view, {'contract_id': self.contract.id})

        # Assertion
        parent_condition = ParentCondition.objects.filter(contract=self.contract)
        self.assertEqual(200, response.status_code)
        self.assertEqual(max_condition + 1, parent_condition.count())

    """
    delete_condition_ajax
    """
    def test_delete_condition_ajax_unauthorized_access(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._delete_condition, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    @freezegun.freeze_time('2000-01-01 00:00:00')
    @ddt.data('', '1')
    def test_delete_condition_ajax_reset_reservation_settings(self, param_reset_reservation_settings):
        # Set auto_register_students_flg and auto_register_reservation_date
        _now = datetime.now()
        ContractOptionFactory.create(
            contract=self.contract, auto_register_students_flg=True, auto_register_reservation_date=_now)

        created_parent_condition = ParentConditionFactory.create(
            contract=self.contract,
            parent_condition_name='test parent name1',
            setting_type=1,
            created_by_id=self.user.id)

        # Request
        param = {
            'contract_id': self.contract.id,
            'condition_id': created_parent_condition.id,
            'reset_reservation_settings': param_reset_reservation_settings
        }
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._delete_condition, param)

        # Assertion
        option = ContractOption.objects.get(contract=self.contract)
        if not param_reset_reservation_settings:
            self.assertEqual(True, option.auto_register_students_flg)
            self.assertNotEqual(None, option.auto_register_reservation_date)
        else:
            self.assertEqual(False, option.auto_register_students_flg)
            self.assertEqual(None, option.auto_register_reservation_date)

    def test_delete_condition_ajax(self):
        # Create self parent and child condition
        setting_type_list = self._get_setting_type_list()
        all_comparison_list = self._get_comparison_list()

        delete_condition_id = ''

        for i, parent in enumerate(setting_type_list):
            created_parent_condition = ParentConditionFactory.create(
                contract=self.contract,
                parent_condition_name='test parent name' + str(i + 1),
                setting_type=parent,
                created_by_id=self.user.id)

            if i == 5:
                delete_condition_id = created_parent_condition.id

            self._create_child_condition(
                self.contract.id,
                created_parent_condition.id,
                created_parent_condition.parent_condition_name,
                all_comparison_list[i])

        # Request
        param = {
            'contract_id': self.contract.id,
            'condition_id': delete_condition_id,
            'reset_reservation_settings': False
        }
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._delete_condition, param)

        # Assertion
        all_parent_condition = ParentCondition.objects.filter(contract=self.contract)
        all_child_condition = ChildCondition.objects.filter(contract=self.contract)
        deleted_parent_condition = ParentCondition.objects.filter(id=delete_condition_id, contract=self.contract)
        deleted_child_condition = ChildCondition.objects.filter(
            parent_condition_id=delete_condition_id,
            contract=self.contract
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(7, all_parent_condition.count())
        self.assertEqual(26, all_child_condition.count())
        self.assertEqual(0, deleted_parent_condition.count())
        self.assertEqual(0, deleted_child_condition.count())

        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Success')
        self.assertEqual(data['conditions'], [
            {"id": 1, "parent_condition_name": "test parent name1"},
            {"id": 2, "parent_condition_name": "test parent name2"},
            {"id": 3, "parent_condition_name": "test parent name3"},
            {"id": 4, "parent_condition_name": "test parent name4"},
            {"id": 5, "parent_condition_name": "test parent name5"},
            {"id": 7, "parent_condition_name": "test parent name7"},
            {"id": 8, "parent_condition_name": "test parent name8"}
        ])

    """
    copy_condition_ajax
    """
    def test_copy_condition_unauthorized_access(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._copy_condition, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_copy_condition(self):
        # Create self parent and child condition
        setting_type_list = [1, 1, 1, 1, 1, 2, 2, 2, 2, 2]
        comparison_list = [
            {'target': 'login_code', 'type': 1, 'string': 'before1'},
            {'target': 'username', 'type': 1, 'string': 'before2'},
            {'target': 'email', 'type': 1, 'string': 'before3'}
        ]

        for i, child in enumerate(setting_type_list):
            created_parent_condition = ParentConditionFactory.create(
                contract=self.contract,
                parent_condition_name='test parent name' + str(i + 1),
                setting_type=child,
                created_by_id=self.user.id)

            self._create_child_condition(
                self.contract.id,
                created_parent_condition.id,
                created_parent_condition.parent_condition_name,
                comparison_list)

        # Create copy_original parent and child condition
        copy_contract_id = 300
        setting_type_list = self._get_setting_type_list()
        all_comparison_list = self._get_comparison_list()

        for i, child in enumerate(setting_type_list):
            created_parent_condition = ParentCondition.objects.create(
                contract_id=copy_contract_id,
                parent_condition_name='test parent name' + str(i + 1),
                setting_type=child,
                created_by_id=self.user.id)

            self._create_child_condition(
                copy_contract_id,
                created_parent_condition.id,
                created_parent_condition.parent_condition_name,
                all_comparison_list[i])

        # Request
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(
                self._copy_condition, {'contract_id': self.contract.id, 'copy_contract_id': copy_contract_id})

        # Assertion
        parent_condition = ParentCondition.objects.filter(contract=self.contract)
        child_condition = ChildCondition.objects.filter(contract=self.contract)
        self.assertEqual(200, response.status_code)
        self.assertEqual(8, parent_condition.count())
        self.assertEqual(31, child_condition.count())

        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Success')
        no_copy_parent_name_list = ['test parent name4', 'test parent name8']
        self.assertEqual(data['no_copy_parents'], no_copy_parent_name_list)


    """
    detail_simple_save_condition_ajax
    """

    def test_detail_simple_save_condition_transaction_check(self):
        # Create self parent and child condition
        setting_type_list = [2, 1, 2]
        comparison_list = [
            [
                {'target': 'login_code', 'type': 2, 'string': 'before1'},
                {'target': 'username', 'type': 3, 'string': 'before2'},
                {'target': 'email', 'type': 4, 'string': 'before3'}
            ],
            [
                {'target': 'login_code', 'type': 1, 'string': 'before4'},
                {'target': 'username', 'type': 1, 'string': 'before5'},
                {'target': 'email', 'type': 1, 'string': 'before6'}
            ],
            [
                {'target': 'login_code', 'type': 5, 'string': 'before7'},
                {'target': 'username', 'type': 6, 'string': 'before8'},
                {'target': 'email', 'type': 7, 'string': 'before9'}
            ]]

        p_id = ''
        p_name = ''
        for i, child in enumerate(setting_type_list):
            created_parent_condition = ParentConditionFactory.create(
                contract=self.contract,
                parent_condition_name='test parent name' + str(i + 1),
                setting_type=child,
                created_by_id=self.user.id)

            self._create_child_condition(
                self.contract.id,
                created_parent_condition.id,
                created_parent_condition.parent_condition_name,
                comparison_list[i])

            if i == 2:
                p_id = created_parent_condition.id
                p_name = created_parent_condition.parent_condition_name

        condition_data = [
            {'target': 'org1', 'type': 1, 'string': 'after1'},
            {'target': 'org2', 'type': 1, 'string': 'after2'},
            {'target': 'org3', 'type': 1, 'string': 'after3'}
        ]
        # Request
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            with patch('biz.djangoapps.gx_save_register_condition.views._delete_c_condition', side_effect=Exception()):
                response = self.client.post(
                    self._detail_simple_save_condition, {'condition_data': json.dumps(condition_data),
                                                         'parent_condition_id': p_id,
                                                         'condition_name': p_name})

        child_condition_a = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after1')
        child_condition_b = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after2')
        child_condition_c = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after3')

        self.assertEqual(0, child_condition_a.count())
        self.assertEqual(0, child_condition_b.count())
        self.assertEqual(0, child_condition_c.count())

    def test_detail_simple_save_condition(self):
        # Create self parent and child condition
        setting_type_list = [2, 1, 2]
        comparison_list = [
            [
                {'target': 'login_code', 'type': 2, 'string': 'before1'},
                {'target': 'username', 'type': 3, 'string': 'before2'},
                {'target': 'email', 'type': 4, 'string': 'before3'}
            ],
            [
                {'target': 'login_code', 'type': 1, 'string': 'before4'},
                {'target': 'username', 'type': 1, 'string': 'before5'},
                {'target': 'email', 'type': 1, 'string': 'before6'}
            ],
            [
                {'target': 'login_code', 'type': 5, 'string': 'before7'},
                {'target': 'username', 'type': 6, 'string': 'before8'},
                {'target': 'email', 'type': 7, 'string': 'before9'}
             ]]

        p_id = ''
        p_name = ''
        for i, child in enumerate(setting_type_list):
            created_parent_condition = ParentConditionFactory.create(
                contract=self.contract,
                parent_condition_name='test parent name' + str(i + 1),
                setting_type=child,
                created_by_id=self.user.id)

            self._create_child_condition(
                self.contract.id,
                created_parent_condition.id,
                created_parent_condition.parent_condition_name,
                comparison_list[i])

            if i == 2:
                p_id = created_parent_condition.id
                p_name = created_parent_condition.parent_condition_name

        condition_data = [
            {'target': 'org1', 'type': 1, 'string': 'after1'},
            {'target': 'org2', 'type': 1, 'string': 'after2'},
            {'target': 'org3', 'type': 1, 'string': 'after3'}
        ]
        # Request
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(
                self._detail_simple_save_condition, {'condition_data': json.dumps(condition_data),
                                                     'parent_condition_id': p_id,
                                                     'condition_name': p_name})

        child_condition_a = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after1')
        child_condition_b = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after2')
        child_condition_c = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after3')

        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Success')
        self.assertEqual(1, child_condition_a.count())
        self.assertEqual(1, child_condition_b.count())
        self.assertEqual(1, child_condition_c.count())

    """
    detail_advanced_save_condition_ajax
    """

    def test_detail_advanced_save_condition_transaction_check(self):
        # Create self parent and child condition
        setting_type_list = [1, 2, 1]
        comparison_list = [
            [
                {'target': 'login_code', 'type': 1, 'string': 'before1'},
                {'target': 'username', 'type': 1, 'string': 'before2'},
                {'target': 'email', 'type': 1, 'string': 'before3'}
            ],
            [
                {'target': 'login_code', 'type': 2, 'string': 'before4'},
                {'target': 'username', 'type': 3, 'string': 'before5'},
                {'target': 'email', 'type': 4, 'string': 'before6'}
            ],
            [
                {'target': 'login_code', 'type': 1, 'string': 'before7'},
                {'target': 'username', 'type': 1, 'string': 'before8'},
                {'target': 'email', 'type': 1, 'string': 'before9'}
            ]]

        p_id = ''
        p_name = ''
        for i, child in enumerate(setting_type_list):
            created_parent_condition = ParentConditionFactory.create(
                contract=self.contract,
                parent_condition_name='test parent name' + str(i + 1),
                setting_type=child,
                created_by_id=self.user.id)

            self._create_child_condition(
                self.contract.id,
                created_parent_condition.id,
                created_parent_condition.parent_condition_name,
                comparison_list[i])

            if i == 2:
                p_id = created_parent_condition.id
                p_name = created_parent_condition.parent_condition_name

        condition_data = [
            {'target': 'org1', 'type': 5, 'string': 'after1'},
            {'target': 'org2', 'type': 6, 'string': 'after2'},
            {'target': 'org3', 'type': 7, 'string': 'after3'}
        ]
        # Request
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            with patch('biz.djangoapps.gx_save_register_condition.views._delete_c_condition', side_effect=Exception()):
                response = self.client.post(
                    self._detail_advanced_save_condition, {'condition_data': json.dumps(condition_data),
                                                           'parent_condition_id': p_id,
                                                           'condition_name': p_name})

        child_condition_a = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after1')
        child_condition_b = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after2')
        child_condition_c = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after3')

        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Success')
        self.assertEqual(0, child_condition_a.count())
        self.assertEqual(0, child_condition_b.count())
        self.assertEqual(0, child_condition_c.count())

    def test_detail_advanced_save_condition(self):
        # Create self parent and child condition
        setting_type_list = [1, 2, 1]
        comparison_list = [
            [
                {'target': 'login_code', 'type': 1, 'string': 'before1'},
                {'target': 'username', 'type': 1, 'string': 'before2'},
                {'target': 'email', 'type': 1, 'string': 'before3'}
            ],
            [
                {'target': 'login_code', 'type': 2, 'string': 'before4'},
                {'target': 'username', 'type': 3, 'string': 'before5'},
                {'target': 'email', 'type': 4, 'string': 'before6'}
            ],
            [
                {'target': 'login_code', 'type': 1, 'string': 'before7'},
                {'target': 'username', 'type': 1, 'string': 'before8'},
                {'target': 'email', 'type': 1, 'string': 'before9'}
            ]]

        p_id = ''
        p_name = ''
        for i, child in enumerate(setting_type_list):
            created_parent_condition = ParentConditionFactory.create(
                contract=self.contract,
                parent_condition_name='test parent name' + str(i + 1),
                setting_type=child,
                created_by_id=self.user.id)

            self._create_child_condition(
                self.contract.id,
                created_parent_condition.id,
                created_parent_condition.parent_condition_name,
                comparison_list[i])

            if i == 2:
                p_id = created_parent_condition.id
                p_name = created_parent_condition.parent_condition_name

        condition_data = [
            {'target': 'org1', 'type': 5, 'string': 'after1'},
            {'target': 'org2', 'type': 6, 'string': 'after2'},
            {'target': 'org3', 'type': 7, 'string': 'after3'}
        ]
        # Request
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(
                self._detail_advanced_save_condition, {'condition_data': json.dumps(condition_data),
                                                       'parent_condition_id': p_id,
                                                       'condition_name': p_name})

        child_condition_a = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after1')
        child_condition_b = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after2')
        child_condition_c = ChildCondition.objects.filter(
            contract=self.contract, parent_condition_id=p_id, comparison_string='after3')

        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Success')
        self.assertEqual(1, child_condition_a.count())
        self.assertEqual(1, child_condition_b.count())
        self.assertEqual(1, child_condition_c.count())

    """
    search_target_ajax
    """

    def _assert_search_target(self, results, full_name, username, email, login_code):
        self.assertEqual(results, [{
            u'recid': 1,
            u'full_name': unicode(full_name),
            u'user_name': unicode(username),
            u'user_email': unicode(email),
            u'login_code': unicode(login_code)
        }])

    def test_search_target_ajax_unauthorized_access(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._search_target, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_search_target_ajax_no_child_condition(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._search_target, {'contract_id': self.contract.id})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Condition does not exist. Please set at least one condition.")

    def test_search_target_ajax(self):
        parent = self._create_parent_condition(parent_name='sample')
        self._create_child_condition(
            contract_id=self.contract.id, parent_condition_id=parent.id, condition_name=parent.parent_condition_name,
            comparison_list=[{'target': 'email', 'type': '1', 'string': 'sample001@example.com'}])

        user1 = UserFactory.create(email='sample001@example.com')
        member = MemberFactory.create(
            org=self.contract_org, user=user1, code='sample001', is_active=True, is_delete=False,
            created_by=self.user, creator_org=self.contract_org)
        biz_user = BizUserFactory.create(user=user1, login_code='sample_login_code')

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._search_target, {'contract_id': self.contract.id})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        show_list = json.loads(data['show_list'])
        self._assert_search_target(
            show_list, member.user.profile.name, member.user.username, member.user.email, biz_user.login_code)

    """
    detail_search_target_ajax
    """

    def test_detail_search_target_ajax_unauthorized_access(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._detail_search_target, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_detail_search_target_ajax_when_no_condition_param(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._detail_search_target, {
                'org_id': self.contract_org.id, 'contract_id': self.contract.id, 'condition_data': '[]'})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Condition does not exist. Please set at least one condition.")

    def test_detail_search_target_ajax(self):
        user1 = UserFactory.create(email='sample001@example.com')
        member = MemberFactory.create(
            org=self.contract_org, user=user1, code='sample001', is_active=True, is_delete=False,
            created_by=self.user, creator_org=self.contract_org)
        biz_user = BizUserFactory.create(user=user1, login_code='sample_login_code')

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._detail_search_target, {
                'org_id': self.contract_org.id,
                'contract_id': self.contract.id,
                'condition_data': json.dumps([{'target': 'email', 'type': '1', 'string': 'sample001@example.com'}])
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        show_list = json.loads(data['show_list'])
        self._assert_search_target(
            show_list, member.user.profile.name, member.user.username, member.user.email, biz_user.login_code)

    """
    cancel_reservation_date_ajax
    """

    def test_cancel_reservation_date_ajax_unauthorized_access(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._cancel_reservation_date, {})
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_cancel_reservation_date_ajax_when_has_contract_option(self):
        ContractOptionFactory.create(contract=self.contract, auto_register_reservation_date=datetime.now())
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._cancel_reservation_date, {'contract_id': self.contract.id})
        self.assertEqual(200, response.status_code)
        option = ContractOption.objects.get(contract=self.contract)
        self.assertFalse(option.auto_register_reservation_date)

    def test_cancel_reservation_date_ajax_when_has_not_contract_option(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._cancel_reservation_date, {'contract_id': self.contract.id})
        self.assertEqual(200, response.status_code)
        self.assertFalse(self.contract.auto_register_reservation_date)

    """
    reservation_date_ajax
    """

    def test_reservation_date_ajax_unauthorized_access(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._reservation_date, {})
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_reservation_date_ajax_no_child_condition(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._reservation_date, {
                'contract_id': self.contract.id, 'reservation_date': '2000/01/02'})
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Condition does not exist. Please set at least one condition.")

    @freezegun.freeze_time('2000-01-01 00:00:00')
    def test_reservation_date_ajax_when_past_date(self):
        self._create_one_condition()
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._reservation_date, {
                'contract_id': self.contract.id, 'reservation_date': '1999/12/01'})
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "The past date is entered. Please enter a future date.")

    @freezegun.freeze_time('2000-01-01 20:00:00')
    def test_reservation_date_ajax_when_not_while_reservation_datetime(self):
        self._create_one_condition()
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._reservation_date, {
                'contract_id': self.contract.id, 'reservation_date': '2000/01/02'})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'], "Today 's reception is over. Please enter the date of the future from tomorrow.")

    @freezegun.freeze_time('2000-01-01 00:00:00')
    def test_reservation_date_ajax(self):
        self._create_one_condition()
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._reservation_date, {
                'contract_id': self.contract.id, 'reservation_date': '2999/01/01'})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual('2999/01/01', data['reservation_date'])
        self.assertTrue(self.contract.auto_register_reservation_date)

    """
    update_auto_register_students_flg
    """

    def test_update_auto_register_students_flg_unauthorized_access(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._update_auto_register_students_flg, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_update_auto_register_students_flg_when_exists_reservation_date(self):
        ContractOptionFactory.create(contract=self.contract, auto_register_reservation_date=datetime.now())
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._update_auto_register_students_flg, {
                'contract_id': self.contract.id, 'auto_register_students_flag': 1 })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'], "You can't switch if the reservation reflection date is set. Please cancel reservation.")

    @ddt.data(False, True)
    def test_update_auto_register_students_flg(self, default_test_auto_register_students_flg):
        ContractOptionFactory.create(
            contract=self.contract,
            auto_register_students_flg=default_test_auto_register_students_flg)

        param_auto_register_students_flag = '0' if default_test_auto_register_students_flg else '1'
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._update_auto_register_students_flg, {
                'contract_id': self.contract.id, 'auto_register_students_flag': param_auto_register_students_flag})

        self.assertEqual(200, response.status_code)
        option = ContractOption.objects.get(contract=self.contract)
        self.assertEqual(not default_test_auto_register_students_flg, option.auto_register_students_flg)

    """
    task_history_ajax
    """

    def _create_task(self, task_type, task_key, task_id, task_state, total=0, attempted=0, succeeded=0, skipped=0,
                     failed=0, register=0, unregister=0, masked=0):
        task_output = json.dumps({
            'attempted': attempted,
            'succeeded': succeeded,
            'skipped': skipped,
            'failed': failed,
            'total': total,
            'student_register': register,
            'student_unregister': unregister,
            'personalinfo_mask': masked,
        })
        return TaskFactory.create(
            task_type=task_type, task_key=task_key, task_id=task_id, task_state=task_state, task_output=task_output
        )

    def _assert_task_history(self, history, recid, result, messages, requester, created, updated,
                             register=0, unregister=0, masked=0, failed=0):
        self.assertEqual(history['recid'], recid)
        if result is 'progress':
            self.assertEqual(history['result_message'], 'Task is being executed. Please wait a moment.')
        else:
            self.assertEqual(
                history['result_message'],
                "Register: {register}, Unregister: {unregister}, Masked: {masked}, Failed: {failed}".format(
                    register=register, unregister=unregister, masked=masked, failed=failed))
        self.assertEqual(history['messages'], messages)
        self.assertEqual(history['requester'], requester)
        self.assertEqual(history['created'], to_timezone(created).strftime('%Y/%m/%d %H:%M:%S'))
        self.assertEqual(history['updated'], to_timezone(updated).strftime('%Y/%m/%d %H:%M:%S'))

    def test_task_history_ajax(self):
        task_key = self.contract_org.org_code
        task_list = [
            self._create_task('reflect_conditions_immediate', task_key, 'task_id1', 'SUCCESS', 1, 1, 1, 0, 0, 1, 0, 0),
            self._create_task('reflect_conditions_reservation', task_key, 'task_id2', 'FAILURE', 1, 1, 0, 0, 1, 0, 0, 0),
            self._create_task('reflect_conditions_batch', task_key, 'task_id3', 'QUEUING', 1, 1, 0, 1, 0, 0, 0, 0),
            self._create_task('reflect_conditions_member_register', task_key, 'task_id4', 'PROGRESS', 1, 1, 1, 0, 0, 0, 0, 0),
            self._create_task('dummy_task', 'dummy_task_key2', 'dummy_task_id6', 'DUMMY', 1, 1, 1, 0, 0, 0, 0, 0),
        ]

        now = datetime.now()
        histories = [ReflectConditionTaskHistoryFactory.create(
            organization=self.contract_org,
            contract=self.contract,
            task_id=task.task_id,
            created=now + timedelta(seconds=i),
            updated=now + timedelta(seconds=i * 10),
            requester=self.user
        ) for i, task in enumerate(task_list)]
        histories[0].result = True
        histories[0].messages = 'Sample success message1'
        histories[0].save()
        histories[0].result = False
        histories[1].messages = 'Sample fail message1'
        histories[1].save()

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._task_history, {})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual('success', data['status'])
        self.assertEqual(len(task_list), data['total'])
        records = data['records']
        self._assert_task_history(
            history=records[0], recid=1, result='progress', messages=[],
            requester=self.user.username, created=histories[4].created, updated=histories[4].updated, register=1)
        self._assert_task_history(
            history=records[1], recid=2, result='progress', messages=[],
            requester=self.user.username, created=histories[3].created, updated=histories[3].updated, register=1)
        self._assert_task_history(
            history=records[2], recid=3, result='progress', messages=[],
            requester=self.user.username, created=histories[2].created, updated=histories[2].updated)
        self._assert_task_history(
            history=records[3], recid=4, result='Failed', messages=[{'recid': 1, 'message': 'Sample fail message1'}],
            requester=self.user.username, created=histories[1].created, updated=histories[1].updated, failed=1)
        self._assert_task_history(
            history=records[4], recid=5, result='Success',
            messages=[{'recid': 1, 'message': 'Sample success message1'}],
            requester=self.user.username, created=histories[0].created, updated=histories[0].updated, register=1)

    def test_task_history_ajax_unmatch_history(self):
        patcher = patch('biz.djangoapps.gx_save_register_condition.views.log')
        self.mock_log = patcher.start()
        self.addCleanup(patcher.stop)

        now = datetime.now()
        ReflectConditionTaskHistoryFactory.create(
            organization=self.contract_org,
            contract=self.contract,
            task_id='task_id',
            created=now,
            updated=now,
            requester=self.user
        )

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._task_history, {})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual('success', data['status'])
        self.assertEqual(0, data['total'])
        self.mock_log.warning.assert_any_call('Can not find Task by reflect condition task history')

    def test_task_history_ajax_not_found(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._task_history, {})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Task is not found.")

    """
    reflect_condition_ajax
    """

    def test_reflect_condition_ajax_unauthorized_access(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._reflect_condition, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_reflect_condition_ajax_no_child_condition(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._reflect_condition, {
                'org_id': self.contract_org.id,
                'contract_id': self.contract.id,
                'send_mail_flg': 0,
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], u"Condition does not exist. Please set at least one condition.")

    def test_reflect_condition_ajax_over_max_num(self):
        self._create_one_condition()
        with patch(
                'biz.djangoapps.gx_save_register_condition.views.get_members_by_all_parents_conditions') as mock_get_members_by_all_parents_conditions:
            mock_get_members_by_all_parents_conditions.return_value = [i for i in range(20000)]
            with self.skip_check_course_selection(
                    current_organization=self.contract_org, current_manager=self._director_manager,
                    current_contract=self.contract):
                response = self.client.post(self._reflect_condition, {
                    'org_id': self.contract_org.id,
                    'contract_id': self.contract.id,
                    'send_mail_flg': 0,
                })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'],
            u"Can't use immediate reflection, because Target is over 10000.<br/>Please use reservation reflection."
        )

    def test_reflect_condition_ajax(self):
        self._create_one_condition()
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._reflect_condition, {
                'org_id': self.contract_org.id,
                'contract_id': self.contract.id,
                'send_mail_flg': 0,
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['info'],
            "Began the processing of Reflect Conditions Immediate.Execution status, please check from the task history."
        )
        self.assertEqual(1, ReflectConditionTaskHistory.objects.filter(
            organization=self.contract_org, contract=self.contract).count())

    """
    get_active_condition_num_without_one
    """
    def test_get_active_condition_num_without_one_unauthorized_access(self):
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._get_active_condition_num_without_one, {})

        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_get_active_condition_num_without_one_when_zero(self):
        delete_target_parent, __ = self._create_one_condition()
        param = {
            'contract_id': self.contract.id,
            'without_parent_condition_id': delete_target_parent.id
        }
        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._get_active_condition_num_without_one, param)

        # Assertion
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(0, data['active_condition_num'])

    @ddt.data(1, 5)
    def test_get_active_condition_num_without_one(self, active_condition_num):
        delete_target_parent, __ = self._create_one_condition()
        for i in range(active_condition_num - 1):
            self._create_one_condition()

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_manager=self._director_manager,
                current_contract=self.contract):
            response = self.client.post(self._get_active_condition_num_without_one, {
                'contract_id': self.contract.id,
                'without_parent_condition_id': delete_target_parent.id
            })

        # Assertion
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(active_condition_num - 1, data['active_condition_num'])

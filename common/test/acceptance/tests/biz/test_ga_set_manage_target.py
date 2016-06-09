# -*- coding: utf-8 -*-
"""
End-to-end tests for set manage target of biz feature
"""

from bok_choy.web_app_test import WebAppTest
from . import (
    SUPER_USER_INFO, PLATFORMER_USER_INFO, PLAT_COMPANY_NAME, PLAT_COMPANY_CODE,
    GaccoBizTestMixin,
)
from ...pages.biz.ga_achievement import BizAchievementPage
from ...pages.biz.ga_contract import BizContractPage
from ...pages.biz.ga_dashboard import DashboardPage
from ...pages.biz.ga_navigation import NO_SELECTED
from ...pages.lms.ga_django_admin import DjangoAdminPage


class BizSetManageTargetTest(WebAppTest, GaccoBizTestMixin):

    def _create_aggregator(self, with_contract_count=1):
        new_aggregator = self.register_user()
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)
        new_contracts = []
        for i in range(with_contract_count):
            new_contracts.append(self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'O'))
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'aggregator', new_aggregator)
        return new_aggregator, new_org_info, new_contracts

    def test_director_no_contract(self):
        """
        Test director has no contract
        - Case 1
        """
        new_director = self.register_user()

        # test data, org contract permission
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', new_director)

        # Test Case 1
        self.restart_memcached()
        self.switch_to_user(new_director)
        biz_nav = DashboardPage(self.browser).visit().click_biz()

        self.assertEqual([u'Contract is not specified.'], biz_nav.messages)

    def test_change_manage_target_no_select(self):
        """
        Test change target, select empty
        - Case 2, 3
        """
        # create course
        new_course_key_plat_1, _ = self.install_course(PLAT_COMPANY_CODE)
        new_course_key_plat_2, new_course_name_plat_2 = self.install_course(PLAT_COMPANY_CODE)

        new_director = self.register_user()

        # test data, org contract permission
        new_org_info_1 = self.register_organization(PLATFORMER_USER_INFO)
        new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info_1['Organization Name'], detail_info=[new_course_key_plat_1, new_course_key_plat_2])
        self.register_contract(PLATFORMER_USER_INFO, new_org_info_1['Organization Name'])
        self.grant(PLATFORMER_USER_INFO, new_org_info_1['Organization Name'], 'director', new_director)

        new_org_info_2 = self.register_organization(PLATFORMER_USER_INFO)
        self.grant(PLATFORMER_USER_INFO, new_org_info_2['Organization Name'], 'director', new_director)

        # Test Case 2
        self.switch_to_user(new_director)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_nav.change_manage_target(new_org_info_1['Organization Name'], new_contract['Contract Name'], new_course_name_plat_2)
        BizAchievementPage(self.browser).wait_for_page()
        self.assertEqual(biz_nav.contract_name, new_contract['Contract Name'])
        self.assertEqual(biz_nav.course_name, new_course_name_plat_2)

        # Test Case 3
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_nav.change_manage_target(NO_SELECTED, close=False)
        self.assertEqual(biz_nav.modal_message, u'Organization name is not specified.')

        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_nav.change_manage_target(new_org_info_1['Organization Name'], NO_SELECTED, close=False)
        self.assertEqual(biz_nav.modal_message, u'Contract name is not specified.')

        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_nav.change_manage_target(new_org_info_1['Organization Name'], new_contract['Contract Name'], NO_SELECTED, close=False)
        self.assertEqual(biz_nav.modal_message, u'Course name is not specified.')

    def test_no_contract_no_course(self):
        """
        Test no contract, no course
        - Case 85, 86
        """
        # test data, org contract permission for aggregator
        new_aggregator, _, _ = self._create_aggregator()

        # test data, org permission for director
        new_director = self.register_user()
        new_org_info = self.register_organization(new_aggregator)
        self.grant(new_aggregator, new_org_info['Organization Name'], 'director', new_director)

        # Test Case 85
        self.restart_memcached()
        self.switch_to_user(new_director)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertEqual(biz_nav.messages, [u'Contract is not specified.'])

        # test data contract for director
        self.register_contract(new_aggregator, new_org_info['Organization Name'], 'OS')

        # Test Case 86
        self.restart_memcached()
        self.switch_to_user(new_director)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertEqual(biz_nav.messages, [u'Course is not specified.'])

    def test_just_1(self):
        """
        Test just 1 org, 1 contract, 1 course
        - Case 87
        """
        # test data, org contract permission for aggregator
        new_aggregator, new_org_info_1, _ = self._create_aggregator()

        # create course
        new_course_key_1, new_course_name_1 = self.install_course(new_org_info_1['Organization Code'])

        # test data, org contract permission for director
        new_director = self.register_user()
        new_org_info_2 = self.register_organization(new_aggregator)
        new_contract = self.register_contract(new_aggregator, new_org_info_2['Organization Name'], 'OS', detail_info=[new_course_key_1])
        self.grant(new_aggregator, new_org_info_2['Organization Name'], 'director', new_director)

        # Test Case 87
        self.restart_memcached()
        self.switch_to_user(new_director)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        BizAchievementPage(self.browser).wait_for_page()
        self.assertEqual(biz_nav.contract_name, new_contract['Contract Name'])
        self.assertEqual(biz_nav.course_name, new_course_name_1)

    def test_2_courses(self):
        """
        Test 1 org, 1 contract, 2 courses
        - Case 88
        """
        # test data, org contract permission for aggregator
        new_aggregator, new_org_info_1, _ = self._create_aggregator()

        # create course
        new_course_key_1, _ = self.install_course(new_org_info_1['Organization Code'])
        new_course_key_2, new_course_name_2 = self.install_course(new_org_info_1['Organization Code'])

        # test data, org contract permission for director
        new_director = self.register_user()
        new_org_info_2 = self.register_organization(new_aggregator)
        new_contract = self.register_contract(new_aggregator, new_org_info_2['Organization Name'], 'OS', detail_info=[new_course_key_1, new_course_key_2])
        self.grant(new_aggregator, new_org_info_2['Organization Name'], 'director', new_director)

        # Test Case 88
        self.restart_memcached()
        self.switch_to_user(new_director)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertEqual(biz_nav.messages, [u'Course is not specified.'])

        biz_nav.change_manage_target(new_org_info_2['Organization Name'], new_contract['Contract Name'], new_course_name_2)
        BizAchievementPage(self.browser).wait_for_page()
        self.assertEqual(biz_nav.contract_name, new_contract['Contract Name'])
        self.assertEqual(biz_nav.course_name, new_course_name_2)

        # Retry from Dashboard
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertEqual(biz_nav.contract_name, new_contract['Contract Name'])
        self.assertEqual(biz_nav.course_name, new_course_name_2)

    def test_2_contracts(self):
        """
        Test 1 org, 2 contracts, 1 course
        - Case 89
        """
        # test data, org contract permission for aggregator
        new_aggregator, new_org_info_1, _ = self._create_aggregator()

        # create course
        new_course_key_1, new_course_name_1 = self.install_course(new_org_info_1['Organization Code'])

        # test data, org contract permission for director
        new_director = self.register_user()
        new_org_info_2 = self.register_organization(new_aggregator)
        self.register_contract(new_aggregator, new_org_info_2['Organization Name'], 'OS')
        new_contract = self.register_contract(new_aggregator, new_org_info_2['Organization Name'], 'OS', detail_info=[new_course_key_1])
        self.grant(new_aggregator, new_org_info_2['Organization Name'], 'director', new_director)

        # Test Case 89
        self.restart_memcached()
        self.switch_to_user(new_director)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertEqual(biz_nav.messages, [u'Contract is not specified.'])

        biz_nav.change_manage_target(new_org_info_2['Organization Name'], new_contract['Contract Name'], new_course_name_1)
        BizAchievementPage(self.browser).wait_for_page()
        self.assertEqual(biz_nav.contract_name, new_contract['Contract Name'])
        self.assertEqual(biz_nav.course_name, new_course_name_1)

        # Retry from Dashboard
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertEqual(biz_nav.contract_name, new_contract['Contract Name'])
        self.assertEqual(biz_nav.course_name, new_course_name_1)

    def test_aggregator_no_contract_1_contract(self):
        """
        Test aggregator has no contract
        - Case 90, 91
        """
        # test data, org permission for aggregator
        new_aggregator, new_org_info, _ = self._create_aggregator(0)

        # Test Case 90
        self.restart_memcached()
        self.switch_to_user(new_aggregator)
        biz_nav = DashboardPage(self.browser).visit().click_biz()

        self.assertEqual([u'Contract is not specified.'], biz_nav.messages)

        # test data, contract for aggregator
        new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'O')

        # Test Case 91
        self.restart_memcached()
        self.switch_to_user(new_aggregator)
        biz_nav = DashboardPage(self.browser).visit().click_biz()

        BizContractPage(self.browser).wait_for_page()
        self.assertEqual([], biz_nav.messages)

    def test_aggregator_2_contracts(self):
        """
        Test 1 org, 2 contracts
        - Case 92
        """
        # test data, org contract permission for aggregator
        new_aggregator, new_org_info, new_contracts = self._create_aggregator(2)

        # Test Case 92
        self.restart_memcached()
        self.switch_to_user(new_aggregator)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertEqual(biz_nav.messages, [u'Contract is not specified.'])

        biz_nav.change_manage_target(new_org_info['Organization Name'], new_contracts[1]['Contract Name'])
        BizContractPage(self.browser).wait_for_page()
        self.assertEqual([], biz_nav.messages)

        # Retry from Dashboard
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        BizContractPage(self.browser).wait_for_page()
        self.assertEqual([], biz_nav.messages)

    def test_platformer(self):
        """
        Test platformer view page of contract
        - Case 93
        """
        self.restart_memcached()
        self.switch_to_user(PLATFORMER_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()

        BizContractPage(self.browser).wait_for_page()
        self.assertEqual([], biz_nav.messages)

    def test_new_platformer(self):
        """
        Test new platformer view page of contract
        - Case 94
        """
        new_platformer = self.register_user()

        # register platformer on django admin
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = DjangoAdminPage(self.browser).visit().click_add('ga_manager', 'manager')
        django_admin_list_page = django_admin_add_page.input({
            'org': PLAT_COMPANY_NAME,
            'manager_permissions': 'platformer',
        }).lookup_user('lookup_id_user', new_platformer['username']).save()

        django_admin_list_page.get_row({
            'Org name': PLAT_COMPANY_NAME,
            'User name': new_platformer['username'],
            'Permissions': 'platformer',
        })

        # Test Case 94
        self.restart_memcached()
        self.switch_to_user(new_platformer)
        biz_nav = DashboardPage(self.browser).visit().click_biz()

        BizContractPage(self.browser).wait_for_page()
        self.assertEqual([], biz_nav.messages)

# -*- coding: utf-8 -*-
"""
End-to-end tests for access page from menu of biz feature
"""
from flaky import flaky

from bok_choy.web_app_test import WebAppTest
from nose.plugins.attrib import attr

from . import PLAT_COMPANY_CODE, PLATFORMER_USER_INFO, GaccoBizTestMixin
from ...pages.biz.ga_dashboard import DashboardPage


MENU_ORGANIZATION = u'Organization List'
MENU_CONTRACT = u'Contract List'
MENU_MANAGER = u'Manager Setting'

MENU_SCORE = u'Score Status'
MENU_PLAYBACK = u'Playback Status'
MENU_SURVEY = u'Survey Management'

MENU_USER_REGISTER = u'Contract Register Management'
MENU_REGISTER_MANAGEMENT = u'Register User Management'


@attr('shard_ga_biz_1')
class BizAccessPageFromMenuTest(WebAppTest, GaccoBizTestMixin):

    def test_platformer(self):
        """
        Test menu of platformer
        - Case 95
        """
        self.switch_to_user(PLATFORMER_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertItemsEqual(biz_nav.left_menu_items.keys(), [MENU_ORGANIZATION, MENU_CONTRACT, MENU_MANAGER])

        # access to each page
        biz_nav.visit().click_organization().click_add()
        biz_nav.visit().click_contract().click_register_button(wait_for_page=True)
        biz_nav.visit().click_manager()

    def test_director_and_manager(self):
        """
        Test menu of director and manager
        - Case 96, 97
        """
        new_course_key_plat, _ = self.install_course(PLAT_COMPANY_CODE)

        new_director = self.register_user()
        new_manager = self.register_user()

        new_org_info = self.register_organization(PLATFORMER_USER_INFO)
        self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], detail_info=[new_course_key_plat])
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', new_director)
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'manager', new_manager)

        # Case 96
        self.switch_to_user(new_director)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertItemsEqual(biz_nav.left_menu_items.keys(), [MENU_SCORE, MENU_PLAYBACK, MENU_SURVEY, MENU_USER_REGISTER, MENU_REGISTER_MANAGEMENT, MENU_MANAGER])

        # access to each page
        biz_nav.visit().click_score()
        biz_nav.visit().click_survey()
        biz_nav.visit().click_register_students()
        biz_nav.visit().click_register_management()
        biz_nav.visit().click_manager()

        # Case 97
        self.switch_to_user(new_manager)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertItemsEqual(biz_nav.left_menu_items.keys(), [MENU_SCORE, MENU_PLAYBACK])

        # assert access to each page
        biz_nav.visit().click_score()

    @flaky
    def test_owner_director_and_manager(self):
        """
        Test menu of owner and director and manager
        - Case 98, 99, 100
        """
        new_aggregator, new_aggregator_org_info, _ = self.create_aggregator()
        new_course_key_plat, _ = self.install_course(new_aggregator_org_info['Organization Code'])

        new_director = self.register_user()
        new_manager = self.register_user()

        new_org_info = self.register_organization(new_aggregator)

        self.register_contract(new_aggregator, new_org_info['Organization Name'], contract_type='OS', detail_info=[new_course_key_plat])
        self.grant(new_aggregator, new_org_info['Organization Name'], 'director', new_director)
        self.grant(new_aggregator, new_org_info['Organization Name'], 'manager', new_manager)

        # Case 98
        self.switch_to_user(new_aggregator)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertItemsEqual(biz_nav.left_menu_items.keys(), [MENU_ORGANIZATION, MENU_CONTRACT, MENU_MANAGER])

        # access to each page
        biz_nav.visit().click_organization().click_add()
        biz_nav.visit().click_contract().click_register_button(wait_for_page=True)
        biz_nav.visit().click_manager()

        # Case 99
        self.switch_to_user(new_director)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertItemsEqual(biz_nav.left_menu_items.keys(), [MENU_SCORE, MENU_PLAYBACK, MENU_SURVEY, MENU_USER_REGISTER, MENU_REGISTER_MANAGEMENT, MENU_MANAGER])

        # access to each page
        biz_nav.visit().click_score()
        biz_nav.visit().click_survey()
        biz_nav.visit().click_register_students()
        biz_nav.visit().click_register_management()
        biz_nav.visit().click_manager()

        # Case 100
        self.switch_to_user(new_manager)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertItemsEqual(biz_nav.left_menu_items.keys(), [MENU_SCORE, MENU_PLAYBACK])

        # assert access to each page
        biz_nav.visit().click_score()

    def test_director_and_manager_on_mooc(self):
        """
        Test menu of director and manager on mooc
        - Case 101, 102
        """
        new_course_key_plat, _ = self.install_course(PLAT_COMPANY_CODE)

        new_director = self.register_user()
        new_manager = self.register_user()

        new_org_info = self.register_organization(PLATFORMER_USER_INFO)
        self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], contract_type='GS', detail_info=[new_course_key_plat])
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', new_director)
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'manager', new_manager)

        # Case 101
        self.switch_to_user(new_director)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertItemsEqual(biz_nav.left_menu_items.keys(), [MENU_SCORE, MENU_PLAYBACK, MENU_USER_REGISTER, MENU_REGISTER_MANAGEMENT, MENU_MANAGER])

        # access to each page
        biz_nav.visit().click_score()
        biz_nav.visit().click_register_students()
        biz_nav.visit().click_register_management()
        biz_nav.visit().click_manager()

        # Case 102
        self.switch_to_user(new_manager)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        self.assertItemsEqual(biz_nav.left_menu_items.keys(), [MENU_SCORE, MENU_PLAYBACK])

        # assert access to each page
        biz_nav.visit().click_score()

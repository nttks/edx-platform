# -*- coding: utf-8 -*-
"""
End-to-end tests for invitation of biz feature
"""
from flaky import flaky

from bok_choy.web_app_test import WebAppTest
from nose.plugins.attrib import attr

from common.test.acceptance.fixtures.course import CourseFixture
from common.test.acceptance.pages.biz.ga_contract import BizContractPage
from common.test.acceptance.pages.biz.ga_course_about import CourseAboutPage
from common.test.acceptance.pages.biz.ga_invitation import BizInvitationPage, BizInvitationConfirmPage
from common.test.acceptance.pages.lms.account_settings import AccountSettingsPage
from common.test.acceptance.pages.lms.ga_dashboard import DashboardPage
from common.test.acceptance.tests.biz import C_DIRECTOR_USER_INFO, PLATFORMER_USER_INFO, \
    B_DIRECTOR_USER_INFO, B_COMPANY, GaccoBizTestMixin, AGGREGATOR_USER_INFO, C_COMPANY


@attr('shard_ga_biz_1')
class BizInvitationTest(WebAppTest, GaccoBizTestMixin):
    """
    Tests that the invitation functionality works
    """
    CONTRACT_TYPE_GACCO_SERVICE = 'GS'
    CONTRACT_TYPE_OWNER_SERVICE = 'OS'

    @flaky
    def test_register_owner_service_course(self):
        """
        Tests register invitation code of owner service contract.
        """
        # Create owner service courses
        self.course = CourseFixture('owner', 'test_invitation', 'biz_test_run',
                                    'Biz Test Course ' + self._testMethodName)
        self.course.install()

        # Create contract test data
        self.switch_to_user(AGGREGATOR_USER_INFO)
        contract_no_detail = self.create_contract(BizContractPage(self.browser).visit(),
                                                  self.CONTRACT_TYPE_OWNER_SERVICE,
                                                  '2016/01/01',
                                                  '2100/01/01', contractor_organization=C_COMPANY)
        contract_future = self.create_contract(BizContractPage(self.browser).visit(),
                                               self.CONTRACT_TYPE_OWNER_SERVICE,
                                               '2100/01/01',
                                               '2100/01/01', contractor_organization=C_COMPANY,
                                               detail_info=[self.course._course_key],
                                               additional_info=[u'部署'])

        contract_expired = self.create_contract(BizContractPage(self.browser).visit(),
                                                self.CONTRACT_TYPE_OWNER_SERVICE,
                                                '2000/01/01',
                                                '2000/01/01', contractor_organization=C_COMPANY,
                                                detail_info=[self.course._course_key],
                                                additional_info=[u'部署'])

        contract_effective = self.create_contract(BizContractPage(self.browser).visit(),
                                                  self.CONTRACT_TYPE_OWNER_SERVICE,
                                                  '2000/01/01',
                                                  '2100/01/01', contractor_organization=C_COMPANY,
                                                  detail_info=[self.course._course_key],
                                                  additional_info=[u'部署'])

        # Login as C company director
        self.switch_to_user(C_DIRECTOR_USER_INFO)

        # Case 59
        # Do not enter invitation code
        invitation_page = BizInvitationPage(self.browser).visit().click_register_button()
        invitation_page.wait_for_ajax()
        self.assertIn('Invitation code is required.', invitation_page.messages)

        # Case 60
        # Try to input invitation code of incomplete contract
        invitation_page = BizInvitationPage(self.browser).visit().input_invitation_code(
                contract_no_detail['Invitation Code']).click_register_button()
        invitation_page.wait_for_ajax()
        self.assertIn('Invitation code is invalid.', invitation_page.messages)

        # Case 61
        # Try to input invitation code of future contract
        invitation_page = BizInvitationPage(self.browser).visit().input_invitation_code(
                contract_future['Invitation Code']).click_register_button()
        invitation_page.wait_for_ajax()
        self.assertIn('Invitation code is invalid.', invitation_page.messages)

        # Case 62
        # Try to input invitation code of expired contract
        invitation_page = BizInvitationPage(self.browser).visit().input_invitation_code(
                contract_expired['Invitation Code']).click_register_button()
        invitation_page.wait_for_ajax()
        self.assertIn('Invitation code is invalid.', invitation_page.messages)

        # Case 63
        # Try to register invitation code without additional info
        BizInvitationPage(self.browser).visit().input_invitation_code(
                contract_effective['Invitation Code']).click_register_button()
        confirm_page = BizInvitationConfirmPage(self.browser, contract_effective['Invitation Code']).wait_for_page().click_register_button()
        confirm_page.wait_for_ajax()
        self.assertIn(u'部署 is required.', confirm_page.additional_messages)

        # Case 54, 103
        # Input invitation code
        AccountSettingsPage(self.browser).visit().click_on_link_in_link_field('invitation_code')
        BizInvitationPage(self.browser).wait_for_page().input_invitation_code(
                contract_effective['Invitation Code']).click_register_button()
        BizInvitationConfirmPage(self.browser, contract_effective['Invitation Code']).wait_for_page()

        # Verify that course about page have no register link
        course_about_page = CourseAboutPage(self.browser, self.course._course_key).visit()
        self.assertFalse(course_about_page.is_register_link_displayed)

        # Register invitation code
        AccountSettingsPage(self.browser).visit().click_on_link_in_link_field('invitation_code')
        BizInvitationPage(self.browser).wait_for_page().input_invitation_code(
                contract_effective['Invitation Code']).click_register_button()
        BizInvitationConfirmPage(self.browser, contract_effective['Invitation Code']).wait_for_page().input_additional_info(u'マーケティング部',
                                                                                     0).click_register_button()

        # Verify that course is registered
        dashboard = DashboardPage(self.browser).wait_for_page()
        self.assertIn(self.course._course_dict['display_name'], dashboard.available_courses)

    def test_register_platfomer_service_course(self):
        """
        Tests register invitation code of platformer service contract.
        """
        # Create platfomer service courses
        self.course = CourseFixture('plat', self._testMethodName, 'biz_test_run',
                                    'Biz Test Course ' + self._testMethodName)
        self.course.install()

        # Register contract as platfomer
        self.switch_to_user(PLATFORMER_USER_INFO)
        contract = self.create_contract(BizContractPage(self.browser).visit(), self.CONTRACT_TYPE_GACCO_SERVICE,
                                        '2016/01/01',
                                        '2100/01/01', contractor_organization=B_COMPANY,
                                        detail_info=[self.course._course_key],
                                        additional_info=[u'部署', u'社員番号'])

        # Change login user
        self.switch_to_user(B_DIRECTOR_USER_INFO)

        # Case 55
        # Verify that course about page have register link
        self.assertTrue(
                CourseAboutPage(self.browser,
                                self.course._course_key).visit().is_register_link_displayed)
        # Register invitation code
        BizInvitationPage(self.browser).visit().input_invitation_code(
                contract['Invitation Code']).click_register_button()
        BizInvitationConfirmPage(self.browser, contract['Invitation Code']).wait_for_page() \
            .input_additional_info(u'開発部', 0).input_additional_info(u'学校　太郎', 1).click_register_button()
        # Verify that course is registered
        dashboard = DashboardPage(self.browser)
        dashboard.wait_for_page()
        self.assertIn(self.course._course_dict['display_name'], dashboard.available_courses)

        # Case 56
        # Verify that course about page have no register link
        course_about_page = CourseAboutPage(self.browser, self.course._course_key).visit()
        self.assertFalse(course_about_page.is_register_link_displayed)
        self.assertIn('You are enrolled in this course', course_about_page.register_disabled_text)
        # Register invitation code again
        BizInvitationPage(self.browser).visit().input_invitation_code(
                contract['Invitation Code']).click_register_button()
        BizInvitationConfirmPage(self.browser, contract['Invitation Code']).wait_for_page() \
            .input_additional_info(u'事業サービス部', 0).input_additional_info(u'学校　花子', 1).click_register_button()
        # Verify that course is registered
        dashboard = DashboardPage(self.browser).wait_for_page()
        self.assertIn(self.course._course_dict['display_name'], dashboard.available_courses)

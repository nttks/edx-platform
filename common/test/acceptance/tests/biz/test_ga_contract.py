# -*- coding: utf-8 -*-
"""
End-to-end tests for contract of biz feature
"""
from itertools import izip

import bok_choy
from bok_choy.web_app_test import WebAppTest

from common.test.acceptance.fixtures.course import CourseFixture
from common.test.acceptance.pages.biz.ga_contract import BizContractPage, BizContractDetailPage
from common.test.acceptance.pages.biz.ga_navigation import BizNavPage
from common.test.acceptance.pages.common.logout import LogoutPage
from common.test.acceptance.pages.lms.auto_auth import AutoAuthPage
from common.test.acceptance.tests.biz import AGGREGATOR_USER_INFO, GaccoBizTestMixin


class BizContractTest(WebAppTest, GaccoBizTestMixin):
    """
    Tests that the contract functionality works
    """

    COURSE_ORG = 'owner'
    COURSE_RUN = 'biz_test_run'
    COURSE_DISPLAY_NAME = 'Biz Contract Test Course'

    CONTRACTOR_ORGANIZATION = '5'
    CONTRACTOR_ORGANIZATION_NAME = 'C company'
    CONTRACT_TYPE = 'OS'
    CONTRACT_TYPE_NAME = 'Owner Service Contract'

    def assert_initial_columns(self, grid_columns):
        self.assertEqual(len(grid_columns), 6)
        self.assertIn(u'Contract Name', grid_columns)
        self.assertIn(u'Contract Type', grid_columns)
        self.assertIn(u'Invitation Code', grid_columns)
        self.assertIn(u'Contractor Organization Name', grid_columns)
        self.assertIn(u'Contract Start Date', grid_columns)
        self.assertIn(u'Contract End Date', grid_columns)

    def setUp(self):
        super(BizContractTest, self).setUp()
        # Create courses
        course = CourseFixture(self.COURSE_ORG, self._testMethodName, self.COURSE_RUN, self.COURSE_DISPLAY_NAME).install()
        self.course_id = course._course_key
        # Auto login
        self._auto_login(AGGREGATOR_USER_INFO)

    def _auto_login(self, user_info):
        """
        Auto auth.
        """
        AutoAuthPage(self.browser, username=user_info['username'], password=user_info['password'], email=user_info['email']).visit()

    def test_show_register_have_no_org(self):
        """
        Tests can not register contract when have no created organizations.
        Case 38
        """
        # Auto login
        LogoutPage(self.browser).visit()
        self._auto_login({'username': 'towner', 'password': 'edx', 'email': 'towner@example.com'})

        # Visit contract list page
        contract_page = BizNavPage(self.browser).visit().click_contract()
        # Try to show register view
        contract_page = contract_page.click_register_button().wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_show_register_have_no_org_1')
        # Verify that an error is displayed
        self.assertIn("You need to create an organization first.", contract_page.messages)

    def test_register_all_as_owner(self):
        """
        Tests register contract input all fields.
        Case 39
        """
        # Visit register view
        BizNavPage(self.browser).visit().click_contract().click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # Register a contract
        contract_name = self.CONTRACTOR_ORGANIZATION_NAME + self.unique_id[0:8]
        invitation_code = self.unique_id[0:8]
        start_date = '2016/01/01'
        end_date = '2100/01/01'
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date=start_date, end_date=end_date,
                          contractor_organization=self.CONTRACTOR_ORGANIZATION) \
            .add_detail_info(self.course_id, 1) \
            .add_additional_info(u'部署', 1) \
            .add_additional_info(u'社員番号', 2) \
            .click_register_button()
        contract_page = BizContractPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_all_as_owner_1')

        # Verify that success message is displayed
        self.assertIn("The new contract has been added.", contract_page.messages)
        # Verify that grid row displayed
        self.assert_initial_columns(contract_page.grid_columns)
        self.assert_grid_row(
                contract_page.get_row({'Contract Name': contract_name}),
                {
                    'Contract Name': contract_name,
                    'Contract Type': self.CONTRACT_TYPE_NAME,
                    'Invitation Code': invitation_code,
                    'Contract Start Date': start_date,
                    'Contract End Date': end_date,
                    'Contractor Organization Name': self.CONTRACTOR_ORGANIZATION_NAME
                }
        )

    def test_register_contract_and_detail_as_owner(self):
        """
        Tests register contract input detail info.
        Case 41
        """
        # Visit register view
        BizNavPage(self.browser).visit().click_contract().click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # Register a contract
        contract_name = self.CONTRACTOR_ORGANIZATION_NAME + self.unique_id[0:8]
        invitation_code = self.unique_id[0:8]
        start_date = '2016/01/01'
        end_date = '2100/01/01'
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date=start_date, end_date=end_date,
                          contractor_organization=self.CONTRACTOR_ORGANIZATION) \
            .add_detail_info(self.course_id, 1)\
            .click_register_button()
        contract_page = BizContractPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_contract_and_detail_as_owner_1')

        # Verify that success message is displayed
        self.assertIn("The new contract has been added.", contract_page.messages)
        # Verify that grid row displayed
        self.assert_initial_columns(contract_page.grid_columns)
        self.assert_grid_row(
                contract_page.get_row({'Contract Name': contract_name}),
                {
                    'Contract Name': contract_name,
                    'Contract Type': self.CONTRACT_TYPE_NAME,
                    'Invitation Code': invitation_code,
                    'Contract Start Date': start_date,
                    'Contract End Date': end_date,
                    'Contractor Organization Name': self.CONTRACTOR_ORGANIZATION_NAME
                }
        )

    def test_register_contract_and_additinaol_by_owner(self):
        """
        Tests register contract input additional info.
        Case 40
        """
        # Visit register view
        BizNavPage(self.browser).visit().click_contract().click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # Register a contract
        contract_name = self.CONTRACTOR_ORGANIZATION_NAME + self.unique_id[0:8]
        invitation_code = self.unique_id[0:8]
        start_date = '2016/01/01'
        end_date = '2100/01/01'
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date=start_date, end_date=end_date,
                          contractor_organization=self.CONTRACTOR_ORGANIZATION) \
            .add_additional_info(u'部署', 1) \
            .add_additional_info(u'社員番号', 2) \
            .click_register_button()
        contract_page = BizContractPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_contract_and_additinaol_by_owner_1')

        # Verify that success message is displayed
        self.assertIn("The new contract has been added.", contract_page.messages)
        # Verify that grid row displayed
        self.assert_initial_columns(contract_page.grid_columns)
        self.assert_grid_row(
                contract_page.get_row({'Contract Name': contract_name}),
                {
                    'Contract Name': contract_name,
                    'Contract Type': self.CONTRACT_TYPE_NAME,
                    'Invitation Code': invitation_code,
                    'Contract Start Date': start_date,
                    'Contract End Date': end_date,
                    'Contractor Organization Name': self.CONTRACTOR_ORGANIZATION_NAME
                }
        )

    def test_register_required_error(self):
        """
        Tests register contract without required fields.
        Case 42
        """
        # Visit register view
        BizNavPage(self.browser).visit().click_contract().click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # Register a contract
        detail_page.add_additional_info('name', 1).click_register_button()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_required_error_1')

        # Verify that required errors are displayed
        required_error = 'The field is required.'
        self.assertEqual(detail_page.contract_field_errors,
                         [required_error, '', required_error, '', required_error, required_error])

    def test_register_invitation_code_field_error(self):
        """
        Tests that invitation code field validation.
        """
        # Visit register view
        BizNavPage(self.browser).visit().click_contract().click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # Case 43
        # input invalid invitation_code
        contract_name = self.CONTRACTOR_ORGANIZATION_NAME + self.unique_id[0:8]
        start_date = '2016/01/01'
        end_date = '2100/01/01'
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE, invitation_code='&%&%&&&&%',
                          start_date=start_date, end_date=end_date,
                          contractor_organization=self.CONTRACTOR_ORGANIZATION) \
            .click_register_button().wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_invitation_code_invalid_error_1')
        # Verify that error is displayed
        self.assertEqual(detail_page.contract_field_errors, ['', '', 'Enter a valid value.', '', '', ''])

        # Case 44
        # input short invitation_code
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE, invitation_code='E00000',
                          start_date=start_date, end_date=end_date,
                          contractor_organization=self.CONTRACTOR_ORGANIZATION) \
            .click_register_button().wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_invitation_code_length_error_1')
        # Verify that error is displayed
        self.assertEqual(detail_page.contract_field_errors,
                         ['', '', 'Ensure this value has at least 8 characters (it has 6).', '', '', ''])

        # Register a contract
        invitation_code = self.unique_id[0:8]
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date=start_date, end_date=end_date,
                          contractor_organization=self.CONTRACTOR_ORGANIZATION) \
            .add_additional_info(u'部署', 1) \
            .click_register_button()
        contract_page = BizContractPage(self.browser).wait_for_page()
        contract_page.click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # Case 49
        # input used invitation_code
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date=start_date, end_date=end_date,
                          contractor_organization=self.CONTRACTOR_ORGANIZATION).click_register_button().wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_invitation_code_used_error_1')
        # Verify that error is displayed
        self.assertEqual(detail_page.contract_field_errors, ['', '', 'The invitation code has been used.', '', '', ''])

    def test_register_date_field_error(self):
        """
        Tests that date fields validation.
        """
        # Visit register view
        BizNavPage(self.browser).visit().click_contract().click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # Case 45
        # input invalid start date
        contract_name = self.CONTRACTOR_ORGANIZATION_NAME + self.unique_id[0:8]
        invitation_code = self.unique_id[0:8]
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date='2016/01/01/01',
                          end_date='2100/01/01').click_register_button().wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_date_field_error_1')
        # Verify that error is displayed
        self.assertEqual(detail_page.contract_field_errors, ['', '', '', '', 'Enter a valid value.', ''])

        # Case 46
        # input invalid end date
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date='2016/01/01',
                          end_date='2100/01/01/01').click_register_button().wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_date_field_error_2')
        # Verify that error is displayed
        self.assertEqual(detail_page.contract_field_errors, ['', '', '', '', '', 'Enter a valid value.'])

        # Case 47,48
        # input end date before start date
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date='2016/01/02',
                          end_date='2016/01/01').click_register_button().wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_date_field_error_3')
        # Verify that error is displayed
        self.assertEqual(detail_page.main_info_error, 'Contract end date is before contract start date.')

    def test_register_detail_info_error(self):
        """
        Tests contract details validation.
        """
        # Visit register view
        BizNavPage(self.browser).visit().click_contract().click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # Case 50
        # input duplicate detail info
        contract_name = self.CONTRACTOR_ORGANIZATION_NAME + self.unique_id[0:8]
        invitation_code = self.unique_id[0:8]
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE, invitation_code=invitation_code,
                          start_date='2016/01/01',
                          end_date='2100/01/01') \
            .add_detail_info(self.course_id, 1) \
            .add_detail_info(self.course_id, 2) \
            .click_register_button().wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_detail_info_error_1')

        # Verify that error is displayed
        self.assertEqual(detail_page.detail_info_error, 'You can not enter duplicate values in Contract Detail Info.')

    def test_register_additional_info_error(self):
        """
        Tests contract additional validation.
        """
        # Visit register view
        BizNavPage(self.browser).visit().click_contract().click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # Case 51
        # input duplicate detail info
        contract_name = self.CONTRACTOR_ORGANIZATION_NAME + self.unique_id[0:8]
        invitation_code = self.unique_id[0:8]
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE, invitation_code=invitation_code,
                          start_date='2016/01/01',
                          end_date='2100/01/01') \
            .add_additional_info(u'部署', 1) \
            .add_additional_info(u'部署', 2).click_register_button().wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_register_additional_info_error_1')

        # Verify that error is displayed
        self.assertEqual(detail_page.additional_info_error, 'You can not enter duplicate values in Additional Info.')

    def test_edit_success(self):
        """
        Tests edit contract.
        Case 52
        """
        # Create another courses
        course2 = CourseFixture(self.COURSE_ORG, self._testMethodName + '_2', self.COURSE_RUN, self.COURSE_DISPLAY_NAME).install()

        # Visit register view
        BizNavPage(self.browser).visit().click_contract().click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # register a contract
        contract_name = self.CONTRACTOR_ORGANIZATION_NAME + self.unique_id[0:8]
        invitation_code = self.unique_id[0:8]
        start_date = '2016/01/01'
        end_date = '2100/01/01'
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date=start_date, end_date=end_date) \
            .add_detail_info(self.course_id, 1) \
            .add_additional_info(u'部署', 1) \
            .click_register_button()
        contract_page = BizContractPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_edit_success_1')

        # Visit detail view
        detail_page = contract_page.click_grid_row({'Contract Name': contract_name}, BizContractDetailPage)
        bok_choy.browser.save_screenshot(self.browser, 'test_edit_success_2')

        # Edit all fields except contract_type
        contract_name += '2'
        invitation_code += '2'
        start_date = '2016/01/02'
        end_date = '2100/01/02'
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date=start_date, end_date=end_date) \
            .input_detail_info(course2._course_key, 1) \
            .input_additional_info(u'社員番号', 1) \
            .click_register_button()
        contract_page = contract_page.wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_edit_success_3')

        # Verify that an error is displayed
        self.assertIn("The contract changes have been saved.", contract_page.messages)
        # Verify that grid row displayed
        self.assert_initial_columns(contract_page.grid_columns)
        self.assert_grid_row(
                contract_page.get_row({'Contract Name': contract_name}),
                {
                    'Contract Name': contract_name,
                    'Contract Type': self.CONTRACT_TYPE_NAME,
                    'Invitation Code': invitation_code,
                    'Contract Start Date': start_date,
                    'Contract End Date': end_date,
                    'Contractor Organization Name': self.CONTRACTOR_ORGANIZATION_NAME
                }
        )

    def test_delete_success(self):
        """
        Tests delete contract.
        Case 53
        """
        # Visit register view
        BizNavPage(self.browser).visit().click_contract().click_register_button()
        detail_page = BizContractDetailPage(self.browser).wait_for_page()

        # Register a contract
        contract_name = self.CONTRACTOR_ORGANIZATION_NAME + self.unique_id[0:8]
        invitation_code = self.unique_id[0:8]
        start_date = '2016/01/01'
        end_date = '2100/01/01'
        detail_page.input(contract_name=contract_name, contract_type=self.CONTRACT_TYPE,
                          invitation_code=invitation_code,
                          start_date=start_date, end_date=end_date) \
            .add_detail_info(self.course_id, 1) \
            .add_additional_info(u'部署', 1) \
            .click_register_button()
        contract_page = BizContractPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_delete_success_1')

        # Visit detail view
        detail_page = contract_page.click_grid_row({'Contract Name': contract_name}, BizContractDetailPage)
        bok_choy.browser.save_screenshot(self.browser, 'test_delete_success_2')

        # Delete the contract
        contract_page = detail_page.click_delete_button().click_popup_yes(BizContractPage)
        bok_choy.browser.save_screenshot(self.browser, 'test_delete_success_3')

        # Verify that an error is displayed
        self.assertIn("The contract has been deleted.", contract_page.messages)
        # Verify that delete contract removed from grid
        self.assertIsNone(contract_page.get_row({'Contract Name': contract_name}))

    def test_w2ui_grid(self):
        """
        Tests contract grid.
        Case 109
        """
        # TODO Wait  w2ui implementation

    def test_restore_additional_info(self):
        """
        Tests restore additional info after delete
        Case 111
        """
        # TODO Wait  w2ui implementation

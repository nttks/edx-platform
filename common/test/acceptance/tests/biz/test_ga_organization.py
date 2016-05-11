"""
End-to-end tests for organization of biz feature
"""

from bok_choy.web_app_test import WebAppTest

from . import AGGREGATOR_USER_INFO, PLATFORMER_USER_INFO, GaccoBizTestMixin
from ...pages.biz.ga_dashboard import DashboardPage
from ...pages.biz.ga_organization import BizOrganizationPage, BizOrganizationDetailPage


class BizOrganizationTest(WebAppTest, GaccoBizTestMixin):

    def assert_initial_columns(self, grid_columns):
        self.assertEqual(len(grid_columns), 5)
        self.assertIn(u'Organization Name', grid_columns)
        self.assertIn(u'Organization Code', grid_columns)
        self.assertIn(u'Contract Count', grid_columns)
        self.assertIn(u'Manager Count', grid_columns)
        self.assertIn(u'Created Date', grid_columns)

    def assert_organization_in(self, organization_grid_rows, assert_dict):
        for organization_row in organization_grid_rows:
            for assert_key, assert_value in assert_dict.items():
                if assert_key in organization_row and assert_value == organization_row[assert_key]:
                    return
        self.fail('{} not found match row in {}'.format(assert_dict, organization_grid_rows))

    def test_view_as_platformer(self):
        """
        Test view page as platformer.
        """
        self.switch_to_user(PLATFORMER_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        self.assert_initial_columns(biz_organization_page.grid_columns)

        r = biz_organization_page.grid_rows
        self.assertGreaterEqual(len(r), 4)

    def test_view_as_aggregator(self):
        """
        Test view page as aggregator.
        """
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        self.assert_initial_columns(biz_organization_page.grid_columns)

        r = biz_organization_page.grid_rows
        self.assertGreaterEqual(len(r), 1)

    def test_register_edit_name_code_delete(self):
        """
        Test register organization,
          edit organization name and code,
          delete organization.
        - Case 18, 19, 20, 21
        """
        org_code = 'test_org_' + self.unique_id[0:8]
        org_name = 'org name ' + org_code

        org_code_edit = 'edit_test_org_' + self.unique_id[0:8]
        org_name_edit = 'edit org name ' + org_code_edit

        # register
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        biz_organization_page = biz_organization_page.click_add().input(org_name, org_code).click_register()

        self.assert_initial_columns(biz_organization_page.grid_columns)
        self.assert_grid_row(
            biz_organization_page.get_row({'Organization Name': org_name}),
            {
                'Organization Name': org_name,
                'Organization Code': org_code,
            }
        )

        # edit name
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        biz_organization_page = biz_organization_page.click_grid_row(
            {'Organization Name': org_name},
            BizOrganizationDetailPage
        ).input(org_name_edit, org_code).click_register()

        self.assert_initial_columns(biz_organization_page.grid_columns)
        self.assert_grid_row(
            biz_organization_page.get_row({'Organization Name': org_name_edit}),
            {
                'Organization Name': org_name_edit,
                'Organization Code': org_code,
            }
        )

        # edit code
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        biz_organization_page = biz_organization_page.click_grid_row(
            {'Organization Name': org_name_edit},
            BizOrganizationDetailPage
        ).input(org_name_edit, org_code_edit).click_register()

        self.assert_initial_columns(biz_organization_page.grid_columns)
        self.assert_grid_row(
            biz_organization_page.get_row({'Organization Name': org_name_edit}),
            {
                'Organization Name': org_name_edit,
                'Organization Code': org_code_edit,
            }
        )

        # delete
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        biz_organization_page = biz_organization_page.click_grid_row(
            {'Organization Name': org_name_edit},
            BizOrganizationDetailPage
        ).click_delete().click_popup_yes(BizOrganizationPage)

        self.assert_initial_columns(biz_organization_page.grid_columns)
        self.assertEqual(biz_organization_page.find_rows({'Organization Name': org_name_edit}), [])

    def test_can_not_delete_has_contract(self):
        """
        Test can not delete organization, that has a contract.
        - Case 22
        """
        # TODO after contract test
        pass

    def test_register_same_name(self):
        """
        Test register organization duplicate name.
        - Case 23
        """
        org_name = 'org name ' + self.unique_id[0:8]

        org_code_1st = 'first_test_org_' + self.unique_id[0:8]
        org_code_2nd = 'second_test_org_' + self.unique_id[0:8]

        # register
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        biz_organization_page = biz_organization_page.click_add().input(org_name, org_code_1st).click_register()

        self.assert_initial_columns(biz_organization_page.grid_columns)
        self.assert_grid_row(
            biz_organization_page.get_row({'Organization Name': org_name}),
            {
                'Organization Name': org_name,
                'Organization Code': org_code_1st,
            }
        )

        # register same name
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        biz_organization_page = biz_organization_page.click_add().input(org_name, org_code_2nd).click_register()

        self.assert_initial_columns(biz_organization_page.grid_columns)
        grid_rows = biz_organization_page.find_rows({
            'Organization Name': org_name,
        })
        self.assertEqual(len(grid_rows), 2)
        self.assert_organization_in(grid_rows, {
            'Organization Name': org_name,
            'Organization Code': org_code_1st,
        })
        self.assert_organization_in(grid_rows, {
            'Organization Name': org_name,
            'Organization Code': org_code_2nd,
        })

    def test_register_same_code(self):
        """
        Test register organization duplicate code.
        - Case 24
        """
        org_name_1st = 'first org name ' + self.unique_id[0:8]
        org_name_2nd = 'second org name ' + self.unique_id[0:8]

        org_code = 'test_org_' + self.unique_id[0:8]

        # register
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        biz_organization_page = biz_organization_page.click_add().input(org_name_1st, org_code).click_register()

        self.assert_initial_columns(biz_organization_page.grid_columns)
        self.assert_grid_row(
            biz_organization_page.get_row({'Organization Code': org_code}),
            {
                'Organization Name': org_name_1st,
                'Organization Code': org_code,
            }
        )

        # register same name
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        biz_organization_page = biz_organization_page.click_add().input(org_name_2nd, org_code).click_register()

        self.assert_initial_columns(biz_organization_page.grid_columns)
        grid_rows = biz_organization_page.find_rows({
            'Organization Code': org_code,
        })
        self.assertEqual(len(grid_rows), 2)
        self.assert_organization_in(grid_rows, {
            'Organization Name': org_name_1st,
            'Organization Code': org_code,
        })
        self.assert_organization_in(grid_rows, {
            'Organization Name': org_name_2nd,
            'Organization Code': org_code,
        })

    def test_register_no_input(self):
        """
        Test no input error when register organization.
        - Case 25
        """
        # register
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        biz_organization_register_page = biz_organization_page.click_add().click_register(False)

        self.assertEqual(
            biz_organization_register_page.input_error_messages,
            ['The field is required.', 'The field is required.']
        )

    def test_register_input_illegal_character(self):
        """
        Test illegal character error when register organization.
        - Case 26
        """
        org_name = 'org name ' + self.unique_id[0:8]
        org_code = '@@@'

        # register
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_nav = DashboardPage(self.browser).visit().click_biz()
        biz_organization_page = biz_nav.click_organization()

        biz_organization_register_page = biz_organization_page.click_add().input(org_name, org_code).click_register(False)

        self.assertEqual(
            biz_organization_register_page.input_error_messages,
            ['', 'Enter a valid value.']
        )

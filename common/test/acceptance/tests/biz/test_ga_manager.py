"""
End-to-end tests for manager of biz feature
"""

from bok_choy.web_app_test import WebAppTest
from nose.plugins.attrib import attr

from . import PLATFORMER_USER_INFO, AGGREGATOR_USER_INFO, C_COMPANY_NAME, GaccoBizTestMixin, visit_page_on_new_window
from ...pages.biz.ga_dashboard import DashboardPage
from ...pages.lms.account_settings import AccountSettingsPage
from ...pages.lms.ga_resign import (
    ResignCompletePage,
    ResignConfirmPage
)

from lms.envs.bok_choy import EMAIL_FILE_PATH


@attr('shard_ga_biz_1')
class BizManagerTest(WebAppTest, GaccoBizTestMixin):

    def _register_resigned_user(self):
        new_user = self.register_user()

        account_settings_page = AccountSettingsPage(self.browser).visit()
        account_settings_page.click_on_link_in_link_field('resign')
        account_settings_page.wait_for_message(
            'resign',
            'An email has been sent to {}. Follow the link in the email to resign.'.format(new_user['email'])
        )

        uidb36, token = self.assert_email_resign()

        ResignConfirmPage(self.browser, uidb36, token).visit().fill_resign_reason(u'Bar').submit()
        ResignCompletePage(self.browser).wait_for_page()

        return new_user

    def setUp(self):
        """
        Initiailizes the page object and setup email client
        """
        super(BizManagerTest, self).setUp()

        # Set up email client
        self.setup_email_client(EMAIL_FILE_PATH)

    def test_view_as_platformer(self):
        """
        Test view page as platformer.
        """
        self.switch_to_user(PLATFORMER_USER_INFO)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        self.assertIn(u'owner company', biz_manager_page.organizations.values())
        self.assertIn(u'A company', biz_manager_page.organizations.values())
        self.assertIn(u'B company', biz_manager_page.organizations.values())
        self.assertNotIn(u'C company', biz_manager_page.organizations.values())
        self.assertItemsEqual([u'aggregator', u'director', u'manager'], biz_manager_page.permissions.values())

    def test_view_as_aggregator(self):
        """
        Test view page as aggregator.
        """
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        self.assertNotIn(u'owner company', biz_manager_page.organizations.values())
        self.assertNotIn(u'A company', biz_manager_page.organizations.values())
        self.assertNotIn(u'B company', biz_manager_page.organizations.values())
        self.assertIn(u'C company', biz_manager_page.organizations.values())
        self.assertItemsEqual([u'director', u'manager'], biz_manager_page.permissions.values())

    def test_grant_director_with_name(self):
        """
        Test aggregator grant director with name.
        - Case 27
        """
        new_director = self.register_user()

        # grant
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'director')
        self.assertNotIn(new_director['username'], biz_manager_page.names)
        self.assertNotIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_director['username']).click_grant()
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.refresh_page().select(C_COMPANY_NAME, 'director')
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

    def test_grant_manager_with_email_revoke(self):
        """
        Test aggregator grant manager with email and revoke.
        - Case 28, 29
        """
        new_manager = self.register_user()

        # grant
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'manager')
        self.assertNotIn(new_manager['username'], biz_manager_page.names)
        self.assertNotIn(new_manager['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_manager['email']).click_grant()
        self.assertIn(new_manager['username'], biz_manager_page.names)
        self.assertIn(new_manager['email'], biz_manager_page.emails)

        biz_manager_page.refresh_page().select(C_COMPANY_NAME, 'manager')
        self.assertIn(new_manager['username'], biz_manager_page.names)
        self.assertIn(new_manager['email'], biz_manager_page.emails)

        # revoke
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'manager')
        self.assertIn(new_manager['username'], biz_manager_page.names)
        self.assertIn(new_manager['email'], biz_manager_page.emails)

        biz_manager_page.click_revoke(new_manager['username'])
        self.assertNotIn(new_manager['username'], biz_manager_page.names)
        self.assertNotIn(new_manager['email'], biz_manager_page.emails)

        biz_manager_page.refresh_page().select(C_COMPANY_NAME, 'manager')
        self.assertNotIn(new_manager['username'], biz_manager_page.names)
        self.assertNotIn(new_manager['email'], biz_manager_page.emails)

    def test_grant_director_with_name_of_not_exists(self):
        """
        Test error of name is not exists, aggregator grant director with name.
        - Case 30
        """
        username = 'hogehoge_' + self.unique_id[0:8]

        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'director')
        self.assertNotIn(username, biz_manager_page.names)

        biz_manager_page.input_user(username).click_grant()
        biz_manager_page.wait_for_message(u'The user does not exist.')

    def test_grant_director_with_email_of_not_exists(self):
        """
        Test error of email is not exists, aggregator grant director with email.
        - Case 31
        """
        email = 'hogehoge_{}@example.com'.format(self.unique_id[0:8])

        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'director')
        self.assertNotIn(email, biz_manager_page.emails)

        biz_manager_page.input_user(email).click_grant()
        biz_manager_page.wait_for_message(u'The user does not exist.')

    def test_grant_to_resigned_user(self):
        """
        Test error grant to resigned user.
        - Case 32
        """
        new_director = self._register_resigned_user()

        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'director')
        self.assertNotIn(new_director['username'], biz_manager_page.names)
        self.assertNotIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_director['username']).click_grant()
        biz_manager_page.wait_for_message(u'The user is resigned.')

    def test_grant_myself(self):
        """
        Test error grant myself.
        - Case 33
        """
        new_director = self.register_user()

        new_org = self.register_organization(AGGREGATOR_USER_INFO)
        new_contract = self.register_contract(AGGREGATOR_USER_INFO, new_org['Organization Name'])

        # grant director to new_user
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(new_org['Organization Name'], 'director')
        self.assertNotIn(new_director['username'], biz_manager_page.names)
        self.assertNotIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_director['username']).click_grant()
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.refresh_page().select(new_org['Organization Name'], 'director')
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        # grant manager myself
        self.switch_to_user(new_director)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(new_org['Organization Name'], 'manager')
        self.assertNotIn(new_director['username'], biz_manager_page.names)
        self.assertNotIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_director['username']).click_grant()
        biz_manager_page.wait_for_message(u'You can not change permissions of yourself.')

    def test_revoke_myself(self):
        """
        Test error revoke myself.
        - Case 34
        """
        new_director = self.register_user()

        new_org = self.register_organization(AGGREGATOR_USER_INFO)
        new_contract = self.register_contract(AGGREGATOR_USER_INFO, new_org['Organization Name'])

        # grant director to new_user
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(new_org['Organization Name'], 'director')
        self.assertNotIn(new_director['username'], biz_manager_page.names)
        self.assertNotIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_director['username']).click_grant()
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.refresh_page().select(new_org['Organization Name'], 'director')
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        # revoke director myself
        self.switch_to_user(new_director)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(new_org['Organization Name'], 'director')
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.click_revoke(new_director['username'])
        biz_manager_page.wait_for_message(u'You can not change permissions of yourself.')

    def test_grant_duplicate(self):
        """
        Test error grant duplicate.
        - Case 35
        """
        new_director = self.register_user()

        # grant
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'director')
        self.assertNotIn(new_director['username'], biz_manager_page.names)
        self.assertNotIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_director['username']).click_grant()
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.refresh_page().select(C_COMPANY_NAME, 'director')
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        # grant again
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'director')
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_director['email']).click_grant()
        self.assertEqual([u'The user already has the same permission.'], biz_manager_page.messages)

    def test_revoke_revoked(self):
        """
        Test error revoke permission of revoked.
        - Case 36
        """
        new_director = self.register_user()

        # grant
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'director')
        self.assertNotIn(new_director['username'], biz_manager_page.names)
        self.assertNotIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_director['username']).click_grant()
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page.refresh_page().select(C_COMPANY_NAME, 'director')
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        # revoke new window
        with visit_page_on_new_window(biz_manager_page) as biz_manager_page_new:
            # revoke
            biz_manager_page_new.select(C_COMPANY_NAME, 'director')
            self.assertIn(new_director['username'], biz_manager_page_new.names)
            self.assertIn(new_director['email'], biz_manager_page_new.emails)

            biz_manager_page_new.click_revoke(new_director['username'])
            self.assertNotIn(new_director['username'], biz_manager_page_new.names)
            self.assertNotIn(new_director['email'], biz_manager_page_new.emails)

            biz_manager_page_new.refresh_page().select(C_COMPANY_NAME, 'director')
            self.assertNotIn(new_director['username'], biz_manager_page_new.names)
            self.assertNotIn(new_director['email'], biz_manager_page_new.emails)

        # revoke current window
        self.assertIn(new_director['username'], biz_manager_page.names)
        self.assertIn(new_director['email'], biz_manager_page.emails)

        biz_manager_page_new.click_revoke(new_director['username'])
        biz_manager_page.wait_for_message(u'The user does not have permission.')

        biz_manager_page_new.refresh_page().select(C_COMPANY_NAME, 'director')
        self.assertNotIn(new_director['username'], biz_manager_page_new.names)
        self.assertNotIn(new_director['email'], biz_manager_page_new.emails)

    def test_grant_multiple_permission(self):
        """
        Test grant multiple permission to same user
        - Case 37
        """
        new_director_manager = self.register_user()

        # grant director
        self.switch_to_user(AGGREGATOR_USER_INFO)
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'director')
        self.assertNotIn(new_director_manager['username'], biz_manager_page.names)
        self.assertNotIn(new_director_manager['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_director_manager['username']).click_grant()
        self.assertIn(new_director_manager['username'], biz_manager_page.names)
        self.assertIn(new_director_manager['email'], biz_manager_page.emails)

        biz_manager_page.refresh_page().select(C_COMPANY_NAME, 'director')
        self.assertIn(new_director_manager['username'], biz_manager_page.names)
        self.assertIn(new_director_manager['email'], biz_manager_page.emails)

        # grant manager
        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager()

        biz_manager_page.select(C_COMPANY_NAME, 'manager')
        self.assertNotIn(new_director_manager['username'], biz_manager_page.names)
        self.assertNotIn(new_director_manager['email'], biz_manager_page.emails)

        biz_manager_page.input_user(new_director_manager['username']).click_grant()
        self.assertIn(new_director_manager['username'], biz_manager_page.names)
        self.assertIn(new_director_manager['email'], biz_manager_page.emails)

        biz_manager_page.refresh_page().select(C_COMPANY_NAME, 'manager')
        self.assertIn(new_director_manager['username'], biz_manager_page.names)
        self.assertIn(new_director_manager['email'], biz_manager_page.emails)

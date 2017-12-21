"""
End-to-end tests for resign feature
"""

import bok_choy.browser
from bok_choy.web_app_test import WebAppTest
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.account_settings import AccountSettingsPage
from ...pages.lms.ga_dashboard import DashboardPage
from ...pages.lms.ga_resign import (
    DisabledAccountPage,
    ResignCompletePage,
    ResignConfirmPage
)
from ...pages.lms.login_and_register import CombinedLoginAndRegisterPage
from ..ga_helpers import GaccoTestMixin
from lms.envs.ga_bok_choy import EMAIL_FILE_PATH


class ResignTest(WebAppTest, GaccoTestMixin):
    """
    Tests that the resign functionality works
    """

    def setUp(self):
        """
        Initiailizes the page object and create a test user
        """
        super(ResignTest, self).setUp()

        # Set up email client
        self.setup_email_client(EMAIL_FILE_PATH)

        self.username = 'test_' + self.unique_id[0:6]
        self.password = 'Password123'
        self.email = self.username + '@example.com'

        # Auto login and visit dashboard
        AutoAuthPage(self.browser, username=self.username, password=self.password, email=self.email).visit()
        self.dashboard_page = DashboardPage(self.browser)
        self.account_settings_page = AccountSettingsPage(self.browser)
        self.account_settings_page.visit()

    def _visit_resign_confirm_page(self):
        """
        Visits resign confirm page
        """
        # Click resign on dashboard
        self.account_settings_page.click_on_link_in_link_field('resign')
        self.account_settings_page.wait_for_message(
            'resign',
            'An email has been sent to {}. Follow the link in the email to resign.'.format(self.email)
        )

        uidb36, token = self.assert_email_resign()

        # Visit resign confirm page
        self.resign_confirm_page = ResignConfirmPage(self.browser, uidb36, token)
        self.resign_confirm_page.visit()

    def test_resign_success(self):
        """
        Tests that submitting with a valid resign reason is successful
        """
        # Visit resign confirm page
        self._visit_resign_confirm_page()

        # Submit
        self.resign_confirm_page.fill_resign_reason(u'Foo')
        bok_choy.browser.save_screenshot(self.browser, 'test_resign_success__1')
        self.resign_confirm_page.submit()
        resign_complete_page = ResignCompletePage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_resign_success__2')

        # Fail to login
        login_page = CombinedLoginAndRegisterPage(self.browser, start_page='login')
        login_page.visit()
        login_page.login(self.email, self.password)
        login_page.wait_for_errors()
        bok_choy.browser.save_screenshot(self.browser, 'test_resign_success__3')

    def test_resign_with_empty_reason(self):
        """
        Tests that submitting with an empty resign reason is not successful
        """
        # Visit resign confirm page
        self._visit_resign_confirm_page()

        # Submit
        self.resign_confirm_page.submit()

        # Verify that an error is displayed
        self.assertIn(u"Resign reason is required.", self.resign_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_resign_with_empty_reason__1')

    def test_resign_cancel(self):
        """
        Tests that cancelling is successful
        """
        # Visit resign confirm page
        self._visit_resign_confirm_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_resign_cancel__1')

        # Cancel
        self.resign_confirm_page.cancel()
        self.dashboard_page.wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_resign_cancel__2')

"""
End-to-end tests for password reset feature
"""

import re

import bok_choy.browser
from bok_choy.web_app_test import WebAppTest
from ...pages.common.logout import LogoutPage
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.ga_dashboard import DashboardPage
from ...pages.lms.ga_password_reset import PasswordResetCompletePage, PasswordResetConfirmPage
from ...pages.lms.login_and_register import CombinedLoginAndRegisterPage
from ..ga_helpers import GaccoTestMixin
from lms.envs.bok_choy import (
    EMAIL_FILE_PATH,
    PASSWORD_COMPLEXITY,
    PASSWORD_DICTIONARY,
    PASSWORD_MIN_LENGTH
)


class PasswordResetTest(WebAppTest, GaccoTestMixin):
    """
    Tests that the password reset functionality works
    """

    PASSWORD_RESET_CONFIRM_MAIL_SUBJECT_PATTERN = u"^Password reset on [^$]+$"
    PASSWORD_RESET_CONFIRM_MAIL_URL_PATTERN = r'/password_reset_confirm/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/'

    def setUp(self):
        """
        Initiailizes the page object and create a test user
        """
        super(PasswordResetTest, self).setUp()

        # Set up email client
        self.setup_email_client(EMAIL_FILE_PATH)

        self.username = 'Test_' + self.unique_id[0:6]
        self.password = 'Password123'
        self.email = self.username + '@example.com'

        # Auto login and visit dashboard
        AutoAuthPage(self.browser, username=self.username, password=self.password, email=self.email).visit()
        self.dashboard_page = DashboardPage(self.browser)
        self.dashboard_page.visit()

    def _visit_password_reset_confirm_page(self):
        """
        Visits password reset confirm page
        """
        # Click reset password on dashboard
        self.dashboard_page.click_reset_password()

        # Get keys from email
        email_message = self.email_client.get_latest_message()
        self.assertIsNotNone(re.match(self.PASSWORD_RESET_CONFIRM_MAIL_SUBJECT_PATTERN, email_message['subject']))
        matches = re.search(self.PASSWORD_RESET_CONFIRM_MAIL_URL_PATTERN, email_message['body'], re.MULTILINE)
        self.assertIsNotNone(matches)
        uidb36= matches.groupdict()['uidb36']
        token = matches.groupdict()['token']

        # Visit password reset confirm page
        self.password_reset_confirm_page = PasswordResetConfirmPage(self.browser, uidb36, token)
        self.password_reset_confirm_page.visit()

    def test_reset_password_success(self):
        """
        Tests that submitting with a valid password is successful
        """
        # Visit password reset confirm page
        self._visit_password_reset_confirm_page()

        # Submit
        new_password = 'Good1234'
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_success__1')
        self.password_reset_confirm_page.submit()
        password_reset_complete_page = PasswordResetCompletePage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_success__2')

        # Logout
        LogoutPage(self.browser).visit()
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_success__3')

        # Fail to login with old password
        login_page = CombinedLoginAndRegisterPage(self.browser, start_page='login')
        login_page.visit()
        login_page.login(self.email, self.password)
        self.assertIn(u"Email or password is incorrect.", login_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_success__4')

        # Succeed to login with new password
        login_page.login(self.email, new_password)
        self.dashboard_page.wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_success__5')

    def test_reset_password_with_invalid_length_password(self):
        """
        Tests that submitting with an invalid password is not successful
        """
        # Visit password reset confirm page
        self._visit_password_reset_confirm_page()

        new_password = ''
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Password: Invalid Length (must be {0} characters or more)".format(PASSWORD_MIN_LENGTH)
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_invalid_length_password__1')

        new_password = 'Bad1234'
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Password: Invalid Length (must be {0} characters or more)".format(PASSWORD_MIN_LENGTH)
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_invalid_length_password__2')

    def test_reset_password_with_less_complex_password(self):
        """
        Tests that submitting with a less complex password is not successful
        """
        # Visit password reset confirm page
        self._visit_password_reset_confirm_page()

        new_password = 'bad12345'
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Password: Must be more complex (must contain {upper} or more uppercase characters)".format(
            upper=PASSWORD_COMPLEXITY['UPPER'],
        )
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_less_complex_password__1')

        new_password = 'BAD12345'
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Password: Must be more complex (must contain {lower} or more lowercase characters)".format(
            lower=PASSWORD_COMPLEXITY['LOWER'],
        )
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_less_complex_password__2')

        new_password = 'Badddddd'
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Password: Must be more complex (must contain {digits} or more digits)".format(
            digits=PASSWORD_COMPLEXITY['DIGITS'],
        )
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_less_complex_password__3')

        new_password = '12345678'
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Password: Must be more complex (must contain {upper} or more uppercase characters, must contain {lower} or more lowercase characters)".format(
            upper=PASSWORD_COMPLEXITY['UPPER'],
            lower=PASSWORD_COMPLEXITY['LOWER'],
        )
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_less_complex_password__4')

        new_password = 'badddddd'
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Password: Must be more complex (must contain {upper} or more uppercase characters, must contain {digits} or more digits)".format(
            upper=PASSWORD_COMPLEXITY['UPPER'],
            digits=PASSWORD_COMPLEXITY['DIGITS'],
        )
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_less_complex_password__5')

        new_password = 'BADDDDDD'
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Password: Must be more complex (must contain {lower} or more lowercase characters, must contain {digits} or more digits)".format(
            lower=PASSWORD_COMPLEXITY['LOWER'],
            digits=PASSWORD_COMPLEXITY['DIGITS'],
        )
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_less_complex_password__6')

        new_password = '********'
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Password: Must be more complex (must contain {upper} or more uppercase characters, must contain {lower} or more lowercase characters, must contain {digits} or more digits)".format(
            upper=PASSWORD_COMPLEXITY['UPPER'],
            lower=PASSWORD_COMPLEXITY['LOWER'],
            digits=PASSWORD_COMPLEXITY['DIGITS'],
        )
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_less_complex_password__7')

    def test_reset_password_with_same_password_as_dictionary_word(self):
        """
        Tests that submitting with the same password as the dictionary word is not successful
        """
        # Visit password reset confirm page
        self._visit_password_reset_confirm_page()

        new_password = PASSWORD_DICTIONARY[0]
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Password: Too similar to a restricted dictionary word."
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_same_password_as_dictionary_word__1')

    def test_reset_password_with_same_password_as_username(self):
        """
        Tests that submitting with the same password as the username is not successful
        """
        # Visit password reset confirm page
        self._visit_password_reset_confirm_page()

        new_password = self.username
        self.password_reset_confirm_page.fill_password(new_password, new_password)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"Username and password fields cannot match"
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_same_password_as_username__1')

    def test_reset_password_with_empty_password_cofirmation(self):
        """
        Tests that submitting with an empty password confirmation is not successful
        """
        # Visit password reset confirm page
        self._visit_password_reset_confirm_page()

        new_password1 = 'Good1234'
        new_password2 = ''
        self.password_reset_confirm_page.fill_password(new_password1, new_password2)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"New password confirmation is required."
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_empty_password_cofirmation__1')

    def test_reset_password_with_different_password_cofirmation(self):
        """
        Tests that submitting with a different password confirmation is not successful
        """
        # Visit password reset confirm page
        self._visit_password_reset_confirm_page()

        new_password1 = 'Good1234'
        new_password2 = 'Goody123'
        self.password_reset_confirm_page.fill_password(new_password1, new_password2)
        self.password_reset_confirm_page.submit()
        # Verify that an error is displayed
        expected_error = u"The two password fields didn't match."
        self.assertIn(expected_error, self.password_reset_confirm_page.wait_for_errors())
        bok_choy.browser.save_screenshot(self.browser, 'test_reset_password_with_different_password_cofirmation__1')

# -*- coding: utf-8 -*-
"""
End-to-end tests for the LMS registration flow.
"""
import re
import requests

from bok_choy.web_app_test import WebAppTest
from lms.envs.ga_bok_choy import EMAIL_FILE_PATH
from ...fixtures.course import CourseFixture
from ...pages.lms import BASE_URL
from ...pages.lms.account_settings import AccountSettingsPage
from ...pages.lms.ga_dashboard import DashboardPage
from ...pages.lms.ga_header_footer import HeaderPage, FooterPage
from ...pages.lms.ga_register import ActivationPage
from ...pages.lms.login_and_register import CombinedLoginAndRegisterPage
from ..ga_helpers import GaccoTestMixin


class RegistrationTest(WebAppTest, GaccoTestMixin):
    """
    Test the registration process.
    """

    USERNAME = 'STUDENT_TESTER'
    EMAIL = 'student101@example.com'
    PASSWORD = 'openedX101'
    FULL_NAME = 'STUDENT TESTER'

    # Global course
    GLOBAL_COURSE_ORG = 'test_org'
    GLOBAL_COURSE_NUM = 'test_global_course'
    GLOBAL_COURSE_RUN = 'test_run'
    GLOBAL_COURSE_DISPLAY = 'Test Global Course'

    ACTIVATION_URL_PATTERN = r'/activate/(?P<token>[0-9A-Za-z-]+)'

    def setUp(self):
        """
        Initialize pages.
        """
        super(RegistrationTest, self).setUp()

        self.register_page = CombinedLoginAndRegisterPage(self.browser)
        self.header_page = HeaderPage(self.browser)
        self.footer_page = FooterPage(self.browser)

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # Set window size
        self.setup_window_size_for_pc()

    def _get_activation_key_from_message(self, message):
        """
        Returns the activation key from email content.
        """
        matches = re.search(self.ACTIVATION_URL_PATTERN, message, re.MULTILINE)
        if matches:
            return matches.groupdict()['token']
        raise Exception('Activation key not found.')

    def assert_header_footer_link(self, is_login):
        ## Header links
        # Check link of logo
        self.assertEqual(
            BASE_URL + '/',
            requests.get(self.header_page.top_page, allow_redirects=False).headers['Location']
        )
        if is_login:
            # Check link of FAQ
            self.assertEqual(
                'https://support.gacco.org/',
                requests.get(self.header_page.navigation_menu_links[2], allow_redirects=False).headers['Location']
            )

        ## Footer links
        # Check link of terms of service
        self.assertEqual(
            'https://support.gacco.org/hc/ja/articles/204058544',
            requests.get(self.footer_page.get_navigation_link('nav-colophon-01'), allow_redirects=False).headers['Location']
        )
        # Check link of privacy policy
        self.assertEqual(
            'https://support.gacco.org/hc/ja/articles/204245440',
            requests.get(self.footer_page.get_navigation_link('nav-colophon-02'), allow_redirects=False).headers['Location']
        )
        # Check link of FAQ
        self.assertEqual(
            'https://support.gacco.org/',
            requests.get(self.footer_page.get_navigation_link('nav-colophon-03'), allow_redirects=False).headers['Location']
        )

        # bok-choy test can't change language, so generate other language url by en url
        # Check link of terms of service(ja)
        self.assertEqual(
            'https://support.gacco.org/hc/ja/articles/200749224',
            requests.get(self.footer_page.get_navigation_link_ja('nav-colophon-01'), allow_redirects=False).headers['Location']
        )
        # Check link of privacy policy(ja)
        self.assertEqual(
            'https://support.gacco.org/hc/ja/articles/200749314',
            requests.get(self.footer_page.get_navigation_link_ja('nav-colophon-02'), allow_redirects=False).headers['Location']
        )

    def test_register_and_activate(self):
        # Create a course to register for
        course_id = CourseFixture(
            self.GLOBAL_COURSE_ORG, self.GLOBAL_COURSE_NUM,
            self.GLOBAL_COURSE_RUN, self.GLOBAL_COURSE_DISPLAY
        ).install()._course_key

        with self.setup_global_course(course_id):
            # Visit register page
            self.register_page.visit()

            # Check marketing link in header and footer
            self.assert_header_footer_link(is_login=False)

            # User ragistration
            self.register_page.register(
                email=self.EMAIL, password=self.PASSWORD, username=self.USERNAME,
                full_name=self.FULL_NAME, terms_of_service=True
            )

            # Check activation email.
            activation_message = self.email_client.get_latest_message()
            self.assertEqual(self.EMAIL, activation_message['to_addresses'])
            self.assertEqual("Information of edX Member Registration", activation_message['subject'])
            self.assertIn("Information of gacco Member Registration", activation_message['body'])

            # Visit activation page.
            activation_key = self._get_activation_key_from_message(activation_message['body'])
            activation_page = ActivationPage(self.browser, activation_key)
            activation_page.visit()
            self.assertIn("Thanks for activating your account.", activation_page.complete_message)

            activation_page.click_login_button()
            login_page = CombinedLoginAndRegisterPage(
                self.browser,
                start_page="login",
            )
            login_page.wait_for_page()
            login_page.login(email=self.EMAIL, password=self.PASSWORD)

            dashboard_page = DashboardPage(self.browser)
            dashboard_page.wait_for_page()

            # Check marketing link in header and footer
            self.assert_header_footer_link(is_login=True)

            # Check global course is enrolled.
            self.assertFalse(dashboard_page.is_exists_notification())
            self.assertIn(self.GLOBAL_COURSE_DISPLAY, dashboard_page.current_courses_text)
            self.assertFalse(dashboard_page.is_enable_unenroll(self.GLOBAL_COURSE_DISPLAY))

    def test_third_party_register(self):
        """
        Test that we can register using third party credentials, and that the
        third party account gets linked to the edX account.
        """
        # Navigate to the register page and try to authenticate using the "Dummy" provider
        self.register_page.visit()
        self.register_page.click_third_party_dummy_provider()

        # The user will be redirected somewhere and then back to the register page:
        msg_text = self.register_page.wait_for_auth_status_message()
        self.assertEqual(self.register_page.current_form, "register")
        self.assertIn("You've successfully signed into Dummy", msg_text)
        self.assertIn("We just need a little more information", msg_text)

        # Now the form should be pre-filled with the data from the Dummy provider:
        self.assertEqual(self.register_page.email_value, "adama@fleet.colonies.gov")
        self.assertEqual(self.register_page.full_name_value, "William Adama")
        self.assertEqual("", self.register_page.username_value)

        # Set username, country, accept the terms, and submit the form:
        self.register_page.register(username="Galactica1", country="US", terms_of_service=True)
        self.register_page.wait_for_ajax()

        # Check activation email.
        activation_message = self.email_client.get_latest_message()
        self.assertEqual('adama@fleet.colonies.gov', activation_message['to_addresses'])
        self.assertEqual("Information of edX Member Registration", activation_message['subject'])
        self.assertIn("Information of gacco Member Registration", activation_message['body'])

        # Visit activation page.
        activation_key = self._get_activation_key_from_message(activation_message['body'])
        activation_page = ActivationPage(self.browser, activation_key)
        activation_page.visit()
        self.assertIn("Thanks for activating your account.", activation_page.complete_message)

        activation_page.click_login_button()
        login_page = CombinedLoginAndRegisterPage(self.browser, start_page="login")
        login_page.wait_for_page()
        login_page.click_third_party_dummy_provider()

        dashboard_page = DashboardPage(self.browser)
        dashboard_page.wait_for_page()

        # Now unlink the account (To test the account settings view and also to prevent cross-test side effects)
        account_settings = AccountSettingsPage(self.browser).visit()
        field_id = "auth-oa2-dummy"
        account_settings.wait_for_field(field_id)
        self.assertEqual("Unlink", account_settings.link_title_for_link_field(field_id))
        account_settings.click_on_link_in_link_field(field_id)
        account_settings.wait_for_message(field_id, "Successfully unlinked")

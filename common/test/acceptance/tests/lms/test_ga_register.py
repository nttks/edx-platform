# -*- coding: utf-8 -*-
"""
End-to-end tests for the LMS registration flow.
"""

import re
import requests
from nose.plugins.attrib import attr

from bok_choy.web_app_test import WebAppTest
from lms.envs.bok_choy import EMAIL_FILE_PATH
from ...fixtures.course import CourseFixture
from ...pages.lms.ga_header_footer import HeaderPage, FooterPage
from ...pages.lms.ga_register import RegisterPage, ActivationPage
from ..ga_helpers import EmailTestMixin


@attr('shard_ga')
class RegistrationTest(WebAppTest, EmailTestMixin):
    """
    Test the registration process.
    """

    USERNAME = 'STUDENT_TESTER'
    EMAIL = 'student101@example.com'
    PASSWORD = 'openedX101'
    FULL_NAME = 'STUDENT TESTER'

    # Global course is inserted by db_fixture/ga_global_course.json.
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

        self.register_page = RegisterPage(self.browser)
        self.header_page = HeaderPage(self.browser)
        self.footer_page = FooterPage(self.browser)

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

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
            'http://gacco.org/',
            requests.get(self.header_page.logo_link, allow_redirects=False).headers['Location']
        )
        if is_login:
            # Check link of FAQ
            self.assertEqual(
                'https://support.gacco.org/',
                requests.get(self.header_page.navigation_menu_links[0], allow_redirects=False).headers['Location']
            )

        ## Footer links
        # Check link of terms of service
        self.assertEqual(
            'https://support.gacco.org/hc/ja/articles/200749224',
            requests.get(self.footer_page.get_navigation_link('nav-colophon-01'), allow_redirects=False).headers['Location']
        )
        # Check link of privacy policy
        self.assertEqual(
            'https://support.gacco.org/hc/ja/articles/200749314',
            requests.get(self.footer_page.get_navigation_link('nav-colophon-02'), allow_redirects=False).headers['Location']
        )
        # Check link of FAQ
        self.assertEqual(
            'https://support.gacco.org/',
            requests.get(self.footer_page.get_navigation_link('nav-colophon-03'), allow_redirects=False).headers['Location']
        )

    def test_register_and_activate(self):
        # Create a course to register for
        CourseFixture(
            self.GLOBAL_COURSE_ORG, self.GLOBAL_COURSE_NUM,
            self.GLOBAL_COURSE_RUN, self.GLOBAL_COURSE_DISPLAY
        ).install()

        # Visit register page
        self.register_page.visit()

        # Check marketing link in header and footer
        self.assert_header_footer_link(is_login=False)

        # User ragistration
        self.register_page.provide_info(self.EMAIL, self.PASSWORD, self.USERNAME, self.FULL_NAME)
        dashboard_page = self.register_page.submit()

        # Check successfully registerered and logged in.
        self.assertIn(self.EMAIL, dashboard_page.activation_message[0])
        self.assertIn("Looks like you haven't enrolled in any courses yet.", dashboard_page.current_courses_text)

        # Check marketing link in header and footer
        self.assert_header_footer_link(is_login=True)

        # Check activation email.
        activation_message = self.email_client.get_latest_message()
        self.assertEqual(self.EMAIL, activation_message['to_addresses'])
        self.assertEqual("Activate Your edX Account", activation_message['subject'])
        self.assertIn("Thank you for signing up for", activation_message['body'])

        # Visit activation page.
        activation_key = self._get_activation_key_from_message(activation_message['body'])
        activation_page = ActivationPage(self.browser, activation_key)
        activation_page.visit()

        self.assertIn("Thanks for activating your account.", activation_page.complete_message)

        # Visit dashboard again
        dashboard_page.visit()

        # Check global course is enrolled.
        self.assertFalse(dashboard_page.is_exists_notification())
        self.assertIn(self.GLOBAL_COURSE_DISPLAY, dashboard_page.current_courses_text)
        self.assertFalse(dashboard_page.is_enable_unenroll(self.GLOBAL_COURSE_DISPLAY))

# -*- coding: utf-8 -*-
"""
End-to-end tests for the LMS Instructor Dashboard.
"""

from nose.plugins.attrib import attr

from bok_choy.web_app_test import WebAppTest
from ...fixtures.course import CourseFixture
from ...fixtures.ga_course_team import CourseTeamFixture
from ...pages.common.logout import LogoutPage
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.ga_dashboard import DashboardPage
from ...pages.lms.ga_instructor_dashboard import InstructorDashboardPage
from ...pages.lms.ga_login import LoginPage
from ..ga_helpers import EmailTestMixin
from lms.envs.bok_choy import EMAIL_FILE_PATH


@attr('shard_ga')
class SendEmailTest(WebAppTest, EmailTestMixin):
    """
    Test the send email process.
    """

    # Email course is inserted by db_fixture/ga_course_authorization.json.
    EMAIL_COURSE_ORG = 'test_org'
    EMAIL_COURSE_RUN = 'test_run'
    EMAIL_COURSE_DISPLAY = 'Test Email Course'

    def setUp(self):
        """
        Initialize pages and install fixtures.
        """
        super(SendEmailTest, self).setUp()

        # Create a course to register for
        course = CourseFixture(
            self.EMAIL_COURSE_ORG, self._testMethodName,
            self.EMAIL_COURSE_RUN, self.EMAIL_COURSE_DISPLAY
        ).install()
        self.course_key = course._course_key

        # Create users
        username_global_staff = 'test_globalstaff_' + self.unique_id[0:6]
        username_course_staff = 'test_coursestaff_' + self.unique_id[0:6]
        username_course_instructor = 'test_courseinstructor_' + self.unique_id[0:6]

        self.user_global_staff = {'username': username_global_staff, 'email': username_global_staff + '@example.com'}
        self.user_course_staff = {'username': username_course_staff, 'email': username_course_staff + '@example.com'}
        self.user_course_instructor = {'username': username_course_instructor, 'email': username_course_instructor + '@example.com'}

        self._create_user(self.user_global_staff, self.course_key, True)
        self._create_user(self.user_course_staff, self.course_key, False)
        self._create_user(self.user_course_instructor, self.course_key, False)

        # Add course team members
        CourseTeamFixture(self.course_key, self.user_course_staff['email'], False).install()
        CourseTeamFixture(self.course_key, self.user_course_instructor['email'], True).install()

        # Initialize pages.
        self.instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course_key)
        self.login_page = LoginPage(self.browser)
        self.logout_page = LogoutPage(self.browser)

        # Set up email client
        self.setup_email_client(EMAIL_FILE_PATH)

    def _create_user(self, user, course_key, staff):
        AutoAuthPage(
            self.browser,
            username=user['username'],
            email=user['email'],
            password='edx',
            course_id=course_key,
            staff=staff
        ).visit()
        LogoutPage(self.browser).visit()

    def test_displayed_optout_checkbox_only_global_staff(self):
        """
        Scenario:
            Elements about opt-out are displayed only when global-staff access and select all in the send_to select.
        """

        ## login as global staff ##
        self.login_page.visit()
        self.login_page.login(self.user_global_staff['email'], 'edx')

        # Visit instructor dashboard and send email section
        self.instructor_dashboard_page.visit()
        send_email_section = self.instructor_dashboard_page.select_send_email()

        # Select myself
        send_email_section.select_send_to('myself')
        self.assertFalse(send_email_section.is_visible_optout_container())

        # Select staff
        send_email_section.select_send_to('staff')
        self.assertFalse(send_email_section.is_visible_optout_container())

        # Select all
        send_email_section.select_send_to('all')
        self.assertTrue(send_email_section.is_visible_optout_container())

        # Logout
        self.logout_page.visit()

        ## login as instructor ##
        self.login_page.visit()
        self.login_page.login(self.user_course_instructor['email'], 'edx')

        # Visit instructor dashboard and send email section
        self.instructor_dashboard_page.visit()
        send_email_section = self.instructor_dashboard_page.select_send_email()

        # Select all
        send_email_section.select_send_to('all')
        self.assertFalse(send_email_section.is_visible_optout_container())

        # Logout
        self.logout_page.visit()

        ## login as course staff ##
        self.login_page.visit()
        self.login_page.login(self.user_course_staff['email'], 'edx')

        # Visit instructor dashboard and send email section
        self.instructor_dashboard_page.visit()
        send_email_section = self.instructor_dashboard_page.select_send_email()

        # Select all
        send_email_section.select_send_to('all')
        self.assertFalse(send_email_section.is_visible_optout_container())

        # Logout
        self.logout_page.visit()

    def test_send_to_all_include_optout(self):
        """
        Scenario:
            If you have not selected the opt-out checkbox, then mail is not sent to the opt-out user.
            And if it is selected, then mail is send to the opt-out user.
        """

        # Create student and set email off.
        user_optout = {'username': 'test_optout', 'email': 'test_optout@example.com'}
        self._create_user(user_optout, self.course_key, False)
        self.login_page.visit()
        self.login_page.login(user_optout['email'], 'edx')
        dashboard_page = DashboardPage(self.browser)
        dashboard_page.change_email_settings(self.EMAIL_COURSE_DISPLAY)
        self.logout_page.visit()

        # Login as global staff
        self.login_page.visit()
        self.login_page.login(self.user_global_staff['email'], 'edx')

        # Visit instructor dashboard and send email section
        self.instructor_dashboard_page.visit()
        send_email_section = self.instructor_dashboard_page.select_send_email()

        # Select all
        send_email_section.select_send_to('all')

        # Send message without opt-out
        send_email_section.set_title('test title')
        send_email_section.set_message('test message')

        with send_email_section.handle_alert():
            send_email_section.send()

        # Assert to_addresses.
        # this filtering is the process for excluding users to be automatically created by fixture.
        messages = filter(lambda msg: msg['to_addresses'].startswith('test_'), self.email_client.get_messages())
        self.assertItemsEqual([
            self.user_global_staff['email'],
            self.user_course_instructor['email'],
            self.user_course_staff['email']
        ], [message['to_addresses'] for message in messages])

        self.email_client.clear_messages()

        # Check include opt-out
        with send_email_section.handle_alert():
            send_email_section.check_include_optout()
        # Send message
        with send_email_section.handle_alert():
            send_email_section.send()

        # Assert to_addresses.
        # this filtering is the process for excluding users to be automatically created by fixture.
        messages = filter(lambda msg: msg['to_addresses'].startswith('test_'), self.email_client.get_messages())
        self.assertItemsEqual([
            self.user_global_staff['email'],
            self.user_course_instructor['email'],
            self.user_course_staff['email'],
            user_optout['email']
        ], [message['to_addresses'] for message in messages])

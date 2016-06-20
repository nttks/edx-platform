# -*- coding: utf-8 -*-
"""
End-to-end tests for the LMS Instructor Dashboard.
"""
import requests

from bok_choy.web_app_test import WebAppTest
from ...fixtures.course import CourseFixture
from ...fixtures.ga_course_team import CourseTeamFixture
from ...pages.common.logout import LogoutPage
from ...pages.lms import BASE_URL
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.ga_advanced_course import AdvancedF2FCoursesPage
from ...pages.lms.ga_dashboard import DashboardPage
from ...pages.lms.ga_instructor_dashboard import InstructorDashboardPage
from ...pages.lms.login_and_register import CombinedLoginAndRegisterPage
from ..ga_helpers import GaccoTestMixin
from lms.envs.ga_bok_choy import EMAIL_FILE_PATH


class SendEmailTest(WebAppTest, GaccoTestMixin):
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
        _is_f2f_testcase = self._testMethodName in ['test_send_to_advanced_course']
        course = CourseFixture(
            self.EMAIL_COURSE_ORG, self._testMethodName,
            self.EMAIL_COURSE_RUN, self.EMAIL_COURSE_DISPLAY,
            settings={
                'is_f2f_course': {'value': _is_f2f_testcase},
                'is_f2f_course_sell': {'value': _is_f2f_testcase},
            }
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
        self.dashboard_page = DashboardPage(self.browser)
        self.instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course_key)
        self.login_page = CombinedLoginAndRegisterPage(self.browser, start_page='login')
        self.logout_page = LogoutPage(self.browser)

        # Set up email client
        self.setup_email_client(EMAIL_FILE_PATH)

        # Set window size
        self.setup_window_size_for_pc()

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

    def _login(self, email, password='edx'):
        self.login_page.visit()
        self.login_page.login(email, password)
        self.dashboard_page.wait_for_page()

    def test_displayed_optout_checkbox_only_global_staff(self):
        """
        Scenario:
            Elements about opt-out are displayed only when global-staff access and select all in the send_to select.
        """

        ## login as global staff ##
        self._login(self.user_global_staff['email'])

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
        self._login(self.user_course_instructor['email'])

        # Visit instructor dashboard and send email section
        self.instructor_dashboard_page.visit()
        send_email_section = self.instructor_dashboard_page.select_send_email()

        # Select all
        send_email_section.select_send_to('all')
        self.assertFalse(send_email_section.is_visible_optout_container())

        # Logout
        self.logout_page.visit()

        ## login as course staff ##
        self._login(self.user_course_staff['email'])

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
        self._login(user_optout['email'])
        self.dashboard_page.change_email_settings(self.EMAIL_COURSE_DISPLAY)
        self.logout_page.visit()

        # Login as global staff
        self._login(self.user_global_staff['email'])

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

    def test_send_to_advanced_course(self):
        """
        Senario:
            1. Visit email section of instructor dashboard
                First, select element of advanced course is not shown.
            2. Select 'advanced_course'
                then that is shown.
            3. Select target advanced course
            4. Send message
        """
        def _purchase_ticket(advanced_course_number, ticket_number, is_purchased=True):
            advanced_f2f_courses_page = AdvancedF2FCoursesPage(self.browser, self.course_key)
            logout_page = LogoutPage(self.browser)

            _username = 'test_user_' + self.unique_id[0:6]
            _email = _username + '@example.com'
            user = AutoAuthPage(
                self.browser,
                username=_username,
                email=_email,
                course_id=self.course_key
            ).visit().user_info

            _advanced_course_name = 'Test Advance Course {} {}'.format(
                self._testMethodName, advanced_course_number
            )
            _ticket_name = '{} Ticket {}'.format(_advanced_course_name, ticket_number)

            # purchase flow
            advanced_f2f_courses_page.visit()
            choose_ticket_page = advanced_f2f_courses_page.subscribe_by_summary(_advanced_course_name)
            payment_page = choose_ticket_page.purchase(_ticket_name)
            if is_purchased:
                receipt_page = payment_page.submit_payment('card')
                receipt_number = receipt_page.get_receipt_number()

            logout_page.visit()

            return (user, receipt_number) if is_purchased else (user, None)

        def _refund_ticket(order_id, amount, tax, currency='JPN'):
            requests.post(
                '{base}/ga_shoppingcart/notify'.format(base=BASE_URL),
                data={
                    'p001': 'abcd123',
                    "p002": "22222222",
                    "p005": order_id,
                    "p006": "VOID",
                    "p007": "VOID",
                    "p008": str(amount),
                    "p009": str(tax),
                    "p010": currency,
                    "p017": "",
                    "p018": "",
                    "p019": "0"
                }
            )

        ## Create purchase data
        # 2 purchased target course
        users = [user for user, _ in [
            _purchase_ticket(advanced_course_number=2, ticket_number=1),
            _purchase_ticket(advanced_course_number=2, ticket_number=2),
        ]]
        # purchase `NOT` target course
        _purchase_ticket(advanced_course_number=1, ticket_number=1),
        ## purchase target course and refunded
        _, _refund_order_number = _purchase_ticket(advanced_course_number=2, ticket_number=1)
        _refund_ticket(_refund_order_number, 5000, 400)
        # paying target course
        _purchase_ticket(advanced_course_number=2, ticket_number=2, is_purchased=False)

        # clear messages (order complete mail does not need in this test case)
        self.email_client.clear_messages()

        ## login as global staff ##
        self._login(self.user_course_staff['email'])

        # Visit instructor dashboard and send email section
        self.instructor_dashboard_page.visit()
        send_email_section = self.instructor_dashboard_page.select_send_email()

        # Assert advanced_course element is not visible
        self.assertFalse(send_email_section.is_visible_advanced_course())

        # Select advanced_course
        send_email_section.select_send_to('advanced_course')
        # Assert advanced_course element is visible
        self.assertTrue(send_email_section.is_visible_advanced_course())

        # Select target advanced_course
        send_email_section.select_advanced_course('Test Advance Course {} 2'.format(self._testMethodName))

        # Send message without opt-out
        send_email_section.set_title('test title')
        send_email_section.set_message('test message')

        with send_email_section.handle_alert():
            send_email_section.send()

        _expected_emails = [
            user['email'] for user in users
        ] + [self.user_course_instructor['email'], self.user_course_staff['email']]

        # this filtering is the process for excluding users to be automatically created by fixture.
        messages = filter(lambda msg: msg['to_addresses'].startswith('test_'), self.email_client.get_messages())

        self.assertItemsEqual(_expected_emails, [msg['to_addresses'] for msg in messages])

"""
End-to-end tests for receive email
"""
from common.test.acceptance.fixtures.course import CourseFixture

from ..ga_helpers import GaccoTestMixin
from ..helpers import UniqueCourseTest

from ...pages.lms.ga_account_settings import AccountSettingsPage
from ...pages.lms.ga_dashboard import DashboardPage


class ReceiveEmailTest(UniqueCourseTest, GaccoTestMixin):

    def setUp(self):
        """
        Initiailizes the page object and create a test user
        """
        super(ReceiveEmailTest, self).setUp()

        CourseFixture(
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run'],
            self.course_info['display_name'],
        ).install()

        username = 'test_' + self.unique_id[0:6]
        self.user_info = {
            'username': username,
            'password': 'Password123',
            'email': username + '@example.com'
        }

        self.dashboard_page = DashboardPage(self.browser)
        self.account_settings_page = AccountSettingsPage(self.browser)

    def test_accout_settings(self):
        """
        Test on account settings
        """
        # visit account settings with global course
        with self.setup_global_course(self.course_id):
            self.switch_to_user(self.user_info)
            self.account_settings_page.visit().wait_for_loading_receive_email()
            self.assertTrue(self.account_settings_page.is_optin_receive_email)

            # to optout
            self.account_settings_page.click_receive_email()
            self.assertTrue(self.account_settings_page.is_optout_receive_email)

            # to optin
            self.account_settings_page.click_receive_email()
            self.assertTrue(self.account_settings_page.is_optin_receive_email)

        # visit account settings without global course
        self.switch_to_user(self.user_info)
        self.account_settings_page.visit().wait_for_receive_email()
        self.assertFalse(self.account_settings_page.visible_receive_email)

    def test_dashboard(self):
        """
        Test on dashboard
        """

        # visit dashboard without global course
        self.switch_to_user(self.user_info, course_id=self.course_id)
        self.dashboard_page.visit()
        self.assertTrue(self.dashboard_page.show_settings(self.course_info['display_name']))

        # visit dashboard with global course
        with self.setup_global_course(self.course_id):
            self.switch_to_user(self.user_info)
            self.dashboard_page.visit()
            self.assertFalse(self.dashboard_page.show_settings(self.course_info['display_name']))

        # visit dashboard without global course
        self.switch_to_user(self.user_info)
        self.dashboard_page.visit()
        self.assertTrue(self.dashboard_page.show_settings(self.course_info['display_name']))

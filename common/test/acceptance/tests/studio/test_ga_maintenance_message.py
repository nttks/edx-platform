"""
Acceptance tests for Home Page (My Courses / My Libraries).
"""
from bok_choy.web_app_test import WebAppTest

from ...pages.studio.auto_auth import AutoAuthPage
from ...pages.studio.ga_index import DashboardPage
from ...pages.studio.ga_login import LoginPage


class MaintenanceMessageTest(WebAppTest):
    """
    Test that we can create a new content library on the studio home page.
    """

    def setUp(self):
        """
        Load the helper for the home page (dashboard page)
        """
        super(MaintenanceMessageTest, self).setUp()

        self.auth_page = AutoAuthPage(self.browser, staff=True)
        self.login_page = LoginPage(self.browser)
        self.dashboard_page = DashboardPage(self.browser)

    def test_maintenancemessage_models_messages_for_all(self):
        """Test for ga_maintenance_cms.models.MaintenanceMessage messages_for_all"""
        self.login_page.visit()
        self.assertTrue(self.login_page.has_maintenance_message())
        login_titles = self.login_page.get_maintenance_message_title()
        self.assertEqual(len(login_titles), 2)
        self.assertEqual(login_titles[0], 'display2')

        self.auth_page.visit()
        self.dashboard_page.visit()
        self.assertTrue(self.dashboard_page.has_maintenance_message())
        dashboard_titles = self.dashboard_page.get_maintenance_message_title()
        self.assertEqual(len(dashboard_titles), 2)
        self.assertEqual(dashboard_titles[0], 'display2')


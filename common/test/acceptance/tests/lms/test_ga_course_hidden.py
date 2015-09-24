"""
tests for is_course_hidden.
"""
from bok_choy.web_app_test import WebAppTest
from ..ga_helpers import GaccoTestMixin
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.common.logout import LogoutPage
from ...pages.lms.ga_dashboard import DashboardPage
from ...fixtures.course import CourseFixture


class HiddenCourseTest(WebAppTest, GaccoTestMixin):
    """
    Tests that hidden course messages are displayed
    """

    # Email course is inserted by db_fixture/ga_course_authorization.json.
    EMAIL_COURSE_ORG = 'test_org'
    EMAIL_COURSE_RUN = 'test_run'
    EMAIL_COURSE_DISPLAY = 'Test Email Course'

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(HiddenCourseTest, self).setUp()

        self.course_fixture = CourseFixture(
            self.EMAIL_COURSE_ORG, self._testMethodName,
            self.EMAIL_COURSE_RUN, self.EMAIL_COURSE_DISPLAY
        )

        self.course_fixture.add_advanced_settings(
            {u"is_course_hidden":{"value":True}})
        course = self.course_fixture.install()

        self.course_id = course._course_key
        self.dashboard_page = DashboardPage(self.browser)

        # Auto-auth register for the course
        AutoAuthPage(self.browser, course_id=self.course_id).visit()

    def test_dashboard_message_and_link(self):
        """
         Scenario: 
            If is_course_hidden is True, then I see requirements message.
        """

        # visit dashboard page and make sure there is not pre-requisite course message
        self.dashboard_page.visit()
        self.assertEqual(
            self.dashboard_page.hidden_course_text, "This course has been closed.")
        self.assertFalse(self.dashboard_page.is_hidden_course_link_active(self.course_id))

        # Logout and login as a staff.
        LogoutPage(self.browser).visit()
        AutoAuthPage(self.browser, course_id=self.course_id, staff=True).visit()

        self.dashboard_page.visit()
        self.assertEqual(self.dashboard_page.hidden_course_text, "")
        self.assertTrue(self.dashboard_page.is_hidden_course_link_active(self.course_id))

    def test_dashboard_unenroll_when_course_is_closed(self):
        """
         Scenario:
            If is_course_hidden is True, then I can click unenroll-modal.
        """

        # visit dashboard page and make sure able to click unenroll
        self.dashboard_page.visit()
        self.assertTrue(self.dashboard_page.show_unenroll_settings(self.EMAIL_COURSE_DISPLAY))
        self.assertTrue(self.dashboard_page.is_available_unenroll_settings())

    def test_dashboard_email_when_course_is_closed(self):
        """
         Scenario:
            If is_course_hidden is True, then I can click email-settings-modal.
        """

        # visit dashboard page and make sure able to click email_settings
        self.dashboard_page.visit()
        self.assertTrue(self.dashboard_page.show_email_settings(self.EMAIL_COURSE_DISPLAY))
        self.assertTrue(self.dashboard_page.is_available_change_email_settings())

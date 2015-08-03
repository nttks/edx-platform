"""
tests for is_course_hidden.
"""
import unittest

from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.common.logout import LogoutPage
from ...pages.lms.ga_dashboard import DashboardPage
from ...fixtures.course import CourseFixture
from ..helpers import UniqueCourseTest


@unittest.skip("Fix https://trello.com/c/SCQugfKo/319-dogwood-courseoverview-course-hidden")
class HiddenCourseTest(UniqueCourseTest):
    """
    Tests that hidden course messages are displayed
    """

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(HiddenCourseTest, self).setUp()

        self.course_fixture = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        )
        self.course_fixture.add_advanced_settings(
            {u"is_course_hidden":{"value":True}})
        self.course_fixture.install()
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

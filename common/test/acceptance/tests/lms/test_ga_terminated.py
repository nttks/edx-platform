"""
tests for has_terminated.
"""
import datetime

from bok_choy.web_app_test import WebAppTest
from ..helpers import UniqueCourseTest
from ..ga_helpers import GaccoTestMixin, GA_GLOBAL_COURSE_CREATOR_USER_INFO, GA_OLD_COURSE_VIEWER_USER_INFO
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.common.logout import LogoutPage
from ...pages.lms.ga_dashboard import DashboardPage
from ...fixtures.course import CourseFixture


class TerminatedCourseTest(WebAppTest, GaccoTestMixin):
    """
    Tests that terminated course messages are displayed
    """

    # Email course is inserted by db_fixture/ga_course_authorization.json.
    EMAIL_COURSE_ORG = 'test_org'
    EMAIL_COURSE_RUN = 'test_run'
    EMAIL_COURSE_DISPLAY = 'Test Email Course'

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(TerminatedCourseTest, self).setUp()

        self.course_fixture = CourseFixture(
            self.EMAIL_COURSE_ORG, self._testMethodName,
            self.EMAIL_COURSE_RUN, self.EMAIL_COURSE_DISPLAY,
            settings={'terminate_start': datetime.datetime(2000, 1, 1).isoformat()}
        )

        course = self.course_fixture.install()

        self.course_id = course._course_key
        self.dashboard_page = DashboardPage(self.browser)

        # Auto-auth register for the course
        AutoAuthPage(self.browser, course_id=self.course_id).visit()

    def test_dashboard_message_and_link(self):
        """
         Scenario:
            If has_terminated is True, then I see requirements message.
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

        # Logout and login as a ga_old_course_viewer.
        self.switch_to_user(GA_OLD_COURSE_VIEWER_USER_INFO, self.course_id)

        self.dashboard_page.visit()
        self.assertEqual(self.dashboard_page.hidden_course_text, "")
        self.assertTrue(self.dashboard_page.is_hidden_course_link_active(self.course_id))

        # Logout and login as a ga_global_course_creator.
        self.switch_to_user(GA_GLOBAL_COURSE_CREATOR_USER_INFO, self.course_id)

        self.dashboard_page.visit()
        self.assertEqual(self.dashboard_page.hidden_course_text, "")
        self.assertTrue(self.dashboard_page.is_hidden_course_link_active(self.course_id))

    def test_dashboard_unenroll_when_course_has_terminated(self):
        """
         Scenario:
            If has_terminated is True, then I can click unenroll-modal.
        """

        # visit dashboard page and make sure able to click unenroll
        self.dashboard_page.visit()
        self.assertTrue(self.dashboard_page.show_unenroll_settings(self.EMAIL_COURSE_DISPLAY))
        self.assertTrue(self.dashboard_page.is_available_unenroll_settings())

    def test_dashboard_email_when_course_has_terminated(self):
        """
         Scenario:
            If has_terminated is True, then I can click email-settings-modal.
        """

        # visit dashboard page and make sure able to click email_settings
        self.dashboard_page.visit()
        self.assertTrue(self.dashboard_page.show_email_settings(self.EMAIL_COURSE_DISPLAY))
        self.assertTrue(self.dashboard_page.is_available_change_email_settings())

class HiddenCourseTest(UniqueCourseTest, GaccoTestMixin):
    """
    Tests that terminated(is_course_hidden) messages are displayed
    """

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(HiddenCourseTest, self).setUp()

        course_fixture = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        )
        course_fixture.add_advanced_settings({'is_course_hidden': {'value': 'true'}})
        course_fixture.install()

        self.dashboard_page = DashboardPage(self.browser)

    def test_dashboard_message_and_link(self):
        """
         Scenario:
            If has_terminated is True, then I see requirements message.
        """

        # Auto-auth register for the course
        AutoAuthPage(self.browser, course_id=self.course_id).visit()

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

        # Logout and login as a ga_old_course_viewer.
        self.switch_to_user(GA_OLD_COURSE_VIEWER_USER_INFO, self.course_id)

        self.dashboard_page.visit()
        self.assertEqual(self.dashboard_page.hidden_course_text, "")
        self.assertTrue(self.dashboard_page.is_hidden_course_link_active(self.course_id))

        # Logout and login as a ga_global_course_creator.
        self.switch_to_user(GA_GLOBAL_COURSE_CREATOR_USER_INFO, self.course_id)

        self.dashboard_page.visit()
        self.assertEqual(self.dashboard_page.hidden_course_text, "")
        self.assertTrue(self.dashboard_page.is_hidden_course_link_active(self.course_id))

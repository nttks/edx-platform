"""
End-to-end tests for dashboard
"""

from bok_choy.web_app_test import WebAppTest

from opaque_keys.edx.keys import CourseKey

from ..ga_helpers import GaccoTestMixin
from ..helpers import disable_animations
from ...pages.lms.ga_dashboard import DashboardPage


class DashboardTest(WebAppTest, GaccoTestMixin):

    def test_search_course(self):
        course_id, course_name = self.install_course()
        course_key = CourseKey.from_string(course_id)

        self.register_user(course_id)

        dashboard_page = DashboardPage(self.browser).visit()
        self.assertEqual([course_name], dashboard_page.displayed_course_names)

        dashboard_page.input_search_box('None Course')
        self.assertEqual([], dashboard_page.displayed_course_names)

        dashboard_page.input_search_box(course_name)
        self.assertEqual([course_name], dashboard_page.displayed_course_names)

        dashboard_page.input_search_box('None {}'.format(course_name))
        self.assertEqual([], dashboard_page.displayed_course_names)

        dashboard_page.input_search_box(course_key.org)
        self.assertEqual([course_name], dashboard_page.displayed_course_names)

        dashboard_page.input_search_box('{}{}'.format(course_key.org, course_key.course))
        self.assertEqual([], dashboard_page.displayed_course_names)

        dashboard_page.input_search_box(course_key.course)
        self.assertEqual([course_name], dashboard_page.displayed_course_names)

        dashboard_page.input_search_box('{}{}'.format(course_key.course, course_key.run))
        self.assertEqual([], dashboard_page.displayed_course_names)

        dashboard_page.input_search_box(course_key.run)
        self.assertEqual([course_name], dashboard_page.displayed_course_names)

        dashboard_page.input_search_box('{}{}'.format(course_key.org, course_key.run))
        self.assertEqual([], dashboard_page.displayed_course_names)

        dashboard_page.clear_search_box()
        self.assertEqual([course_name], dashboard_page.displayed_course_names)

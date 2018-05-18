"""
End-to-end tests for dashboard
"""
from bok_choy.web_app_test import WebAppTest

from opaque_keys.edx.keys import CourseKey

from ..ga_helpers import GaccoTestMixin
from ..helpers import UniqueCourseTest
from ...fixtures.certificates import CertificateConfigFixture
from ...fixtures.course import CourseFixture
from ...pages.lms.auto_auth import AutoAuthPage
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


class DashboardCertificateInformationFinalGradeTest(UniqueCourseTest):
    """
    Tests for certificate information on dashboard
    """

    def setUp(self):
        super(DashboardCertificateInformationFinalGradeTest, self).setUp()

    def log_in_as_unique_user(self):
        """
        Log in as a valid lms user.
        """
        AutoAuthPage(
            self.browser,
            username="testcert",
            email="cert@example.com",
            password="testuser",
            course_id=self.course_id
        ).visit()

    def test_dashboard_certificate_information_final_grade_present_grade_not_passed(self):
        """
        test for the certificate information on dashboard.
        """
        # set same course number as we have in fixture json
        self.course_info['number'] = "3355358979513794782079645765720179322222"
        self.course_fixture = CourseFixture(
            self.course_info["org"],
            self.course_info["number"],
            self.course_info["run"],
            self.course_info["display_name"]
        )
        self.course_fixture.add_advanced_settings({
            "grading_policy": {"value": {"GRADE_CUTOFFS": {"Pass": 0.5}}}
        })
        self.course_fixture.install()

        # Load dashboard web view page for use by the tests
        self.dashboard_page = DashboardPage(self.browser)
        self.log_in_as_unique_user()
        self.dashboard_page.visit()

        # assert
        li = 'li[data-course-id="course-v1:' + self.course_info['org'] + '+' + self.course_info['number'] + '+' + self.course_info['run'] + '"]'
        self.assertIn(u'Your final grade:', self.dashboard_page.q(css=li+' p.message-copy').text[0])
        self.assertIn(u'0%', self.dashboard_page.q(css=li+' span.grade-value').text[0])
        self.assertIn(u'Grade required for a', self.dashboard_page.q(css=li+' p.message-copy').text[0])
        self.assertIn(u'50%', self.dashboard_page.q(css=li+' span.grade-value').text[1])
        self.assertFalse(self.dashboard_page.q(css=li+' a.btn').first.present)

    def test_dashboard_certificate_information_final_grade_not_present_grade_passed(self):
        """
        test for the certificate information on dashboard.
        """
        # set same course number as we have in fixture json
        self.course_info['number'] = "3355358979513794782079645765720179322223"
        self.course_fixture = CourseFixture(
            self.course_info["org"],
            self.course_info["number"],
            self.course_info["run"],
            self.course_info["display_name"]
        )
        # We need to set cert_html_view_enabled to false (default is true).
        # See: cms/djangoapps/contentstore/views/course.py#create_new_course_in_store
        self.course_fixture.add_advanced_settings({
            "grading_policy": {"value": {"GRADE_CUTOFFS": {"Pass": 0.0}}},
            "cert_html_view_enabled": {"value": "false"}
        })
        self.course_fixture.install()

        # Load dashboard web view page for use by the tests
        self.dashboard_page = DashboardPage(self.browser)
        self.log_in_as_unique_user()
        self.dashboard_page.visit()

        # assert
        li = 'li[data-course-id="course-v1:' + self.course_info['org'] + '+' + self.course_info['number'] + '+' + self.course_info['run'] + '"]'
        self.assertFalse(self.dashboard_page.q(css=li+' p.message-copy').first.present)
        self.assertFalse(self.dashboard_page.q(css=li+' span.grade-value').first.present)
        self.assertTrue(self.dashboard_page.q(css=li+' a.btn').first.present)
        self.assertIn(u'Download Certificate (PDF)', self.dashboard_page.q(css=li+' a.btn').text)

    def test_dashboard_certificate_information_final_grade_present_grade_passed(self):
        """
        test for the certificate information on dashboard.
        """
        # set same course number as we have in fixture json
        self.course_info['number'] = "3355358979513794782079645765720179322224"
        self.course_fixture = CourseFixture(
            self.course_info["org"],
            self.course_info["number"],
            self.course_info["run"],
            self.course_info["display_name"]
        )
        # We need to set cert_html_view_enabled to false (default is true).
        # See: cms/djangoapps/contentstore/views/course.py#create_new_course_in_store
        self.course_fixture.add_advanced_settings({
            "grading_policy": {"value": {"GRADE_CUTOFFS": {"Pass": 0.5}}},
            "cert_html_view_enabled": {"value": "false"}
        })
        self.course_fixture.install()

        # Load dashboard web view page for use by the tests
        self.dashboard_page = DashboardPage(self.browser)
        self.log_in_as_unique_user()
        self.dashboard_page.visit()

        # assert
        li = 'li[data-course-id="course-v1:' + self.course_info['org'] + '+' + self.course_info['number'] + '+' + self.course_info['run'] + '"]'
        self.assertIn(u'Your final grade:', self.dashboard_page.q(css=li+' p.message-copy').text[0])
        self.assertIn(u'100%', self.dashboard_page.q(css=li+' span.grade-value').text[0])
        self.assertNotIn(u'Grade required for a', self.dashboard_page.q(css=li+' p.message-copy').text[0])
        self.assertTrue(self.dashboard_page.q(css=li+' a.btn').first.present)
        self.assertIn(u'Download Certificate (PDF)', self.dashboard_page.q(css=li+' a.btn').text)

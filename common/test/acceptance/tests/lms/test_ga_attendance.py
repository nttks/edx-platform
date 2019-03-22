# -*- coding: utf-8 -*-
"""
End-to-end tests for attendance feature
"""
from bok_choy.web_app_test import WebAppTest

from ..biz.test_ga_contract_operation import BizStudentRegisterMixin
from ...fixtures.course import CourseFixture
from ...pages.biz.ga_contract import BizContractPage
from ...pages.biz.ga_navigation import BizNavPage
from ...pages.common.logout import LogoutPage
from ...pages.lms.courseware import CoursewarePage
from ...pages.lms.ga_dashboard import DashboardPage
from ...pages.lms.ga_attendance import AttendancePage
from ...pages.lms.tab_nav import TabNavPage
from ...tests.biz import GaccoBizTestMixin, PLATFORMER_USER_INFO


class AttendanceTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):
    """
    Tests that the attendance functionality works
    """

    def setUp(self):
        """
        Initializes the page object and create a test user
        """
        super(AttendanceTest, self).setUp()
        # Set window size
        self.setup_window_size_for_pc()
        # Register organization
        self.org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_user = self.new_user_info
        self.director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, self.org_info['Organization Name'], 'director', self.director)

        # page
        self.dashboard_page = DashboardPage(self.browser)
        self.tab_nav_page = TabNavPage(self.browser)

    def _setup_spoc_course(self):
        course_info = {
            'org': 'plat',
            'number': self._testMethodName,
            'run': 'biz_test_run',
            'display_name': 'Biz Test Course ' + self._testMethodName
        }
        course_fixture = CourseFixture(**course_info)
        course_fixture.install()
        self.course_key = course_fixture._course_key

        # Register a contract with platformer
        self.switch_to_user(PLATFORMER_USER_INFO)
        self.create_contract(BizContractPage(self.browser).visit(),
                             'PF', '2018/07/01', '2100/01/01',
                             contractor_organization=self.org_info['Organization Name'],
                             detail_info=[self.course_key])

        LogoutPage(self.browser).visit()

    def test_view_attendance_page(self):
        """
        Scenario: Show attendance page.
        """
        self._setup_spoc_course()
        courseware_page = CoursewarePage(self.browser, self.course_key)
        attendance_page = AttendancePage(self.browser, self.course_key)

        # Register biz user
        self.switch_to_user(self.director)

        # Register biz user
        self.switch_to_user(self.director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students().click_tab_one_register_student()
        biz_register_students_page.input_one_user_info(self.new_user).click_one_register_button().click_popup_yes()
        biz_register_students_page.wait_for_ajax()

        # Check 'playback' tab is enabled.
        self.switch_to_user(self.new_user)
        self.dashboard_page.visit()
        link_css = self.dashboard_page._link_css(self.course_key)
        self.dashboard_page.q(css=link_css).click()
        courseware_page.visit()
        self.assertIn('Attendance', self.tab_nav_page.tab_names)

        self.tab_nav_page.is_browser_on_page()
        self.tab_nav_page.go_to_tab('Attendance')

        attendance_page.visit()
        self.assertTrue(attendance_page.is_browser_on_page())
        self.assertEqual('Attendance Status : Currently Enrolled', attendance_page.title_name)
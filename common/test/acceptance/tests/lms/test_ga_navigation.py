"""
Tests the click to "TopPage" button with each page
"""
import bok_choy.browser

from bok_choy.web_app_test import WebAppTest
from ..helpers import UniqueCourseTest, load_data_str
from ..ga_helpers import GaccoTestMixin

from ...pages.common.ga_top_page import TopPage
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.course_about import CourseAboutPage
from ...pages.lms.course_info import CourseInfoPage
from ...pages.lms.courseware import CoursewarePage
from ...pages.lms.dashboard import DashboardPage
from ...pages.lms.ga_register import RegisterPage, LoginPage
from ...fixtures.course import CourseFixture


class TestAccount(WebAppTest):

    def log_in_as_unique_user(self, email=None):
        """
        Create a unique user and return the account's username and id.
        """
        username = "test_{uuid}".format(uuid=self.unique_id[0:6])
        auto_auth_page = AutoAuthPage(self.browser, username=username, email=email).visit()
        user_id = auto_auth_page.get_user_id()
        return username, user_id


class DashboardTest(TestAccount, GaccoTestMixin):

    def test_click_top_page_in_dashboard(self):
        self.log_in_as_unique_user()
        dashboard_page = DashboardPage(self.browser)
        dashboard_page.visit()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_dashboard_01')

        dashboard_page.click_top_page()
        top_page = TopPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_dashboard_02')


class LoginTest(WebAppTest, GaccoTestMixin):

    def test_click_top_page_in_login(self):
        login_page = LoginPage(self.browser)
        login_page.visit()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_login_01')

        login_page.click_top_page()
        top_page = TopPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_login_02')


class RegisterTest(WebAppTest, GaccoTestMixin):

    def test_click_top_page_in_login(self):
        login_page = RegisterPage(self.browser)
        login_page.visit()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_register_01')

        login_page.click_top_page()
        top_page = TopPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_register_02')


class AboutCourseTest(UniqueCourseTest, TestAccount, GaccoTestMixin):

    def test_click_top_page_in_about_with_not_login(self):
        CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        ).install()

        about_page = CourseAboutPage(self.browser, self.course_id)
        about_page.visit()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_about_with_not_login_01')

        about_page.click_top_page()
        top_page = TopPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_about_with_not_login_02')

    def test_click_top_page_in_about_with_login(self):

        CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        ).install()
        self.log_in_as_unique_user()

        about_page = CourseAboutPage(self.browser, self.course_id)
        about_page.visit()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_about_with_login_01')

        about_page.click_top_page()
        top_page = TopPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_about_with_login_02')


class InfoCourseTest(UniqueCourseTest, TestAccount, GaccoTestMixin):

    def test_click_top_page_in_info_with_login(self):

        self.log_in_as_unique_user()

        course = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        )
        course.install()

        info_page = CourseInfoPage(self.browser, self.course_id)
        info_page.visit()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_info_with_login_01')

        info_page.click_top_page()
        top_page = TopPage(self.browser).wait_for_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_top_page_in_info_with_login_02')

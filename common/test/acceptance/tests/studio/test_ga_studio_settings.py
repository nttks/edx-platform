"""
Acceptance tests for Studio's Setting pages
"""

import bok_choy.browser

from ..ga_helpers import GaccoTestMixin

from ...pages.studio.ga_settings import SettingsPage
from ...fixtures.course import CourseFixture

from base_studio_test import StudioCourseTest


class CourseSettingsTest(StudioCourseTest, GaccoTestMixin):

    def test_show_settings_page_for_custom_logo_not_enabled(self):

        self.course_info['org'] = 'test_org_00002'
        self.course_info['number'] = self._testMethodName
        self.course_info['run'] = 'test_run_00002'

        self.course_fixture = CourseFixture(
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run'],
            self.course_info['display_name']
        )
        self.populate_course_fixture(self.course_fixture)
        self.course_fixture.install()
        self.user = self.course_fixture.user
        self.log_in(self.user, False)

        self.settings_page = SettingsPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )
        self.settings_page.visit()
        bok_choy.browser.save_screenshot(self.browser, 'show_settings_page_for_custom_logo_not_enabled')

    def test_show_settings_page_for_custom_logo_enabled(self):

        self.course_info['org'] = 'test_org_00001'
        self.course_info['number'] = self._testMethodName
        self.course_info['run'] = 'test_run_00001'

        self.course_fixture = CourseFixture(
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run'],
            self.course_info['display_name']
        )
        self.populate_course_fixture(self.course_fixture)
        self.course_fixture.install()
        self.user = self.course_fixture.user
        self.log_in(self.user, False)

        self.settings_page = SettingsPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )
        self.settings_page.visit()
        bok_choy.browser.save_screenshot(self.browser, 'show_settings_page_for_custom_logo_enabled')

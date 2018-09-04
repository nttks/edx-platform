"""
Acceptance tests for Studio's New Icon Display Days Test
"""

from .base_studio_test import StudioCourseTest

from ...pages.studio.ga_course_rerun import CourseRerunPage
from ...pages.studio.ga_index import DashboardPage
from ...pages.studio.settings_advanced import AdvancedSettingsPage


class NewIconDisplayDaysTest(StudioCourseTest):

    def setUp(self):
        super(NewIconDisplayDaysTest, self).setUp(True)
        self.dashboard = DashboardPage(self.browser)
        self.course_rerun = CourseRerunPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )
        self.advanced_settings = AdvancedSettingsPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )

    def test_set_advanced_settings(self):
        """
        Test when update New Icon Display Days on advanced settings.
        """
        self.advanced_settings.visit()

        self.advanced_settings.set(
            'New Icon Display Days',
            '10'
        )

        self.advanced_settings.refresh_and_wait_for_load()

        self.assertEqual(
            '10',
            self.advanced_settings.get('New Icon Display Days')
        )

    def test_rerun_course(self):
        """
        Test when rerun new course.
        """
        self.advanced_settings.visit()

        self.advanced_settings.set(
            'New Icon Display Days',
            '10'
        )

        self.dashboard.visit()

        self.dashboard.create_rerun(self.course_info['display_name'])
        self.course_rerun.wait_for_page()
        self.course_rerun.course_name = 'TEST COURSE rerun'
        self.course_rerun.course_run = 'new_rerun_run'
        self.course_rerun.create_rerun()

        self.advanced_settings = AdvancedSettingsPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            'new_rerun_run'
        )
        self.advanced_settings.visit()

        self.assertEqual(
            '"TEST COURSE rerun"',
            self.advanced_settings.get('Course Display Name')
        )

        self.assertEqual(
            '10',
            self.advanced_settings.get('New Icon Display Days')
        )

    def test_set_advanced_settings_error(self):
        """
        Test when error New Icon Display Days on advanced settings.
        """
        self.advanced_settings.visit()

        self.advanced_settings.set(
            'New Icon Display Days',
            '"test"'
        )
        self.advanced_settings.wait_for_modal_load()
        self.advanced_settings.save()

        self.assertTrue(self.advanced_settings.is_validation_modal_present())
        self.assertEqual(
            [u'New Icon Display Days'],
            self.advanced_settings.get_error_item_names()
        )
        self.assertEqual(
            [u'invalid literal for int() with base 10: \'test\''],
            self.advanced_settings.get_error_item_messages()
        )

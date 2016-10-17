"""
Acceptance tests for Studio's Course Name(Course display name) Length
"""

from .base_studio_test import StudioCourseTest

from ...pages.studio.ga_course_rerun import CourseRerunPage
from ...pages.studio.ga_index import DashboardPage
from ...pages.studio.settings_advanced import AdvancedSettingsPage


class CourseNameLengthTest(StudioCourseTest):

    def setUp(self):
        super(CourseNameLengthTest, self).setUp(True)
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

    def test_create_course(self):
        """
        Test when create new course.
        """
        self.dashboard.visit()

        new_number = self.unique_id

        self.dashboard.click_new_course_button()
        self.dashboard.fill_new_course_form(
            'TEST COURSE 123456789 123456789 123456789 123456789 123456789 123456789',
            self.course_info['org'],
            new_number,
            self.course_info['run']
        )
        self.assertTrue(self.dashboard.is_new_course_form_valid())
        self.dashboard.submit_new_course_form()

        self.assertFalse(self.dashboard.is_new_course_form_valid())
        self.assertEqual(
            u'Course name, please be up to 64 characters.',
            self.dashboard.course_creation_error_message
        )

    def test_rerun_course(self):
        """
        Test when rerun new course.
        """
        self.dashboard.visit()

        self.dashboard.create_rerun(self.course_info['display_name'])
        self.course_rerun.wait_for_page()
        self.course_rerun.course_name = 'TEST COURSE 123456789 123456789 123456789 123456789 123456789 123456789'
        self.course_rerun.course_run = 'new_rerun_run'
        self.course_rerun.create_rerun()

        self.assertEqual(
            u'Course name, please be up to 64 characters.',
            self.course_rerun.course_rerun_error_message
        )

    def test_set_advanced_settings(self):
        """
        Test when update course display name on advanced settings.
        """
        self.advanced_settings.visit()

        self.advanced_settings.set(
            'Course Display Name',
            '"TEST COURSE 123456789 123456789 123456789 123456789 123456789 123456789"'
        )
        self.advanced_settings.wait_for_modal_load()
        self.advanced_settings.save()

        self.assertTrue(self.advanced_settings.is_validation_modal_present())
        self.assertEqual(
            [u'Course Display Name'],
            self.advanced_settings.get_error_item_names()
        )
        self.assertEqual(
            [u'Course display name, please be up to 64 characters.'],
            self.advanced_settings.get_error_item_messages()
        )

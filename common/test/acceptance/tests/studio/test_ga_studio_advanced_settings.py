"""
Acceptance tests for Studio's page of advanced settings.
"""

from .base_studio_test import StudioCourseTest

from ...pages.studio.ga_index import DashboardPage
from ...pages.studio.settings_advanced import AdvancedSettingsPage


class DefaultValueTest(StudioCourseTest):

    def setUp(self):
        super(DefaultValueTest, self).setUp(True)
        self.advanced_settings = AdvancedSettingsPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )

    def test_certificates_display_behavior(self):
        """
        Test value of certificates_display_behavior on advanced settings when create course.
        """
        self.advanced_settings.visit()

        self.assertEqual(
            '"early_with_info"',
            self.advanced_settings.get('Certificates Display Behavior')
        )

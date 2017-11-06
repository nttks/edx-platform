"""
Acceptance tests for Studio's Settings Details pages
"""

from flaky import flaky

from .base_studio_test import StudioCourseTest
from .test_studio_settings_details import StudioSettingsDetailsTest

from ...pages.studio.ga_settings import SettingsPage


@flaky
class SettingsDeadlineTerminateTest(StudioCourseTest):

    def setUp(self):
        super(SettingsDeadlineTerminateTest, self).setUp(True)
        self.settings_detail = SettingsPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )

    def test_course_new_value_and_update_value(self):
        self.settings_detail.visit()
        self.assertFalse(self.settings_detail.has_error)

        # input value
        self.settings_detail.deadline_start_date.fill('01/01/2020')
        self.settings_detail.deadline_start_time.fill('10:00')
        self.settings_detail.terminate_start_date.fill('01/01/2025')
        self.settings_detail.terminate_start_time.fill('20:00')
        self.settings_detail.course_category.fill('free,secret')
        self.settings_detail.is_f2f_course.click()
        self.settings_detail.is_f2f_course_sell.click()
        self.settings_detail.course_canonical_name.fill('Secret Course')
        self.settings_detail.course_contents_provider.fill('Secret College')
        self.settings_detail.teacher_name.fill('Secret T')
        self.settings_detail.course_span.fill('10S')
        self.assertFalse(self.settings_detail.has_error)

        self.settings_detail.save_changes()
        self.assertEqual(
            'Your changes have been saved.',
            self.settings_detail.alert_confirmation_title.text
        )
        self.assertEquals('01/01/2020', self.settings_detail.deadline_start_date.attrs('value')[0])
        self.assertEquals('10:00', self.settings_detail.deadline_start_time.attrs('value')[0])
        self.assertEquals('01/01/2025', self.settings_detail.terminate_start_date.attrs('value')[0])
        self.assertEquals('20:00', self.settings_detail.terminate_start_time.attrs('value')[0])
        self.assertEquals('free,secret', self.settings_detail.course_category.attrs('value')[0])
        self.assertTrue(self.settings_detail.is_f2f_course_checked)
        self.assertTrue(self.settings_detail.is_f2f_course_sell_checked)
        self.assertEquals('Secret Course', self.settings_detail.course_canonical_name.attrs('value')[0])
        self.assertEquals('Secret College', self.settings_detail.course_contents_provider.attrs('value')[0])
        self.assertEquals('Secret T', self.settings_detail.teacher_name.attrs('value')[0])
        self.assertEquals('10S', self.settings_detail.course_span.attrs('value')[0])

        # refresh page
        self.settings_detail.refresh_page()
        self.assertFalse(self.settings_detail.has_error)

        self.assertEquals('01/01/2020', self.settings_detail.deadline_start_date.attrs('value')[0])
        self.assertEquals('10:00', self.settings_detail.deadline_start_time.attrs('value')[0])
        self.assertEquals('01/01/2025', self.settings_detail.terminate_start_date.attrs('value')[0])
        self.assertEquals('20:00', self.settings_detail.terminate_start_time.attrs('value')[0])
        self.assertEquals('free,secret', self.settings_detail.course_category.attrs('value')[0])
        self.assertTrue(self.settings_detail.is_f2f_course_checked)
        self.assertTrue(self.settings_detail.is_f2f_course_sell_checked)
        self.assertEquals('Secret Course', self.settings_detail.course_canonical_name.attrs('value')[0])
        self.assertEquals('Secret College', self.settings_detail.course_contents_provider.attrs('value')[0])
        self.assertEquals('Secret T', self.settings_detail.teacher_name.attrs('value')[0])
        self.assertEquals('10S', self.settings_detail.course_span.attrs('value')[0])

        # update value
        self.settings_detail.deadline_start_date.fill('02/02/2020')
        self.settings_detail.deadline_start_time.fill('20:00')
        self.settings_detail.terminate_start_date.fill('03/03/2025')
        self.settings_detail.terminate_start_time.fill('10:00')
        self.settings_detail.course_category.fill('free')
        self.settings_detail.is_f2f_course.click()
        self.settings_detail.is_f2f_course_sell.click()
        self.settings_detail.course_canonical_name.fill('Free Course')
        self.settings_detail.course_contents_provider.fill('Free College')
        self.settings_detail.teacher_name.fill('Free T')
        self.settings_detail.course_span.fill('7M')
        self.assertFalse(self.settings_detail.has_error)

        self.settings_detail.save_changes()
        self.assertEqual(
            'Your changes have been saved.',
            self.settings_detail.alert_confirmation_title.text
        )
        self.assertEquals('02/02/2020', self.settings_detail.deadline_start_date.attrs('value')[0])
        self.assertEquals('20:00', self.settings_detail.deadline_start_time.attrs('value')[0])
        self.assertEquals('03/03/2025', self.settings_detail.terminate_start_date.attrs('value')[0])
        self.assertEquals('10:00', self.settings_detail.terminate_start_time.attrs('value')[0])
        self.assertEquals('free', self.settings_detail.course_category.attrs('value')[0])
        self.assertFalse(self.settings_detail.is_f2f_course_checked)
        self.assertFalse(self.settings_detail.is_f2f_course_checked)
        self.assertEquals('Free Course', self.settings_detail.course_canonical_name.attrs('value')[0])
        self.assertEquals('Free College', self.settings_detail.course_contents_provider.attrs('value')[0])
        self.assertEquals('Free T', self.settings_detail.teacher_name.attrs('value')[0])
        self.assertEquals('7M', self.settings_detail.course_span.attrs('value')[0])

        # refresh page
        self.settings_detail.refresh_page()
        self.assertFalse(self.settings_detail.has_error)

        self.assertEquals('02/02/2020', self.settings_detail.deadline_start_date.attrs('value')[0])
        self.assertEquals('20:00', self.settings_detail.deadline_start_time.attrs('value')[0])
        self.assertEquals('03/03/2025', self.settings_detail.terminate_start_date.attrs('value')[0])
        self.assertEquals('10:00', self.settings_detail.terminate_start_time.attrs('value')[0])
        self.assertEquals('free', self.settings_detail.course_category.attrs('value')[0])
        self.assertFalse(self.settings_detail.is_f2f_course_checked)
        self.assertFalse(self.settings_detail.is_f2f_course_sell_checked)
        self.assertEquals('Free Course', self.settings_detail.course_canonical_name.attrs('value')[0])
        self.assertEquals('Free College', self.settings_detail.course_contents_provider.attrs('value')[0])
        self.assertEquals('Free T', self.settings_detail.teacher_name.attrs('value')[0])
        self.assertEquals('7M', self.settings_detail.course_span.attrs('value')[0])

    def test_course_new_value_only_require(self):
        self.settings_detail.visit()
        self.assertFalse(self.settings_detail.has_error)

        # input value
        self.settings_detail.course_canonical_name.fill('Course')
        self.settings_detail.teacher_name.fill('Teacher')
        self.assertFalse(self.settings_detail.has_error)

        self.settings_detail.save_changes()
        self.assertEqual(
            'Your changes have been saved.',
            self.settings_detail.alert_confirmation_title.text
        )
        self.assertEquals('', self.settings_detail.deadline_start_date.attrs('value')[0])
        self.assertEquals('', self.settings_detail.deadline_start_time.attrs('value')[0])
        self.assertEquals('', self.settings_detail.terminate_start_date.attrs('value')[0])
        self.assertEquals('', self.settings_detail.terminate_start_time.attrs('value')[0])
        self.assertEquals('', self.settings_detail.course_category.attrs('value')[0])
        self.assertFalse(self.settings_detail.is_f2f_course_checked)
        self.assertFalse(self.settings_detail.is_f2f_course_sell_checked)
        self.assertEquals('Course', self.settings_detail.course_canonical_name.attrs('value')[0])
        self.assertEquals('', self.settings_detail.course_contents_provider.attrs('value')[0])
        self.assertEquals('Teacher', self.settings_detail.teacher_name.attrs('value')[0])
        self.assertEquals('', self.settings_detail.course_span.attrs('value')[0])

        # refresh page
        self.settings_detail.refresh_page()
        self.assertFalse(self.settings_detail.has_error)

        self.assertEquals('', self.settings_detail.deadline_start_date.attrs('value')[0])
        self.assertEquals('', self.settings_detail.deadline_start_time.attrs('value')[0])
        self.assertEquals('', self.settings_detail.terminate_start_date.attrs('value')[0])
        self.assertEquals('', self.settings_detail.terminate_start_time.attrs('value')[0])
        self.assertEquals('', self.settings_detail.course_category.attrs('value')[0])
        self.assertFalse(self.settings_detail.is_f2f_course_checked)
        self.assertFalse(self.settings_detail.is_f2f_course_sell_checked)
        self.assertEquals('Course', self.settings_detail.course_canonical_name.attrs('value')[0])
        self.assertEquals('', self.settings_detail.course_contents_provider.attrs('value')[0])
        self.assertEquals('Teacher', self.settings_detail.teacher_name.attrs('value')[0])
        self.assertEquals('', self.settings_detail.course_span.attrs('value')[0])

    def test_course_new_value_only_require_empty_course_canonical_name(self):
        self.settings_detail.visit()
        self.assertFalse(self.settings_detail.has_error)

        # input value
        self.settings_detail.course_canonical_name.fill('')
        self.assertTrue(self.settings_detail.has_error)

    def test_course_new_value_only_require_empty_teacher_name(self):
        self.settings_detail.visit()
        self.assertFalse(self.settings_detail.has_error)

        # input value
        self.settings_detail.teacher_name.fill('')
        self.assertTrue(self.settings_detail.has_error)


@flaky
class SettingsNotStaffTest(StudioCourseTest):
    """
    Tests for settings page by not staff user.
    """

    def setUp(self):
        super(SettingsNotStaffTest, self).setUp()
        self.settings_detail = SettingsPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )

    def test_course_category_not_displayed(self):
        self.settings_detail.visit()
        # First, verify canonical name has displayed, since canonical name is rendered after course category.
        self.assertEqual(
            self.course_info['display_name'],
            self.settings_detail.course_canonical_name.attrs('value')[0]
        )
        # Second, verify course category has not displayed.
        self.assertFalse(self.settings_detail.is_course_category_displayed)


class SettingsPlaybackRateTest(StudioSettingsDetailsTest):

    def setUp(self):
        super(SettingsPlaybackRateTest, self).setUp(True)
        self.settings_detail = SettingsPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )

    def _add_playback_rate_settings(self):
        self.course_fixture.add_advanced_settings({'advanced_modules': {'value': ['jwplayerxblock']}})
        self.course_fixture._add_advanced_settings()
        self.browser.refresh()

    def test_invisible_playback_rate(self):
        self.settings_detail.visit()
        self.assertFalse(self.settings_detail.is_playback_rate_1_only_displayed)

    def test_visible_playback_rate_and_checked(self):
        self._add_playback_rate_settings()

        self.settings_detail.visit()
        self.assertTrue(self.settings_detail.is_playback_rate_1_only_displayed)

        self.settings_detail.playback_rate_1_only.click()
        self.assertTrue(self.settings_detail.playback_rate_1_only_checked)
        self.settings_detail.save_changes()
        self.assertEqual(
            'Your changes have been saved.',
            self.settings_detail.alert_confirmation_title.text
        )

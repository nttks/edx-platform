import unittest
from django.conf import settings
from django.test import TestCase
from opaque_keys.edx.locations import SlashSeparatedCourseKey

from openedx.core.djangoapps.course_global.models import CourseGlobalSetting


@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class CourseGlobalSettingTest(TestCase):
    """
    Tests for the CourseGlobalSetting model.
    """

    def setUp(self):
        pass

    def _create_global_setting(self, course_id, global_enabled=True):
        """
        Create a new couse global setting model.
        """
        return CourseGlobalSetting.objects.get_or_create(
            course_id=course_id,
            global_enabled=global_enabled
        )

    def test_all_global_courses(self):
        """
        Tests all of global-course.
        """
        course_id_1 = SlashSeparatedCourseKey('Test', 'TestCourse', 'TestCourseRun1')
        course_id_2 = SlashSeparatedCourseKey('Test', 'TestCourse', 'TestCourseRun2')
        course_id_3 = SlashSeparatedCourseKey('Test', 'TestCourse', 'TestCourseRun3')
        # create test models
        self._create_global_setting(course_id_1)
        self._create_global_setting(course_id_2)
        self._create_global_setting(course_id_3, False)

        course_global_ids = CourseGlobalSetting.all_course_id()

        self.assertEquals(2, len(course_global_ids))
        self.assertTrue(course_id_1 in course_global_ids)
        self.assertTrue(course_id_2 in course_global_ids)
        self.assertFalse(course_id_3 in course_global_ids)

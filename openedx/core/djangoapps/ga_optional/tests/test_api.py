
from django.test import TestCase

from opaque_keys.edx.keys import CourseKey

from ..api import is_available
from ..models import CourseOptionalConfiguration


class ApiTest(TestCase):

    def setUp(self):
        super(ApiTest, self).setUp()

        self.test_key_1 = 'test-key-1'
        self.test_course_key_1 = CourseKey.from_string('course-v1:test_org+test_course_1+test_run')
        self.test_key_2 = 'test-key-2'
        self.test_course_key_2 = CourseKey.from_string('course-v1:test_org+test_course_2+test_run')

    def _save_configuration(self, key, course_key, enabled=True):
        CourseOptionalConfiguration(key=key, course_key=course_key, enabled=enabled).save()

    def test_is_available(self):
        # no configuration
        self.assertFalse(is_available(self.test_key_1))
        self.assertFalse(is_available(self.test_key_2))
        self.assertFalse(is_available(self.test_key_1, self.test_course_key_1))
        self.assertFalse(is_available(self.test_key_1, self.test_course_key_2))
        self.assertFalse(is_available(self.test_key_2, self.test_course_key_1))
        self.assertFalse(is_available(self.test_key_2, self.test_course_key_2))

        # Set configuration
        ## - Enabled key1 and course_key1
        ## - Disabled key1 and course_key2
        ## - Enabled key2 and course_key2
        ## - Disabled key2 and course_key1
        self._save_configuration(self.test_key_1, self.test_course_key_1)
        self._save_configuration(self.test_key_1, self.test_course_key_2, enabled=False)
        self._save_configuration(self.test_key_2, self.test_course_key_2)
        self._save_configuration(self.test_key_2, self.test_course_key_1, enabled=False)

        self.assertTrue(is_available(self.test_key_1, self.test_course_key_1))
        self.assertTrue(is_available(self.test_key_2, self.test_course_key_2))

        ## different pair
        self.assertFalse(is_available(self.test_key_1))
        self.assertFalse(is_available(self.test_key_2))
        self.assertFalse(is_available(self.test_key_1, self.test_course_key_2))
        self.assertFalse(is_available(self.test_key_2, self.test_course_key_1))

        # Change configuration
        ## - Disabled key1 and course_key1
        ## - Enabled key1 and course_key2
        ## - Disabled key2 and course_key2
        ## - Enabled key2 and course_key1
        self._save_configuration(self.test_key_1, self.test_course_key_1, enabled=False)
        self._save_configuration(self.test_key_1, self.test_course_key_2)
        self._save_configuration(self.test_key_2, self.test_course_key_2, enabled=False)
        self._save_configuration(self.test_key_2, self.test_course_key_1)

        self.assertTrue(is_available(self.test_key_1, self.test_course_key_2))
        self.assertTrue(is_available(self.test_key_2, self.test_course_key_1))

        ## different pair
        self.assertFalse(is_available(self.test_key_1, self.test_course_key_1))
        self.assertFalse(is_available(self.test_key_2, self.test_course_key_2))

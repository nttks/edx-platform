"""
Tests for course utilities
"""
from biz.djangoapps.util import course_utils
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


class CourseUtilsTest(ModuleStoreTestCase):
    """Test for course utilities"""

    def setUp(self):
        super(CourseUtilsTest, self).setUp()

    def test_get_course_with_course_key(self):
        course = CourseFactory.create()
        result = course_utils.get_course(course.id)
        self.assertEqual(course, result)

    def test_get_course_with_unicode_course_id(self):
        course = CourseFactory.create()
        result = course_utils.get_course(unicode(course.id))
        self.assertEqual(course, result)

    def test_get_course_with_invalid_course_id(self):
        invalid_course_id = 'invalid_course_id'
        result = course_utils.get_course(invalid_course_id)
        self.assertIsNone(result)

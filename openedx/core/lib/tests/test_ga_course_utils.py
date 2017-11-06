"""
Tests for functionality in openedx/core/lib/ga_course_utils.py.
"""
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from ..ga_course_utils import is_using_jwplayer_course


class GaCourseUtilsTestCase(ModuleStoreTestCase):

    def setUp(self):
        super(GaCourseUtilsTestCase, self).setUp()
        self.course = CourseFactory.create()

    def test_using_jwplayer_course(self):
        self.course.advanced_modules = ["jwplayerxblock"]
        self.assertTrue(is_using_jwplayer_course(self.course))

    def test_not_using_jwplayer_course(self):
        self.assertFalse(is_using_jwplayer_course(self.course))

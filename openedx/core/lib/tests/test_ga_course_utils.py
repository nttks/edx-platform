"""
Tests for functionality in openedx/core/lib/ga_course_utils.py.
"""
from datetime import timedelta

from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from ..ga_course_utils import is_using_jwplayer_course, sort_by_start_date
from biz.djangoapps.util import datetime_utils


class GaCourseUtilsTestCase(ModuleStoreTestCase):

    def setUp(self):
        super(GaCourseUtilsTestCase, self).setUp()
        self.course = CourseFactory.create()

    def test_using_jwplayer_course(self):
        self.course.advanced_modules = ["jwplayerxblock"]
        self.assertTrue(is_using_jwplayer_course(self.course))

    def test_not_using_jwplayer_course(self):
        self.assertFalse(is_using_jwplayer_course(self.course))

    def test_sort_by_start_date_desc(self):
        course1 = CourseFactory.create(start=None)
        course2 = CourseFactory.create(start=datetime_utils.timezone_now() - timedelta(days=1))
        course3 = CourseFactory.create(start=datetime_utils.timezone_now() + timedelta(days=1))
        course4 = CourseFactory.create(start=datetime_utils.timezone_now() - timedelta(days=2))
        course5 = CourseFactory.create(start=datetime_utils.timezone_now() + timedelta(days=2))

        courses = [course1, course2, course3, course4, course5]
        sorted_courses_desc = sort_by_start_date(courses)

        self.assertEquals(sorted_courses_desc[0], course5)
        self.assertEquals(sorted_courses_desc[1], course3)
        self.assertEquals(sorted_courses_desc[2], course2)
        self.assertEquals(sorted_courses_desc[3], course4)
        self.assertEquals(sorted_courses_desc[4], course1)

    def test_sort_by_start_date_asc(self):
        course1 = CourseFactory.create(start=None)
        course2 = CourseFactory.create(start=datetime_utils.timezone_now() - timedelta(days=1))
        course3 = CourseFactory.create(start=datetime_utils.timezone_now() + timedelta(days=1))
        course4 = CourseFactory.create(start=datetime_utils.timezone_now() - timedelta(days=2))
        course5 = CourseFactory.create(start=datetime_utils.timezone_now() + timedelta(days=2))

        courses = [course1, course2, course3, course4, course5]
        sorted_courses_desc = sort_by_start_date(courses, desc=False)

        self.assertEquals(sorted_courses_desc[0], course1)
        self.assertEquals(sorted_courses_desc[1], course4)
        self.assertEquals(sorted_courses_desc[2], course2)
        self.assertEquals(sorted_courses_desc[3], course3)
        self.assertEquals(sorted_courses_desc[4], course5)

"""
Tests for ga_course_overviews app.
"""
from datetime import datetime, timedelta

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, check_mongo_calls, check_mongo_calls_range

from .models import CourseOverviewExtra


class CourseOverviewExtraTest(ModuleStoreTestCase):

    def setUp(self):
        super(CourseOverviewExtraTest, self).setUp()

        self.course = CourseFactory.create()

    def test_extra(self):
        # Tests default value
        overview = CourseOverview.get_from_id(self.course.id)
        self.assertFalse(overview.extra.has_terminated)
        self.assertFalse(overview.extra.is_f2f_course)
        self.assertFalse(overview.extra.is_f2f_course_sell)
        self.assertFalse(overview.extra.self_paced)
        self.assertIsNone(overview.extra.individual_end_days)
        self.assertIsNone(overview.extra.individual_end_hours)
        self.assertIsNone(overview.extra.individual_end_minutes)

        self.course.terminate_start = datetime.now() - timedelta(seconds=1)
        self.course.is_f2f_course = True
        self.course.is_f2f_course_sell = True
        self.course.self_paced = True
        self.course.individual_end_days = 1
        self.course.individual_end_hours = 2
        self.course.individual_end_minutes = 3
        # This fires a course_published signal, which should be caught in signals.py, which should in turn
        # delete the corresponding CourseOverviewExtra from the cache.
        self.update_course(self.course, self.user.id)

        # Tests updated value
        overview = CourseOverview.get_from_id(self.course.id)
        self.assertTrue(overview.extra.has_terminated)
        self.assertTrue(overview.extra.is_f2f_course)
        self.assertTrue(overview.extra.is_f2f_course_sell)
        self.assertTrue(overview.extra.self_paced)
        self.assertEqual(1, overview.extra.individual_end_days)
        self.assertEqual(2, overview.extra.individual_end_hours)
        self.assertEqual(3, overview.extra.individual_end_minutes)

    def test_extra_stale_cache(self):
        overview = CourseOverview.get_from_id(self.course.id)
        self.assertFalse(overview.extra.is_f2f_course)

        # Update value but does not reflect to cache
        CourseOverviewExtra.objects.filter(course_overview=overview).update(is_f2f_course=True)
        self.assertFalse(overview.extra.is_f2f_course)

        # Value is updated if reacquire the instance
        overview = CourseOverview.get_from_id(self.course.id)
        self.assertTrue(overview.extra.is_f2f_course)

    def test_extra_invalid_version(self):
        overview = CourseOverview.get_from_id(self.course.id)
        self.assertFalse(overview.extra.is_f2f_course)

        # Update extra directly
        CourseOverviewExtra.objects.filter(course_overview=overview).update(is_f2f_course=True)
        overview = CourseOverview.get_from_id(self.course.id)
        self.assertTrue(overview.extra.is_f2f_course)

        # if version is old, then reacquire data from modulestore
        overview.version = 0
        overview.save()
        overview = CourseOverview.get_from_id(self.course.id)
        self.assertFalse(overview.extra.is_f2f_course)

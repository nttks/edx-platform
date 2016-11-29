"""
Tests for ga_self_paced api.
"""
import datetime
import ddt
from mock import patch

from django.utils import timezone

from student.tests.factories import CourseEnrollmentFactory, UserFactory
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from .. import api


@ddt.ddt
class TestApi(ModuleStoreTestCase):

    def setUp(self):
        super(TestApi, self).setUp()
        self.course = CourseFactory.create()
        self.user = UserFactory.create()

    def _update_course(self, start, self_paced, days, hours, minutes):
        self.course.start = start
        self.course.self_paced = self_paced
        self.course.individual_end_days = days
        self.course.individual_end_hours = hours
        self.course.individual_end_minutes = minutes

        self.update_course(self.course, self.user.id)

    @ddt.data(
        (None, None, None),
        (0, 1, 2),
        (2, 0, 1),
        (1, 2, 0),
    )
    @ddt.unpack
    def test_get_individual_date(self, days, hours, minutes):
        now = timezone.now()

        timeinfo = {}
        if days:
            timeinfo['days'] = days
        if hours:
            timeinfo['hours'] = hours
        if minutes:
            timeinfo['minutes'] = minutes

        expected = now + datetime.timedelta(days=days or 0, hours=hours or 0, minutes=minutes or 0)
        self.assertEqual(expected, api.get_individual_date(now, timeinfo))

    def test_get_individual_date_none(self):
        self.assertIsNone(api.get_individual_date(None, {}))

    @ddt.data(
        ('course',     1, 0),
        ('enrollment', 0, 1),
    )
    @ddt.unpack
    def test_get_base_date(self, expected, start_delay, created_delay):
        now = timezone.now()
        start = (now + datetime.timedelta(seconds=start_delay)).replace(microsecond=0)
        created = now + datetime.timedelta(seconds=created_delay)

        self.course.start = start
        self.update_course(self.course, self.user.id)

        enrollment = CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)
        enrollment.created = created
        enrollment.save()

        if expected == 'course':
            self.assertEqual(start, api.get_base_date(enrollment))
        else:
            self.assertEqual(created, api.get_base_date(enrollment))

    def test_get_base_date_none(self):
        self.assertIsNone(api.get_base_date(None))

    def test_get_course_end_date(self):
        # Fixed start date to the future in this test
        course_start_date = timezone.now().replace(microsecond=0) + datetime.timedelta(days=1)
        days, hours, minutes = 1, 2, 3

        self._update_course(course_start_date, True, days, hours, minutes)

        enrollment = CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)
        end_date = api.get_course_end_date(enrollment)
        expected_date = course_start_date + datetime.timedelta(days=days, hours=hours, minutes=minutes)

        self.assertEqual(expected_date, end_date)

    @ddt.data(
        (False, 1, 2, 3),
        (True, 0, 0, 0),
    )
    @ddt.unpack
    def test_get_course_end_date_none_date(self, self_paced, days, hours, minutes):
        # Fixed start date to the future in this test
        course_start_date = timezone.now().replace(microsecond=0) + datetime.timedelta(days=1)

        self._update_course(course_start_date, self_paced, days, hours, minutes)

        enrollment = CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)

        self.assertIsNone(api.get_course_end_date(enrollment))

    @ddt.data(
        # boundary
        (True,   61, True,  0, 0, 1),
        (False,  60, True,  0, 0, 1),
        (False,  59, True,  0, 0, 1),
        # no end_date
        (False,  0,  False, 1, 2, 3),
        (False,  0,  True,  0, 0, 0),
    )
    @ddt.unpack
    def test_is_course_closed(self, expected, delay, self_paced, days, hours, minutes):
        course_start_date = timezone.now()

        self._update_course(course_start_date, self_paced, days, hours, minutes)

        enrollment = CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)

        with patch('django.utils.timezone.now', return_value=course_start_date + datetime.timedelta(seconds=delay)):
            if expected:
                self.assertTrue(api.is_course_closed(enrollment))
            else:
                self.assertFalse(api.is_course_closed(enrollment))

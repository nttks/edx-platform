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
        ('course', 1, 0),
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

    @ddt.data('audit', 'no-id-professional')
    def test_get_base_date_paid_course(self, mode):
        self.course.start = timezone.now()
        self.update_course(self.course, self.user.id)

        if mode == 'no-id-professional':
            # emulate payment flow
            enrollment = CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id, mode='audit', is_active=False)
            enrollment.is_active = True
            enrollment.mode = mode
            enrollment.save()
        else:
            enrollment = CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id, mode=mode)

        # Get enrollment date (enrollment data was created after course update)
        base_date = api.get_base_date(enrollment)

        if mode == 'no-id-professional':
            self.assertNotEqual(base_date, enrollment.created)
            self.assertEqual(base_date, enrollment.history.filter(is_active=True).order_by('-history_date')[0].history_date)
        else:
            self.assertEqual(base_date, enrollment.created)

    def test_get_base_date_none(self):
        self.assertIsNone(api.get_base_date(None))

    @ddt.data(
        (1, 2, 3),
        (1, None, None),
        (None, 1, None),
        (None, None, 1),
    )
    @ddt.unpack
    def test_get_course_end_date(self, days, hours, minutes):
        # Fixed start date to the future in this test
        course_start_date = timezone.now().replace(microsecond=0) + datetime.timedelta(days=1)

        self._update_course(course_start_date, True, days, hours, minutes)

        enrollment = CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)
        end_date = api.get_course_end_date(enrollment)
        expected_date = course_start_date + datetime.timedelta(days=days or 0, hours=hours or 0, minutes=minutes or 0)

        self.assertEqual(expected_date, end_date)

    @ddt.data(
        (False, 1, 2, 3),
        (True, None, None, None),
    )
    @ddt.unpack
    def test_get_course_end_date_none_date(self, self_paced, days, hours, minutes):
        # Fixed start date to the future in this test
        course_start_date = timezone.now().replace(microsecond=0) + datetime.timedelta(days=1)

        self._update_course(course_start_date, self_paced, days, hours, minutes)

        enrollment = CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)

        self.assertIsNone(api.get_course_end_date(enrollment))

    def test_get_course_end_date_if_enrollment_is_none(self):
        self.assertIsNone(api.get_course_end_date(None))

    @ddt.data(
        # boundary
        (True, 61, True, 0, 0, 1),
        (False, 60, True, 0, 0, 1),
        (False, 59, True, 0, 0, 1),
        # 0 time-width
        (True, 1, True, 0, None, None),
        # no end_date
        (False, 1, False, 0, 0, 0),
        (False, 1, True, None, None, None),
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

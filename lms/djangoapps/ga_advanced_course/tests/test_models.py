
from datetime import timedelta
import unittest

from django.test.utils import override_settings
from django.utils import timezone

from opaque_keys.edx.locator import CourseLocator

from ga_advanced_course.models import AdvancedCourse
from ga_advanced_course.tests.factories import AdvancedF2FCourseFactory, AdvancedCourseTicketFactory


class AdvancedF2FCourseTest(unittest.TestCase):

    def setUp(self):
        self.course_key = CourseLocator('org', self._testMethodName, 'run')
        _another_key = CourseLocator('org', self._testMethodName + 'X', 'run')
        self.advanced_courses = [
            AdvancedF2FCourseFactory.create(course_id=self.course_key),
            AdvancedF2FCourseFactory.create(course_id=self.course_key, is_active=False),
            AdvancedF2FCourseFactory.create(course_id=self.course_key),
            AdvancedF2FCourseFactory.create(course_id=_another_key),
        ]

    def test_get_advanced_course(self):
        expected_1 = self.advanced_courses[0]
        self.assertEqual(expected_1, AdvancedCourse.get_advanced_course(expected_1.id))

        # Not active
        with self.assertRaises(AdvancedCourse.DoesNotExist):
            AdvancedCourse.get_advanced_course(self.advanced_courses[1].id)

        # Not exist
        with self.assertRaises(AdvancedCourse.DoesNotExist):
            AdvancedCourse.get_advanced_course(999)

    def test_get_advanced_courses_by_course_key(self):
        self.assertListEqual(
            [self.advanced_courses[0], self.advanced_courses[2]],
            list(AdvancedCourse.get_advanced_courses_by_course_key(self.course_key))
        )


class AdvancedCourseTicketTest(unittest.TestCase):

    @override_settings(PAYMENT_TAX=8)
    def test_tax(self):
        advanced_course = AdvancedF2FCourseFactory.create()
        self.assertEquals(0, AdvancedCourseTicketFactory.create(advanced_course=advanced_course, price=12).tax)
        self.assertEquals(1, AdvancedCourseTicketFactory.create(advanced_course=advanced_course, price=13).tax)

    def test_price_with_tax(self):
        advanced_course = AdvancedF2FCourseFactory.create()

        self.assertEquals(
            12,
            AdvancedCourseTicketFactory.create(advanced_course=advanced_course, price=12).price_with_tax
        )
        self.assertEquals(
            14,
            AdvancedCourseTicketFactory.create(advanced_course=advanced_course, price=13).price_with_tax
        )

    def test_is_end_of_sale(self):
        advanced_course = AdvancedF2FCourseFactory.create()

        # End
        self.assertTrue(
            AdvancedCourseTicketFactory.create(
                advanced_course=advanced_course,
                sell_by_date=timezone.now() - timedelta(seconds=1)
            ).is_end_of_sale()
        )

        # Not End
        self.assertFalse(
            AdvancedCourseTicketFactory.create(
                advanced_course=advanced_course,
                sell_by_date=timezone.now() + timedelta(seconds=1)
            ).is_end_of_sale()
        )

"""
Tests for ga-self-paced course overrides.
"""
from datetime import datetime, timedelta
from dateutil.tz import tzutc

from django.test.utils import override_settings

from courseware.field_overrides import OverrideFieldData
from courseware.tests.test_field_overrides import inject_field_overrides
from openedx.core.djangoapps.self_paced.models import SelfPacedConfiguration
from student.roles import CourseStaffRole
from student.tests.factories import CourseEnrollmentFactory, UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory


@override_settings(
    FIELD_OVERRIDE_PROVIDERS=('courseware.ga_self_paced_overrides.SelfPacedDateOverrideProvider',)
)
class SelfPacedDateOverrideTest(ModuleStoreTestCase):

    def setUp(self):
        SelfPacedConfiguration(enabled=True).save()
        super(SelfPacedDateOverrideTest, self).setUp()
        self.start = datetime(2016, 1, 1, 0, 0, 0).replace(tzinfo=tzutc())
        self.due_date = datetime(2016, 2, 1, 0, 0, 0).replace(tzinfo=tzutc())
        self.individual_start_days = 1
        self.individual_start_hours = 2
        self.individual_start_minutes = 3
        self.individual_due_days = 4
        self.individual_due_hours = 5
        self.individual_due_minutes = 6

    def tearDown(self):
        super(SelfPacedDateOverrideTest, self).tearDown()
        OverrideFieldData.provider_classes = None

    def setup_course(
        self, display_name, self_paced, staff=False,
        individual_start_days=None, individual_start_hours=None, individual_start_minutes=None,
        individual_due_days=None, individual_due_hours=None, individual_due_minutes=None
    ):
        """Set up a course with `display_name` and `self_paced` attributes.

        Creates a child block with a start date and a due date and individual data,
        and ensures that field overrides are correctly applied for both blocks.
        """
        course = CourseFactory.create(display_name=display_name, self_paced=self_paced, start=self.start)
        user = UserFactory.create()
        enrollment = CourseEnrollmentFactory.create(user=user, course_id=course.id)
        if staff:
            CourseStaffRole(course.id).add_users(user)
        chapter = ItemFactory.create(
            parent=course,
            individual_start_days=individual_start_days,
            individual_start_hours=individual_start_hours,
            individual_start_minutes=individual_start_minutes
        )
        section = ItemFactory.create(
            parent=chapter,
            due=self.due_date,
            individual_due_days=individual_due_days,
            individual_due_hours=individual_due_hours,
            individual_due_minutes=individual_due_minutes
        )
        inject_field_overrides((course, chapter, section), course, user)
        return (enrollment, chapter, section)

    def test_instructor_paced(self):
        """
        Tests that individual data does not effect to the instructor-paced course.
        """
        _, chapter, section = self.setup_course(
            "Instructor Paced Course", False, True,
            self.individual_start_days, self.individual_start_hours, self.individual_start_minutes,
            self.individual_due_days, self.individual_due_hours, self.individual_due_minutes
        )
        self.assertEqual(self.start, chapter.start)
        self.assertEqual(self.start, section.start)
        self.assertEqual(self.due_date, section.due)

    def test_self_paced(self):
        """
        Tests that individual data apply to the self-paced course.
        """
        enrollment, chapter, section = self.setup_course(
            "Self-Paced Course", True, False,
            self.individual_start_days, self.individual_start_hours, self.individual_start_minutes,
            self.individual_due_days, self.individual_due_hours, self.individual_due_minutes
        )

        expected_start = enrollment.created + timedelta(
            days=self.individual_start_days, hours=self.individual_start_hours, minutes=self.individual_start_minutes
        )
        self.assertEqual(expected_start, chapter.start)
        self.assertEqual(expected_start, section.start)

        expected_due = enrollment.created + timedelta(
            days=self.individual_due_days, hours=self.individual_due_hours, minutes=self.individual_due_minutes
        )
        self.assertEqual(expected_due, section.due)

    def test_self_paced_by_staff(self):
        """
        Tests that a start date and a due date to be None if accessing by staff.
        """
        _, chapter, section = self.setup_course(
            "Self-Paced Course", True, True,
            self.individual_start_days, self.individual_start_hours, self.individual_start_minutes,
            self.individual_due_days, self.individual_due_hours, self.individual_due_minutes
        )
        self.assertIsNone(chapter.start)
        self.assertIsNone(section.start)
        self.assertIsNone(section.due)

    def test_self_paced_no_data(self):
        """
        Tests that a start date and a due date to be None if individual data has not been configured.
        """
        _, chapter, section = self.setup_course("Self-Paced Course", True, False)
        self.assertIsNone(chapter.start)
        self.assertIsNone(section.start)
        self.assertIsNone(section.due)

    def test_self_paced_disabled(self):
        """
        Tests that individual data does not effect if SelfPacedConfiguration is disabled.
        """
        SelfPacedConfiguration(enabled=False).save()
        _, chapter, section = self.setup_course(
            "Self-Paced Course", True, False,
            self.individual_start_days, self.individual_start_hours, self.individual_start_minutes,
            self.individual_due_days, self.individual_due_hours, self.individual_due_minutes
        )
        self.assertEqual(self.start, chapter.start)
        self.assertEqual(self.start, section.start)
        self.assertEqual(self.due_date, section.due)

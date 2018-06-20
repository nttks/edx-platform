# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from courseware.ga_access import is_terminated
from courseware.tests.factories import (
    BetaTesterFactory,
    GaCourseScorerFactory,
    GaGlobalCourseCreatorFactory,
    GaOldCourseViewerStaffFactory,
    StaffFactory,
    UserFactory,
)
from courseware.tests.helpers import LoginEnrollmentTestCase
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from student.models import CourseEnrollment


class IsTerminatedTestCase(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests for course termination hadling logic.
    """
    def _create_enrolled_users(self, course, enroll_days_ago=0):
        # create users
        global_staff = UserFactory(is_staff=True)
        old_course_viewer = GaOldCourseViewerStaffFactory()
        course_staff = StaffFactory(course_key=course.id)
        course_beta_tester = BetaTesterFactory(course_key=course.id)
        student = UserFactory()
        global_course_creator = GaGlobalCourseCreatorFactory()
        course_scorer = GaCourseScorerFactory(course_key=course.id)

        # enroll to course
        enroll_global_staff = CourseEnrollment.enroll(global_staff, course.id)
        enroll_global_staff.created = datetime.now() - timedelta(days=enroll_days_ago)
        enroll_global_staff.save()
        enroll_old_course_viewer = CourseEnrollment.enroll(old_course_viewer, course.id)
        enroll_old_course_viewer.created = datetime.now() - timedelta(days=enroll_days_ago)
        enroll_old_course_viewer.save()
        enroll_course_staff = CourseEnrollment.enroll(course_staff, course.id)
        enroll_course_staff.created = datetime.now() - timedelta(days=enroll_days_ago)
        enroll_course_staff.save()
        enroll_course_beta_tester = CourseEnrollment.enroll(course_beta_tester, course.id)
        enroll_course_beta_tester.created = datetime.now() - timedelta(days=enroll_days_ago)
        enroll_course_beta_tester.save()
        enroll_student = CourseEnrollment.enroll(student, course.id)
        enroll_student.created = datetime.now() - timedelta(days=enroll_days_ago)
        enroll_student.save()
        enroll_global_course_creator = CourseEnrollment.enroll(global_course_creator, course.id)
        enroll_global_course_creator.created = datetime.now() - timedelta(days=enroll_days_ago)
        enroll_global_course_creator.save()
        enroll_course_scorer = CourseEnrollment.enroll(course_scorer, course.id)
        enroll_course_scorer.created = datetime.now() - timedelta(days=enroll_days_ago)
        enroll_course_scorer.save()

        return global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer

    def setUp(self):
        super(IsTerminatedTestCase, self).setUp()

    def test_self_paced_course_after_course_registration_date(self):
        """
        Tests for Self-Paced course, after course registration date
        """

        # create Self-Paced course, after course registration date
        course = CourseFactory.create(
            self_paced=True,
            individual_end_days=10,
            enrollment_start=datetime.now() - timedelta(days=60),
            start=datetime.now() - timedelta(days=60),
            end=datetime.now() - timedelta(days=30),
            enrollment_end=datetime.now() - timedelta(days=30),
            terminate_start=datetime.now() + timedelta(days=60),
        )

        # get course overview
        course_overview = CourseOverview.get_from_id(course.id)

        # create users and enroll to course
        global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer = self._create_enrolled_users(course)

        # assert is_terminated
        self.assertFalse(is_terminated(course_overview, global_staff))
        self.assertFalse(is_terminated(course_overview, old_course_viewer))
        self.assertFalse(is_terminated(course_overview, course_staff))
        self.assertFalse(is_terminated(course_overview, course_beta_tester))
        self.assertFalse(is_terminated(course_overview, student))
        self.assertFalse(is_terminated(course_overview, global_course_creator))
        self.assertFalse(is_terminated(course_overview, course_scorer))

    def test_self_paced_course_after_self_pace_course_finished(self):
        """
        Tests for Self-Paced course, after self pace course finished
        """

        # create Self-Paced course, after self pace course finished
        course = CourseFactory.create(
            self_paced=True,
            individual_end_days=10,
            enrollment_start=datetime.now() - timedelta(days=60),
            start=datetime.now() - timedelta(days=60),
            end=datetime.now() + timedelta(days=30),
            enrollment_end=datetime.now() + timedelta(days=60),
            terminate_start=datetime.now() + timedelta(days=60),
        )

        # get course overview
        course_overview = CourseOverview.get_from_id(course.id)

        # create users and enroll to course
        global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer = self._create_enrolled_users(
            course=course, enroll_days_ago=20)

        # assert is_terminated
        self.assertFalse(is_terminated(course_overview, global_staff))
        self.assertFalse(is_terminated(course_overview, old_course_viewer))
        self.assertFalse(is_terminated(course_overview, course_staff))
        self.assertFalse(is_terminated(course_overview, course_beta_tester))
        self.assertTrue(is_terminated(course_overview, student))
        self.assertFalse(is_terminated(course_overview, global_course_creator))
        self.assertFalse(is_terminated(course_overview, course_scorer))

    def test_self_paced_course_after_course_closed(self):
        """
        Tests for Self-Paced course, after course closed
        """

        # create Self-Paced course, after course closed
        course = CourseFactory.create(
            self_paced=True,
            individual_end_days=10,
            enrollment_start=datetime.now() - timedelta(days=60),
            start=datetime.now() - timedelta(days=60),
            end=datetime.now() - timedelta(days=30),
            enrollment_end=datetime.now() - timedelta(days=30),
            terminate_start=datetime.now() - timedelta(days=30),
        )

        # get course overview
        course_overview = CourseOverview.get_from_id(course.id)

        # create users and enroll to course
        global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer = self._create_enrolled_users(course)

        # assert is_terminated
        self.assertFalse(is_terminated(course_overview, global_staff))
        self.assertFalse(is_terminated(course_overview, old_course_viewer))
        self.assertFalse(is_terminated(course_overview, course_staff))
        self.assertTrue(is_terminated(course_overview, course_beta_tester))
        self.assertTrue(is_terminated(course_overview, student))
        self.assertFalse(is_terminated(course_overview, global_course_creator))
        self.assertFalse(is_terminated(course_overview, course_scorer))

    def test_self_paced_course_after_course_start(self):
        """
        Tests for Self-Paced course, after course start
        """

        # create Self-Paced course, after course start
        course = CourseFactory.create(
            self_paced=True,
            individual_end_days=10,
            enrollment_start=datetime.now() - timedelta(days=30),
            start=datetime.now() - timedelta(days=30),
            end=datetime.now() + timedelta(days=30),
            enrollment_end=datetime.now() + timedelta(days=30),
            terminate_start=datetime.now() + timedelta(days=30),
        )

        # get course overview
        course_overview = CourseOverview.get_from_id(course.id)

        # create users and enroll to course
        global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer = self._create_enrolled_users(course)

        # assert is_terminated
        self.assertFalse(is_terminated(course_overview, global_staff))
        self.assertFalse(is_terminated(course_overview, old_course_viewer))
        self.assertFalse(is_terminated(course_overview, course_staff))
        self.assertFalse(is_terminated(course_overview, course_beta_tester))
        self.assertFalse(is_terminated(course_overview, student))
        self.assertFalse(is_terminated(course_overview, global_course_creator))
        self.assertFalse(is_terminated(course_overview, course_scorer))

    def test_self_paced_course_before_course_start(self):
        """
        Tests for Self-Paced course, before course start
        """

        # create Self-Paced course, before course start
        course = CourseFactory.create(
            self_paced=True,
            individual_end_days=10,
            enrollment_start=datetime.now() + timedelta(days=30),
            start=datetime.now() + timedelta(days=30),
            end=datetime.now() + timedelta(days=60),
            enrollment_end=datetime.now() + timedelta(days=60),
            terminate_start=datetime.now() + timedelta(days=60),
        )

        # get course overview
        course_overview = CourseOverview.get_from_id(course.id)

        # create users and enroll to course
        global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer = self._create_enrolled_users(course)

        # assert is_terminated
        self.assertFalse(is_terminated(course_overview, global_staff))
        self.assertFalse(is_terminated(course_overview, old_course_viewer))
        self.assertFalse(is_terminated(course_overview, course_staff))
        self.assertFalse(is_terminated(course_overview, course_beta_tester))
        self.assertFalse(is_terminated(course_overview, student))  # note
        self.assertFalse(is_terminated(course_overview, global_course_creator))
        self.assertFalse(is_terminated(course_overview, course_scorer))

    def test_instructor_paced_course_after_registration_close(self):
        """
        Tests for Instructor-Paced course, after registration closed
        """

        # create Instructor-Paced course, after registration closed
        course = CourseFactory.create(
            self_paced=False,
            enrollment_start=datetime.now() - timedelta(days=60),
            start=datetime.now() - timedelta(days=60),
            end=datetime.now() - timedelta(days=30),
            enrollment_end=datetime.now() - timedelta(days=30),
            terminate_start=datetime.now() + timedelta(days=30),
        )

        # get course overview
        course_overview = CourseOverview.get_from_id(course.id)

        # create users and enroll to course
        global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer = self._create_enrolled_users(course)

        # assert is_terminated
        self.assertFalse(is_terminated(course_overview, global_staff))
        self.assertFalse(is_terminated(course_overview, old_course_viewer))
        self.assertFalse(is_terminated(course_overview, course_staff))
        self.assertFalse(is_terminated(course_overview, course_beta_tester))
        self.assertFalse(is_terminated(course_overview, student))
        self.assertFalse(is_terminated(course_overview, global_course_creator))
        self.assertFalse(is_terminated(course_overview, course_scorer))

    def test_instructor_paced_course_after_course_closed(self):
        """
        Tests for Instructor-Paced course, after course closed
        """

        # create Instructor-Paced course, after course closed
        course = CourseFactory.create(
            self_paced=False,
            enrollment_start=datetime.now() - timedelta(days=60),
            start=datetime.now() - timedelta(days=60),
            end=datetime.now() - timedelta(days=30),
            enrollment_end=datetime.now() - timedelta(days=30),
            terminate_start=datetime.now() - timedelta(days=30),
        )

        # get course overview
        course_overview = CourseOverview.get_from_id(course.id)

        # create users and enroll to course
        global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer = self._create_enrolled_users(course)

        # assert is_terminated
        self.assertFalse(is_terminated(course_overview, global_staff))
        self.assertFalse(is_terminated(course_overview, old_course_viewer))
        self.assertFalse(is_terminated(course_overview, course_staff))
        self.assertTrue(is_terminated(course_overview, course_beta_tester))
        self.assertTrue(is_terminated(course_overview, student))
        self.assertFalse(is_terminated(course_overview, global_course_creator))
        self.assertFalse(is_terminated(course_overview, course_scorer))

    def test_instructor_paced_course_after_course_finished(self):
        """
        Tests for Instructor-Paced course, after course finished
        """

        # create Instructor-Paced course, after course finished
        course = CourseFactory.create(
            self_paced=False,
            enrollment_start=datetime.now() - timedelta(days=60),
            start=datetime.now() - timedelta(days=60),
            end=datetime.now() - timedelta(days=30),
            enrollment_end=datetime.now() - timedelta(days=30),
            terminate_start=datetime.now() + timedelta(days=30),
        )

        # get course overview
        course_overview = CourseOverview.get_from_id(course.id)

        # create users and enroll to course
        global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer = self._create_enrolled_users(course)

        # assert is_terminated
        self.assertFalse(is_terminated(course_overview, global_staff))
        self.assertFalse(is_terminated(course_overview, old_course_viewer))
        self.assertFalse(is_terminated(course_overview, course_staff))
        self.assertFalse(is_terminated(course_overview, course_beta_tester))
        self.assertFalse(is_terminated(course_overview, student))
        self.assertFalse(is_terminated(course_overview, global_course_creator))
        self.assertFalse(is_terminated(course_overview, course_scorer))

    def test_instructor_paced_course_after_course_start(self):
        """
        Tests for Instructor-Paced course, after course start
        """

        # create Instructor-Paced course, after course start
        course = CourseFactory.create(
            self_paced=False,
            enrollment_start=datetime.now() - timedelta(days=30),
            start=datetime.now() - timedelta(days=30),
            end=datetime.now() + timedelta(days=30),
            enrollment_end=datetime.now() + timedelta(days=30),
            terminate_start=datetime.now() + timedelta(days=30),
        )

        # get course overview
        course_overview = CourseOverview.get_from_id(course.id)

        # create users and enroll to course
        global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer = self._create_enrolled_users(course)

        # assert is_terminated
        self.assertFalse(is_terminated(course_overview, global_staff))
        self.assertFalse(is_terminated(course_overview, old_course_viewer))
        self.assertFalse(is_terminated(course_overview, course_staff))
        self.assertFalse(is_terminated(course_overview, course_beta_tester))
        self.assertFalse(is_terminated(course_overview, student))
        self.assertFalse(is_terminated(course_overview, global_course_creator))
        self.assertFalse(is_terminated(course_overview, course_scorer))

    def test_instructor_paced_course_before_course_start(self):
        """
        Tests for Instructor-Paced course, before course start
        """

        # create Instructor-Paced course, before course start
        course = CourseFactory.create(
            self_paced=False,
            enrollment_start=datetime.now() + timedelta(days=30),
            start=datetime.now() + timedelta(days=30),
            end=datetime.now() + timedelta(days=60),
            enrollment_end=datetime.now() + timedelta(days=60),
            terminate_start=datetime.now() + timedelta(days=60),
        )

        # get course overview
        course_overview = CourseOverview.get_from_id(course.id)

        # create users and enroll to course
        global_staff, old_course_viewer, course_staff, course_beta_tester, student, global_course_creator, course_scorer = self._create_enrolled_users(course)

        # assert is_terminated
        self.assertFalse(is_terminated(course_overview, global_staff))
        self.assertFalse(is_terminated(course_overview, old_course_viewer))
        self.assertFalse(is_terminated(course_overview, course_staff))
        self.assertFalse(is_terminated(course_overview, course_beta_tester))
        self.assertFalse(is_terminated(course_overview, student))
        self.assertFalse(is_terminated(course_overview, global_course_creator))
        self.assertFalse(is_terminated(course_overview, course_scorer))

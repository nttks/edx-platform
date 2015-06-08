import unittest
from django.conf import settings
from django.test import TestCase
from django.core.management import call_command, CommandError

from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from student.tests.factories import UserFactory, UserStandingFactory
from student.models import CourseEnrollment, UserStanding

from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory


@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class EnrollAllUsersTest(ModuleStoreTestCase):
    """
    Tests for the command.
    """

    def setUp(self):
        super(EnrollAllUsersTest, self).setUp(**{'create_user': False})

        self.users = [UserFactory.create() for _ in range(5)]
        self.courses = [CourseFactory.create(display_name="test course {}".format(i)) for i in range(3)]
        # course0 and course1 are global course
        CourseGlobalSettingFactory.create(course_id=self.courses[0].id)
        CourseGlobalSettingFactory.create(course_id=self.courses[1].id)
        # mark user2 resigned
        UserStandingFactory.create(user=self.users[2], account_status=UserStanding.ACCOUNT_DISABLED, changed_by=self.users[0])
        # user0 is enroll in course0
        CourseEnrollment.enroll(self.users[0], self.courses[0].id)
        # user1 is enroll in course0 and course1
        CourseEnrollment.enroll(self.users[1], self.courses[0].id)
        CourseEnrollment.enroll(self.users[1], self.courses[1].id)

    def test_no_arguments(self):
        self.assertRaises(CommandError, call_command, ('enroll_global_course',))

    def test_invalid_arguments(self):
        self.assertRaises(CommandError, call_command, ('enroll_global_course',), **{'all': True, 'course_id': self.courses[0].id.to_deprecated_string()})

    def test_enroll_one_course(self):
        self.assertEquals(2, CourseEnrollment.objects.num_enrolled_in(self.courses[0].id))
        call_command('enroll_global_course', *[], **{'course_id': self.courses[0].id.to_deprecated_string()})
        self.assertEquals(4, CourseEnrollment.objects.num_enrolled_in(self.courses[0].id))

    def test_enroll_all_courses(self):
        self.assertEquals(2, CourseEnrollment.objects.num_enrolled_in(self.courses[0].id))
        self.assertEquals(1, CourseEnrollment.objects.num_enrolled_in(self.courses[1].id))

        call_command('enroll_global_course', all=True)

        self.assertEquals(4, CourseEnrollment.objects.num_enrolled_in(self.courses[0].id))
        self.assertEquals(4, CourseEnrollment.objects.num_enrolled_in(self.courses[1].id))

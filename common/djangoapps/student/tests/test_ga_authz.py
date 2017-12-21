"""
Tests authz.py
"""

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from opaque_keys.edx.locations import SlashSeparatedCourseKey
from student.auth import user_has_role, add_users, remove_users
from student.roles import CourseInstructorRole, CourseStaffRole, GaCourseScorerRole, GaGlobalCourseCreatorRole
from student.tests.factories import AdminFactory


class CourseGroupTest(TestCase):
    """
    Tests for instructor and staff groups for a particular course.
    """

    def setUp(self):
        """ Test case setup """
        super(CourseGroupTest, self).setUp()
        self.course_key = SlashSeparatedCourseKey('mitX', '101', 'test')
        self.global_admin = AdminFactory()
        self.creator = User.objects.create_user('testcreator', 'testcreator+courses@edx.org', 'foo')
        self.staff = User.objects.create_user('teststaff', 'teststaff+courses@edx.org', 'foo')
        self.ga_global_course_creator = User.objects.create_user('testgaglobalcoursecreator', 'testgaglobalcoursecreator+courses@edx.org', 'foo')
        add_users(self.global_admin, GaGlobalCourseCreatorRole(), self.ga_global_course_creator)
        self.ga_course_scorer = User.objects.create_user('testgacoursescorer', 'testgacoursescorer+courses@edx.org', 'foo')
        add_users(self.global_admin, GaCourseScorerRole(self.course_key), self.ga_course_scorer)

    def test_add_user_to_course_group(self):
        """
        Tests adding user to course group (happy path).
        """
        # Create groups for a new course (and assign instructor role to the creator).
        self.assertFalse(user_has_role(self.creator, CourseInstructorRole(self.course_key)))
        add_users(self.ga_global_course_creator, CourseInstructorRole(self.course_key), self.creator)
        add_users(self.ga_global_course_creator, CourseStaffRole(self.course_key), self.creator)
        self.assertTrue(user_has_role(self.creator, CourseInstructorRole(self.course_key)))

    def test_add_user_to_course_group_permission_denied(self):
        """
        Verifies PermissionDenied if caller of add_user_to_course_group is not instructor role.
        """
        with self.assertRaises(PermissionDenied):
            add_users(self.ga_course_scorer, CourseStaffRole(self.course_key), self.staff)

    def test_remove_user_from_course_group(self):
        """
        Tests removing user from course group (happy path).
        """
        add_users(self.ga_global_course_creator, CourseInstructorRole(self.course_key), self.creator)
        add_users(self.ga_global_course_creator, CourseStaffRole(self.course_key), self.creator)

        remove_users(self.ga_global_course_creator, CourseInstructorRole(self.course_key), self.creator)
        self.assertFalse(user_has_role(self.creator, CourseInstructorRole(self.course_key)))

        remove_users(self.ga_global_course_creator, CourseStaffRole(self.course_key), self.creator)
        self.assertFalse(user_has_role(self.creator, CourseStaffRole(self.course_key)))

    def test_remove_user_from_course_group_permission_denied(self):
        """
        Verifies PermissionDenied if caller of remove_user_from_course_group is not instructor role.
        """
        add_users(self.ga_global_course_creator, CourseStaffRole(self.course_key), self.staff)
        with self.assertRaises(PermissionDenied):
            remove_users(self.ga_course_scorer, CourseStaffRole(self.course_key), self.staff)

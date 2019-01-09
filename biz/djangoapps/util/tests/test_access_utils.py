"""
Tests for test_access_utils
"""

from student.tests.factories import UserFactory

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from biz.djangoapps.util import access_utils
from biz.djangoapps.util.tests.testcase import TestCase

class AccessUtilsTest(ModuleStoreTestCase):

    def test_staff(self):
        user = UserFactory.create(is_staff=True)
        course = CourseFactory.create()
        self.assertTrue(access_utils.has_staff_access(user, course.id))

    def test_non_staff(self):
        user = UserFactory.create()
        course = CourseFactory.create()
        self.assertFalse(access_utils.has_staff_access(user, course.id))

"""
Tests for cache_utils
"""
from datetime import datetime
from mock import patch

from opaque_keys.edx.keys import CourseKey
from student.tests.factories import UserFactory

from biz.djangoapps.util import cache_utils
from biz.djangoapps.util.tests.testcase import BizTestBase


class CacheUtilsTest(BizTestBase):

    def test_course_selection(self):
        user = UserFactory.create()

        self.assertEqual((None, None, None), cache_utils.get_course_selection(user))

        cache_utils.set_course_selection(user, 123, 456, 789)
        self.assertEqual((123, 456, 789), cache_utils.get_course_selection(user))
        # access by another user
        self.assertEqual((None, None, None), cache_utils.get_course_selection(UserFactory.create()))

        # override
        cache_utils.set_course_selection(user, 456, 789, 123)
        self.assertEqual((456, 789, 123), cache_utils.get_course_selection(user))

        # Verify that the setting by the other user does not affect
        user_x = UserFactory.create()
        cache_utils.set_course_selection(user_x, 123, 456, 789)
        self.assertEqual((456, 789, 123), cache_utils.get_course_selection(user))
        self.assertEqual((123, 456, 789), cache_utils.get_course_selection(user_x))

        cache_utils.delete_course_selection(user)
        # Verify after deleted
        self.assertEqual((None, None, None), cache_utils.get_course_selection(user))
        # Verify that the deleting by the other user does not affect
        self.assertEqual((123, 456, 789), cache_utils.get_course_selection(user_x))

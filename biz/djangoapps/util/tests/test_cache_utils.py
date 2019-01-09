"""
Tests for cache_utils
"""
from student.tests.factories import UserFactory

from biz.djangoapps.util import cache_utils
from biz.djangoapps.util.tests.testcase import BizTestBase
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory


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

    def test_organization_group(self):
        user = UserFactory.create()
        group1 = GroupFactory.create(
            org=self._create_organization(), group_code='group1', group_name='group1', parent_id=0, level_no=0,
            created_by=UserFactory.create()
        )
        self.assertEqual((None, None), cache_utils.get_organization_group(user))

        cache_utils.set_organization_group(user, group1, [1, 2, 3])
        self.assertEqual((group1, [1, 2, 3]), cache_utils.get_organization_group(user))
        # access by another user
        self.assertEqual((None, None), cache_utils.get_organization_group(UserFactory.create()))

        # override
        group2 = GroupFactory.create(
            org=self._create_organization(), group_code='group2', group_name='group2', parent_id=1, level_no=1,
            created_by=UserFactory.create()
        )
        cache_utils.set_organization_group(user, group2, [4, 5, 6])
        self.assertEqual((group2, [4, 5, 6]), cache_utils.get_organization_group(user))

        # Verify that the setting by the other user does not affect
        user_x = UserFactory.create()
        cache_utils.set_organization_group(user_x, group1, [1, 2, 3])
        self.assertEqual((group2, [4, 5, 6]), cache_utils.get_organization_group(user))
        self.assertEqual((group1, [1, 2, 3]), cache_utils.get_organization_group(user_x))

        cache_utils.delete_organization_group(user)
        # Verify after deleted
        self.assertEqual((None, None), cache_utils.get_organization_group(user))
        # Verify that the deleting by the other user does not affect
        self.assertEqual((group1, [1, 2, 3]), cache_utils.get_organization_group(user_x))


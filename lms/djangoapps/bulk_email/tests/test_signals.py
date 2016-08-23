"""
Unit tests for signal to optout.
"""
import ddt
import unittest

from bulk_email.models import Optout
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from .factories import OptoutFactory


@ddt.ddt
class TestFromCourseGlobalSetting(ModuleStoreTestCase):

    def setUp(self):
        super(TestFromCourseGlobalSetting, self).setUp()
        self.user1 = UserFactory.create()
        self.user2 = UserFactory.create()
        self.user3 = UserFactory.create()
        self.user4 = UserFactory.create()

        self.global_course_id = CourseFactory.create(org='global', course='course', run='run').id

    def _assert_optout_exists(self, user, course_id):
        self.assertIsNotNone(Optout.objects.get(user=user, course_id=course_id))

    def _assert_optout_not_exists(self, user, course_id):
        with self.assertRaises(Optout.DoesNotExist):
            Optout.objects.get(user=user, course_id=course_id)

    def _setup_course_global_setting(self):
        self.global_course_id_enabled = CourseFactory.create(org='global', course='course1', run='run').id
        self.global_course_settings_enabled = CourseGlobalSettingFactory.create(course_id=self.global_course_id_enabled, global_enabled=True)
        OptoutFactory.create(user=self.user1, course_id=self.global_course_id_enabled)
        OptoutFactory.create(user=self.user2, course_id=self.global_course_id_enabled)

        self.global_course_id_disabled = CourseFactory.create(org='global', course='course2', run='run').id
        self.global_course_settings_disabled = CourseGlobalSettingFactory.create(course_id=self.global_course_id_disabled, global_enabled=False)
        OptoutFactory.create(user=self.user1, course_id=self.global_course_id_disabled)
        OptoutFactory.create(user=self.user3, course_id=self.global_course_id_disabled)

    @ddt.data(True, False)
    def test_without_global_course(self, global_enabled):
        # INSERT
        course_global_setting = CourseGlobalSettingFactory.create(course_id=self.global_course_id, global_enabled=global_enabled)
        self._assert_optout_not_exists(self.user1, self.global_course_id)
        self._assert_optout_not_exists(self.user2, self.global_course_id)
        self._assert_optout_not_exists(self.user3, self.global_course_id)
        self._assert_optout_not_exists(self.user4, self.global_course_id)

        # UPDATE
        course_global_setting.global_enabled = not global_enabled
        course_global_setting.save()
        self._assert_optout_not_exists(self.user1, self.global_course_id)
        self._assert_optout_not_exists(self.user2, self.global_course_id)
        self._assert_optout_not_exists(self.user3, self.global_course_id)
        self._assert_optout_not_exists(self.user4, self.global_course_id)

        # DELETE
        course_global_setting.delete()
        self._assert_optout_not_exists(self.user1, self.global_course_id)
        self._assert_optout_not_exists(self.user2, self.global_course_id)
        self._assert_optout_not_exists(self.user3, self.global_course_id)
        self._assert_optout_not_exists(self.user4, self.global_course_id)

    def test_with_global_course_enabled(self):
        self._setup_course_global_setting()

        # INSERT
        course_global_setting = CourseGlobalSettingFactory.create(course_id=self.global_course_id, global_enabled=True)
        self._assert_optout_exists(self.user1, self.global_course_id)
        self._assert_optout_exists(self.user2, self.global_course_id)
        self._assert_optout_not_exists(self.user3, self.global_course_id)
        self._assert_optout_not_exists(self.user4, self.global_course_id)

        # UPDATE
        course_global_setting.global_enabled = False
        course_global_setting.save()
        self._assert_optout_exists(self.user1, self.global_course_id)
        self._assert_optout_exists(self.user2, self.global_course_id)
        self._assert_optout_not_exists(self.user3, self.global_course_id)
        self._assert_optout_not_exists(self.user4, self.global_course_id)

        # DELETE
        course_global_setting.delete()
        self._assert_optout_exists(self.user1, self.global_course_id)
        self._assert_optout_exists(self.user2, self.global_course_id)
        self._assert_optout_not_exists(self.user3, self.global_course_id)
        self._assert_optout_not_exists(self.user4, self.global_course_id)

    def test_with_global_course_disabled(self):
        self._setup_course_global_setting()

        # INSERT
        course_global_setting = CourseGlobalSettingFactory.create(course_id=self.global_course_id, global_enabled=False)
        self._assert_optout_not_exists(self.user1, self.global_course_id)
        self._assert_optout_not_exists(self.user2, self.global_course_id)
        self._assert_optout_not_exists(self.user3, self.global_course_id)
        self._assert_optout_not_exists(self.user4, self.global_course_id)

        # UPDATE
        course_global_setting.global_enabled = True
        course_global_setting.save()
        self._assert_optout_exists(self.user1, self.global_course_id)
        self._assert_optout_exists(self.user2, self.global_course_id)
        self._assert_optout_not_exists(self.user3, self.global_course_id)
        self._assert_optout_not_exists(self.user4, self.global_course_id)

        # DELETE
        course_global_setting.delete()
        self._assert_optout_exists(self.user1, self.global_course_id)
        self._assert_optout_exists(self.user2, self.global_course_id)
        self._assert_optout_not_exists(self.user3, self.global_course_id)
        self._assert_optout_not_exists(self.user4, self.global_course_id)

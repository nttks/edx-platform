# -*- coding: utf-8 -*-
"""
Unit tests for receive email APIs.
"""
import unittest

from django.conf import settings

from bulk_email.models import Optout
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ...errors import ReceiveEmailNotFoundGlobalCourseError, UserNotFound
from ..api import (
    can_receive_email_global_course, optout_global_course, optin_global_course
)


@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Account APIs are only supported in LMS')
class TestReceiveEmailAPI(ModuleStoreTestCase):

    def setUp(self):
        super(TestReceiveEmailAPI, self).setUp()
        self.user = UserFactory.create()

    def test_user_none(self):
        """
        Verifies behavior user is none.
        """
        with self.assertRaises(UserNotFound):
            can_receive_email_global_course(None)

        with self.assertRaises(UserNotFound):
            optout_global_course(None)

        with self.assertRaises(UserNotFound):
            optin_global_course(None)

    def test_with_global_course(self):
        """
        Verifies behavior with global course.
        """
        global_course_id = CourseFactory.create(org='global', course='course1', run='run').id
        CourseGlobalSettingFactory.create(course_id=global_course_id)

        self.assertTrue(can_receive_email_global_course(self.user))
        with self.assertRaises(Optout.DoesNotExist):
            Optout.objects.get(user=self.user, course_id=global_course_id)

        optout_global_course(self.user)
        self.assertFalse(can_receive_email_global_course(self.user))
        self.assertIsNotNone(Optout.objects.get(user=self.user, course_id=global_course_id))

        optin_global_course(self.user)
        self.assertTrue(can_receive_email_global_course(self.user))
        with self.assertRaises(Optout.DoesNotExist):
            Optout.objects.get(user=self.user, course_id=global_course_id)

    def test_without_global_course(self):
        """
        Verifies behavior without global course.
        """
        with self.assertRaises(ReceiveEmailNotFoundGlobalCourseError):
            can_receive_email_global_course(self.user)

        with self.assertRaises(ReceiveEmailNotFoundGlobalCourseError):
            optout_global_course(self.user)

        with self.assertRaises(ReceiveEmailNotFoundGlobalCourseError):
            optin_global_course(self.user)

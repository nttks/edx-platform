# -*- coding: utf-8 -*-
"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command

from biz.djangoapps.util.tests.testcase import BizTestBase
from student.models import Registration
from student.tests.factories import UserFactory, RegistrationFactory, UserProfileFactory


class MaskUserTest(BizTestBase):

    def setUp(self):
        self.user = UserFactory.create(is_active=False)

        # Create a registration for the user
        self.registration = RegistrationFactory.create(user=self.user, masked=False)
        modified_datetime = datetime.now() - timedelta(2)
        Registration.objects.filter(pk=self.registration.id).update(modified=modified_datetime)

        # Create a profile for the user
        UserProfileFactory(user=self.user)

    def test_call_command_mask_user(self):
        call_command('mask_user')

        user = User.objects.get(pk=self.user.id)
        self.assertNotEquals(self.user.email, user.email)
        self.assertNotEquals(self.user.registration.modified, user.registration.modified)
        self.assertEquals(user.first_name, '')
        self.assertEquals(user.last_name, '')
        self.assertTrue(user.registration.masked)

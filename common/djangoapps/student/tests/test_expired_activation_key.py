"""
Tests for expired activation key
"""
import unittest

from django.conf import settings
from django.core.urlresolvers import reverse

from student.tests.factories import UserFactory, RegistrationFactory, UserProfileFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class ExpiredActivationKeyTest(ModuleStoreTestCase):
    """Tests for expired activation key"""

    def setUp(self):
        super(ExpiredActivationKeyTest, self).setUp()

    def test_user_not_active_and_masked(self):
        user = UserFactory.create(is_active=False)
        registration = RegistrationFactory.create(user=user, masked=True)
        UserProfileFactory(user=user)

        response = self.client.get(reverse('activate', kwargs={'key': registration.activation_key}))
        self.assertEqual(response.status_code, 200)
        self.assertRegexpMatches(response.content, 'This URL validity has expired')
        self.assertRegexpMatches(response.content, 'Unfortunately, this URL validity has expired')

    def test_user_not_active_and_not_masked(self):
        user = UserFactory.create(is_active=False)
        registration = RegistrationFactory.create(user=user, masked=False)
        UserProfileFactory(user=user)

        response = self.client.get(reverse('activate', kwargs={'key': registration.activation_key}))
        self.assertEqual(response.status_code, 200)
        self.assertRegexpMatches(response.content, 'Thanks for activating your account')

    def test_user_already_active_and_masked(self):
        user = UserFactory.create(is_active=True)
        registration = RegistrationFactory.create(user=user, masked=True)
        UserProfileFactory(user=user)

        response = self.client.get(reverse('activate', kwargs={'key': registration.activation_key}))
        self.assertEqual(response.status_code, 200)
        self.assertRegexpMatches(response.content, 'This URL validity has expired')
        self.assertRegexpMatches(response.content, 'Unfortunately, this URL validity has expired')

    def test_user_already_active_and_not_masked(self):
        user = UserFactory.create(is_active=True)
        registration = RegistrationFactory.create(user=user, masked=False)
        UserProfileFactory(user=user)

        response = self.client.get(reverse('activate', kwargs={'key': registration.activation_key}))
        self.assertEqual(response.status_code, 200)
        self.assertRegexpMatches(response.content, 'This account has already been activated')

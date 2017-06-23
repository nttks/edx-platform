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
        self.user = UserFactory.create(is_active=False)

        # Create a registration for the user
        self.registration = RegistrationFactory.create(user=self.user, masked=True)

        # Create a profile for the user
        UserProfileFactory(user=self.user)

    def test_expired_activation_key(self):
        response = self.client.get(reverse('activate', kwargs={'key': self.registration.activation_key}))

        self.assertEqual(response.status_code, 200)
        self.assertRegexpMatches(response.content, 'This URL validity has expired')
        self.assertRegexpMatches(response.content, 'Unfortunately, this URL validity has expired')

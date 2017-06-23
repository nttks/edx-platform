"""
Tests for notice unactivated
"""
import unittest

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class NoticeUnactivatedTest(ModuleStoreTestCase):
    """Tests for notice unactivated"""

    def setUp(self):
        self.username = "test_user"
        self.url = reverse("notice_unactivated")
        self.request_factory = RequestFactory()
        self.params = {
            "username": self.username,
            "email": "test@example.org",
            "password": "testpass",
            "name": "Test User",
        }

    def test_notice_unactivated_confirm_param(self):
        response = self.client.post(self.url, self.params)
        self.assertEquals(response.status_code, 302)
        self.assertTrue(response.url.endswith('unactivated=true'))

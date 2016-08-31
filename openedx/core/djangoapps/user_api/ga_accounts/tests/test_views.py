"""
Unit tests for ga_accounts APIs.
"""

import unittest

from django.core.urlresolvers import reverse
from django.conf import settings

from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ...accounts.tests.test_views import UserAPITestCase


@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class TestReceiveEmailAPI(UserAPITestCase, ModuleStoreTestCase):
    """
    Unit tests /api/user/v1/receive_email/{username}
    """
    def setUp(self):
        super(TestReceiveEmailAPI, self).setUp()
        self.url_endpoint_name = "ga_receive_email_api"
        self.url = reverse(self.url_endpoint_name, kwargs={'username': self.user.username})

    def test_anonymous_access(self):
        """
        Test that an anonymous client (not logged in) cannot call GET or PUT or DELETE.
        """
        self.send_get(self.anonymous_client, expected_status=403)
        self.send_put(self.anonymous_client, {}, expected_status=403)
        self.send_delete(self.anonymous_client, expected_status=403)

    def test_unsupported_methods(self):
        """
        Test that POST, and PATCH are not supported.
        """
        self.client.login(username=self.user.username, password=self.test_password)
        self.assertEqual(405, self.client.post(self.url).status_code)
        self.assertEqual(405, self.client.patch(self.url).status_code)

    def test_different_user(self):
        """
        Test that a client (logged in) cannot call GET or PUT or DELETE for a different client.
        """
        self.different_client.login(username=self.different_user.username, password=self.test_password)
        self.send_get(self.different_client, expected_status=403)
        self.send_put(self.different_client, {}, expected_status=403)
        self.send_delete(self.different_client, expected_status=403)

    def test_get_receive_email_with_global_course(self):
        """
        Test that a global course exists.
        """
        # Create global course.
        CourseGlobalSettingFactory.create(course_id=CourseFactory.create(org='global', course='course1', run='run').id)

        self.client.login(username=self.user.username, password=self.test_password)

        # Do the GET.
        self.assertEqual(
            {
                "is_receive_email": True,
                "has_global_courses": True
            },
            self.send_get(self.client, expected_status=200).data
        )

        # Do the PUT.
        self.send_put(self.client, {}, expected_status=204)

        # Do the DELETE.
        self.send_delete(self.client, expected_status=204)

    def test_get_receive_email_without_global_course(self):
        """
        Test that a global course not exists.
        """
        self.client.login(username=self.user.username, password=self.test_password)

        # Do the GET.
        self.assertEqual(
            {
                "is_receive_email": False,
                "has_global_courses": False
            },
            self.send_get(self.client, expected_status=200).data
        )

        # Do the PUT.
        self.send_put(self.client, {}, expected_status=400)

        # Do the DELETE.
        self.send_delete(self.client, expected_status=400)

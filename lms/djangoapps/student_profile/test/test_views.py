# -*- coding: utf-8 -*-
""" Tests for student profile views. """

import boto
from boto.s3.key import Key
import ddt
import pytz
from copy import copy
from datetime import datetime, timedelta
from mock import patch, MagicMock
from moto import mock_s3
from StringIO import StringIO

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
from django.test.utils import override_settings

from certificates.tests.factories import GeneratedCertificateFactory  # pylint: disable=import-error

from util.testing import UrlResetMixin
from student.tests.factories import UserFactory, CourseEnrollmentFactory

from student_profile.views import learner_profile_context

from xmodule.contentstore.content import StaticContent
from xmodule.contentstore.django import contentstore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


class LearnerProfileViewTest(UrlResetMixin, ModuleStoreTestCase):
    """ Tests for the student profile view. """

    USERNAME = "username"
    PASSWORD = "password"
    CONTEXT_DATA = [
        'default_public_account_fields',
        'accounts_api_url',
        'preferences_api_url',
        'account_settings_page_url',
        'has_preferences_access',
        'own_profile',
        'country_options',
        'language_options',
        'account_settings_data',
        'preferences_data',
        'cert_infos',
    ]

    def setUp(self):
        super(LearnerProfileViewTest, self).setUp()
        self.user = UserFactory.create(username=self.USERNAME, password=self.PASSWORD)
        self.client.login(username=self.USERNAME, password=self.PASSWORD)
        self.course = CourseFactory.create()

    def test_context(self):
        """
        Verify learner profile page context data.
        """
        request = RequestFactory().get('/url')
        request.user = self.user

        context = learner_profile_context(request, self.USERNAME, self.user.is_staff)

        self.assertEqual(
            context['data']['default_public_account_fields'],
            settings.ACCOUNT_VISIBILITY_CONFIGURATION['public_fields']
        )

        self.assertEqual(
            context['data']['accounts_api_url'],
            reverse("accounts_api", kwargs={'username': self.user.username})
        )

        self.assertEqual(
            context['data']['preferences_api_url'],
            reverse('preferences_api', kwargs={'username': self.user.username})
        )

        self.assertEqual(
            context['data']['profile_image_upload_url'],
            reverse("profile_image_upload", kwargs={'username': self.user.username})
        )

        self.assertEqual(
            context['data']['profile_image_remove_url'],
            reverse('profile_image_remove', kwargs={'username': self.user.username})
        )

        self.assertEqual(
            context['data']['profile_image_max_bytes'],
            settings.PROFILE_IMAGE_MAX_BYTES
        )

        self.assertEqual(
            context['data']['profile_image_min_bytes'],
            settings.PROFILE_IMAGE_MIN_BYTES
        )

        self.assertEqual(context['data']['account_settings_page_url'], reverse('account_settings'))

        for attribute in self.CONTEXT_DATA:
            self.assertIn(attribute, context['data'])

    def test_view(self):
        """
        Verify learner profile page view.
        """
        profile_path = reverse('learner_profile', kwargs={'username': self.USERNAME})
        response = self.client.get(path=profile_path)

        for attribute in self.CONTEXT_DATA:
            self.assertIn(attribute, response.content)

    def test_undefined_profile_page(self):
        """
        Verify that a 404 is returned for a non-existent profile page.
        """
        profile_path = reverse('learner_profile', kwargs={'username': "no_such_user"})
        response = self.client.get(path=profile_path)
        self.assertEqual(404, response.status_code)

    def test_change_cert_visibility(self):
        """
        Verify that the url to change setting of visibility accepts a post request.
        """
        tochange_path = reverse('change_visibility_certificates', kwargs={'course_id': self.course.id})
        response = self.client.post(path=tochange_path, data={'is_visible_to_public': '1'})
        self.assertEqual(200, response.status_code)

    def test_change_cert_visibility_lack_parameter(self):
        """
        Verify response for request without parameter.
        """
        tochange_path = reverse('change_visibility_certificates', kwargs={'course_id': self.course.id})
        response = self.client.post(path=tochange_path)
        self.assertEqual(400, response.status_code)


class LearnerProfileCertificatesTestBase(UrlResetMixin, ModuleStoreTestCase):
    USERNAME = "test_user"
    PASSWORD = "password"
    OTHER_USERNAME = "other_user"
    OTHER_PASSWORD = "password"
    DOWNLOAD_URL = "http://www.example.com/certificate.pdf"

    def setUp(self):
        super(LearnerProfileCertificatesTestBase, self).setUp()
        self.user = UserFactory.create(username=self.USERNAME, password=self.PASSWORD)
        self.user.is_staff = False
        self.client.login(username=self.USERNAME, password=self.PASSWORD)
        self.other_user = UserFactory.create(username=self.OTHER_USERNAME, password=self.OTHER_PASSWORD)
        self.other_user.is_staff = False
        self.filename = 'test-image.gif'
        self.image_data = 'GIF87a-dummy'

        self.default_course_args = {
            'org': "org",
            'number': "cn1",
            'run': "run",
            'course_canonical_name': 'cname',
            'course_contents_provider': 'univ',
            'teacher_name': 'teacher',
            'course_span': 'span',
            'is_f2f_course': False,
            'short_description': 'short description!',
            'course_image': self.filename,
            'start': datetime(2015, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'end': datetime(2020, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'enrollment_start': datetime(2014, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'enrollment_end': datetime(2028, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'deadline_start': datetime(2029, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'terminate_start': datetime(2030, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'course_category': [],
            'course_card_path': 'course_card_path',
            'course_list_description': 'course_list_description',
        }

    def _create_course(self, update_course_args):
        course_args = copy(self.default_course_args)
        course_args.update(update_course_args)
        course = CourseFactory.create(**course_args)
        loc = StaticContent.compute_location(course.location.course_key, self.filename)
        content = StaticContent(loc, self.filename, 'image/gif', StringIO(self.image_data))
        contentstore().save(content)
        course.save()
        return course

    def _create_certificate(self, user, course, status="downloadable"):
        """Simulate that the user has a generated certificate. """
        CourseEnrollmentFactory.create(user=user, course_id=course.id)
        return GeneratedCertificateFactory(
            user=user,
            course_id=course.id,
            download_url=self.DOWNLOAD_URL,
            status=status,
            grade=0.98,
        )


@ddt.ddt
class LearnerProfileCertificatesTest(LearnerProfileCertificatesTestBase):
    """ Tests for certificates on student profile. """

    TEST_BUCKET_NAME = 'testbucket'

    def setUp(self):
        super(LearnerProfileCertificatesTest, self).setUp()

    @mock_s3
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        PDFGEN_BASE_BUCKET_NAME=TEST_BUCKET_NAME
    )
    @patch('student_profile.views._is_certificate_visible_to_public')
    @patch('student_profile.views.get_user_preferences')
    @patch('student_profile.views.handle_file_from_s3')
    @ddt.data(
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    )
    @ddt.unpack
    def test_certificate_own_profile(self, is_profile_public, is_cert_public,
                                     mock_handle_file_from_s3,
                                     mock_get_user_preferences,
                                     mock_is_visible_to_public):
        """Verify if certificate is shown on learner's own profile page"""
        mock_get_user_preferences.side_effect = [
            {'account_privacy': 'all_users'} if is_profile_public else {'account_privacy': 'private'}
        ]
        mock_is_visible_to_public.side_effect = [
            True if is_cert_public else False
        ]

        course = self._create_course({
            'course_category': ['gacco'],
        })

        conn = boto.connect_s3()
        f = Key(conn.create_bucket(self.TEST_BUCKET_NAME))
        f.key = 'thumbnail-{}.jpg'.format(course.id)
        mock_handle_file_from_s3.return_value = f

        self._create_certificate(self.user, course)

        request = RequestFactory().get('/url')
        request.user = self.user

        context = learner_profile_context(request, self.USERNAME, self.user.is_staff)

        self.assertIn(self.TEST_BUCKET_NAME, context['data']['cert_infos'][0]['image_url'])
        self.assertIn('thumbnail-', context['data']['cert_infos'][0]['image_url'])
        self.assertIn('.jpg', context['data']['cert_infos'][0]['image_url'])
        self.assertEqual(course.display_name, context['data']['cert_infos'][0]['course_name'])

    @mock_s3
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        PDFGEN_BASE_BUCKET_NAME=TEST_BUCKET_NAME
    )
    @patch('student_profile.views._is_certificate_visible_to_public')
    @patch('student_profile.views.get_user_preferences')
    @patch('student_profile.views.handle_file_from_s3')
    @ddt.data(
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    )
    @ddt.unpack
    def test_certificate_other_profile(self, is_profile_public, is_cert_public,
                                       mock_handle_file_from_s3,
                                       mock_get_user_preferences,
                                       mock_is_visible_to_public):
        """Verify if certificate is shown on other learner's profile page"""
        mock_get_user_preferences.side_effect = [
            {'account_privacy': 'all_users'} if is_profile_public else {'account_privacy': 'private'}
        ]
        mock_is_visible_to_public.side_effect = [
            True if is_cert_public else False
        ]

        course = self._create_course({
            'course_category': ['gacco'],
        })

        conn = boto.connect_s3()
        f = Key(conn.create_bucket(self.TEST_BUCKET_NAME))
        f.key = 'thumbnail-{}.jpg'.format(course.id)
        mock_handle_file_from_s3.return_value = f

        self._create_certificate(self.other_user, course)

        request = RequestFactory().get('/url')
        request.user = self.user

        context = learner_profile_context(request, self.OTHER_USERNAME, self.other_user.is_staff)

        if is_profile_public and is_cert_public:
            self.assertIn(self.TEST_BUCKET_NAME, context['data']['cert_infos'][0]['image_url'])
            self.assertIn('thumbnail-', context['data']['cert_infos'][0]['image_url'])
            self.assertIn('.jpg', context['data']['cert_infos'][0]['image_url'])
            self.assertEqual(course.display_name, context['data']['cert_infos'][0]['course_name'])
            self.assertNotIn('download_url', context['data']['cert_infos'][0])
            self.assertNotIn('is_visible_to_public', context['data']['cert_infos'][0])
        else:
            self.assertTrue(len(context['data']['cert_infos']) == 0)

    def test_no_certificate(self):
        """Verify the context data when no certificates exist"""
        request = RequestFactory().get('/url')
        request.user = self.user

        context = learner_profile_context(request, self.USERNAME, self.user.is_staff)

        self.assertTrue(len(context['data']['cert_infos']) == 0)

    def test_certificate_not_downloadable(self):
        """Verify the context data when certificate's status is not downloadable"""
        course = self._create_course({
            'course_category': ['gacco'],
        })
        self._create_certificate(self.user, course, "generating")

        request = RequestFactory().get('/url')
        request.user = self.user

        context = learner_profile_context(request, self.USERNAME, self.user.is_staff)

        self.assertTrue(len(context['data']['cert_infos']) == 0)

    @mock_s3
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        PDFGEN_BASE_BUCKET_NAME=TEST_BUCKET_NAME
    )
    @patch('student_profile.views._is_certificate_visible_to_public')
    @patch('student_profile.views.get_user_preferences')
    @ddt.data(
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    )
    @ddt.unpack
    def test_certificate_hidden_course(self, is_profile_public, is_cert_public,
                                       mock_get_user_preferences,
                                       mock_is_visible_to_public):
        """Verify if certificate is not shown for hidden course"""
        mock_get_user_preferences.side_effect = [
            {'account_privacy': 'all_users'} if is_profile_public else {'account_privacy': 'private'}
        ]
        mock_is_visible_to_public.side_effect = [
            True if is_cert_public else False
        ]

        course1 = self._create_course({
            'number': 'cn1',
            'course_category': [],
        })
        self._create_certificate(self.user, course1)

        course2 = self._create_course({
            'number': 'cn2',
            'course_category': ['test'],
        })
        self._create_certificate(self.user, course2)

        request = RequestFactory().get('/url')
        request.user = self.user

        context = learner_profile_context(request, self.USERNAME, self.user.is_staff)

        self.assertTrue(len(context['data']['cert_infos']) == 0)

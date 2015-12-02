"""
These are tests for user certificate view
"""
import json
import unittest

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import Client

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from student.tests.factories import UserFactory, CourseEnrollmentFactory
from certificates.tests.factories import GeneratedCertificateFactory  # pylint: disable=import-error

# pylint: disable=no-member


@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class UserCertificateTest(ModuleStoreTestCase):
    """test suite for user certificate view"""

    DOWNLOAD_URL = "http://www.example.com/certificate.pdf"

    def setUp(self):
        super(UserCertificateTest, self).setUp()

        self.non_staff = UserFactory.create(
            username='non_staff',
        )
        self.admin = UserFactory.create(
            username='admin',
            is_staff=True,
        )

        # create clients
        self.non_staff_client = Client()
        self.admin_client = Client()

        for user, client in [
            (self.non_staff, self.non_staff_client),
            (self.admin, self.admin_client),
        ]:
            client.login(username=user.username, password='test')

        self.course = CourseFactory()

        self.passed_user = UserFactory.create(username='passed_user', password='test')
        self._create_certificate(
            self.passed_user, self.course.id, 'honor', 'passed_username', self.DOWNLOAD_URL, 'downloadable', 1.0)

        self.notpassing_user = UserFactory.create(username='notpassing_user', password='test')
        self._create_certificate(
            self.notpassing_user, self.course.id, 'honor', 'notpassing_username', '', 'notpassing', 0)


    def test_show_downloadable_certificate(self):
        response = self.admin_client.post(reverse('show_certificate_info_ajax'), {
            'username': self.passed_user.username,
            'course_id': unicode(self.course.id),
        })
        reparsed = json.loads(response.content)
        self.assertEqual(
            reparsed,
            {
                u'username': self.passed_user.username,
                u'email': self.passed_user.email,
                u'name': u'passed_username',
                u'status': u'downloadable',
                u'grade': u'1.0',
                u'download_url': self.DOWNLOAD_URL,
                u'message': u"Successfully retrieved {}'s certificate info.".format(self.passed_user.username),
            }
        )

    def test_show_notpassing_certificate(self):
        response = self.admin_client.post(reverse('show_certificate_info_ajax'), {
            'username': self.notpassing_user.username,
            'course_id': unicode(self.course.id),
        })
        reparsed = json.loads(response.content)
        self.assertEqual(
            reparsed,
            {
                u'username': self.notpassing_user.username,
                u'email': self.notpassing_user.email,
                u'name': u'notpassing_username',
                u'status': u'notpassing',
                u'grade': u'0',
                u'download_url': '',
                u'message': u"Successfully retrieved {}'s certificate info.".format(self.notpassing_user.username),
            }
        )

    def test_show_certificate_with_invalid_username(self):
        response = self.admin_client.post(reverse('show_certificate_info_ajax'), {
            'username': '',
            'course_id': unicode(self.course.id),
        })
        self.assertEqual(response.status_code, 400)
        reparsed = json.loads(response.content)
        self.assertEqual(
            reparsed['message'],
            u"Please enter a username"
        )

    def test_show_certificate_with_invalid_course_id(self):
        response = self.admin_client.post(reverse('show_certificate_info_ajax'), {
            'username': self.passed_user.username,
            'course_id': '',
        })
        self.assertEqual(response.status_code, 400)
        reparsed = json.loads(response.content)
        self.assertEqual(
            reparsed['message'],
            u"Please enter a course_id"
        )

    def test_show_certificate_with_non_existent_username(self):
        non_existent_username = 'non_existent_username'
        response = self.admin_client.post(reverse('show_certificate_info_ajax'), {
            'username': non_existent_username,
            'course_id': unicode(self.course.id),
        })
        self.assertEqual(response.status_code, 400)
        reparsed = json.loads(response.content)
        self.assertEqual(
            reparsed['message'],
            u"User with username {} does not exist".format(non_existent_username)
        )

    def test_show_certificate_with_non_existent_course_id(self):
        non_existent_course_id = 'non_existent_course_id'
        response = self.admin_client.post(reverse('show_certificate_info_ajax'), {
            'username': self.passed_user.username,
            'course_id': non_existent_course_id,
        })
        self.assertEqual(response.status_code, 400)
        reparsed = json.loads(response.content)
        self.assertEqual(
            reparsed['message'],
            u"Course ID is invalid."
        )

    def test_non_staff_cant_access_manage_view(self):
        response = self.non_staff_client.get(reverse('manage_user_certificate'))
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cant_show_certificate_info(self):
        response = self.non_staff_client.post(reverse('show_certificate_info_ajax'), {
            'username': self.passed_user.username,
            'course_id': unicode(self.course.id),
        })
        self.assertEqual(response.status_code, 404)

    def _create_certificate(self, user, course_id, enrollment_mode, name, download_url, status, grade):
        """Simulate that the user has a generated certificate. """
        CourseEnrollmentFactory.create(user=user, course_id=course_id, mode=enrollment_mode)
        GeneratedCertificateFactory(
            user=user,
            course_id=course_id,
            mode=enrollment_mode,
            name=name,
            download_url=download_url,
            status=status,
            grade=grade,
        )
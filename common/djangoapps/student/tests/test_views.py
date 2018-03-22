"""
Test the student dashboard view.
"""
from datetime import datetime, timedelta
import ddt
import unittest
from mock import patch
from pyquery import PyQuery as pq
import pytz

from django.core.urlresolvers import reverse
from django.conf import settings
from django.test import TestCase

from certificates.models import CertificateStatuses
from certificates.tests.factories import GeneratedCertificateFactory
from course_modes.tests.factories import CourseModeFactory
from student.tests.factories import UserFactory, CourseEnrollmentFactory
from student.models import CourseEnrollment
from student.helpers import DISABLE_UNENROLL_CERT_STATES
from student.views import cert_info
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory

from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase


@ddt.ddt
@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class TestStudentDashboardUnenrollments(ModuleStoreTestCase):
    """
    Test to ensure that the student dashboard does not show the unenroll button for users with certificates.
    """
    USERNAME = "Bob"
    EMAIL = "bob@example.com"
    PASSWORD = "edx"
    UNENROLL_ELEMENT_ID = "#actions-item-unenroll-0"

    def setUp(self):
        """ Create a course and user, then log in. """
        super(TestStudentDashboardUnenrollments, self).setUp()
        self.course = CourseFactory.create(
            certificates_display_behavior='end'
        )
        self.user = UserFactory.create(username=self.USERNAME, email=self.EMAIL, password=self.PASSWORD)
        CourseEnrollmentFactory(course_id=self.course.id, user=self.user)
        self.cert_status = None
        self.client.login(username=self.USERNAME, password=self.PASSWORD)

    def mock_cert(self, _user, _course_overview, _course_mode):
        """ Return a preset certificate status. """
        if self.cert_status is not None:
            return {
                'status': self.cert_status,
                'can_unenroll': self.cert_status not in DISABLE_UNENROLL_CERT_STATES
            }
        else:
            return {}

    @ddt.data(
        ('notpassing', True, 0),
        ('notpassing', False, 1),
        ('restricted', True, 0),
        ('restricted', False, 1),
        ('processing', True, 0),
        ('processing', False, 1),
        (None, True, 0),
        (None, False, 1),
        ('generating', True, 0),
        ('generating', False, 0),
        ('ready', True, 0),
        ('ready', False, 0),
    )
    @ddt.unpack
    def test_unenroll_available(self, cert_status, is_global_course, unenroll_action_count):
        """ Assert that the unenroll action is shown or not based on the cert status."""
        if is_global_course:
            CourseGlobalSettingFactory.create(course_id=self.course.id)

        self.cert_status = cert_status

        with patch('student.views.cert_info', side_effect=self.mock_cert):
            response = self.client.get(reverse('dashboard'))

            self.assertEqual(pq(response.content)(self.UNENROLL_ELEMENT_ID).length, unenroll_action_count)

    @ddt.data(
        (None, None, 1),
        (None, 'honor', 1),
        (None, 'audit', 1),
        (None, 'verified', 1),
        (None, 'credit', 1),
        (None, 'professional', 0),
        (None, 'no-id-professional', 0),
    )
    @ddt.unpack
    def test_unenroll_available_with_course_mode(self, cert_status, mode_slug, unenroll_action_count):
        """ Assert that the unenroll action is shown or not based on the course mode."""
        if mode_slug:
            CourseModeFactory.create(course_id=self.course.id, mode_slug=mode_slug)

        self.cert_status = cert_status

        with patch('student.views.cert_info', side_effect=self.mock_cert):
            response = self.client.get(reverse('dashboard'))

            self.assertEqual(pq(response.content)(self.UNENROLL_ELEMENT_ID).length, unenroll_action_count)

    @ddt.data(
        ('notpassing', 200),
        ('restricted', 200),
        ('processing', 200),
        (None, 200),
        ('generating', 400),
        ('ready', 400),
    )
    @ddt.unpack
    @patch.object(CourseEnrollment, 'unenroll')
    def test_unenroll_request(self, cert_status, status_code, course_enrollment):
        """ Assert that the unenroll method is called or not based on the cert status"""
        self.cert_status = cert_status

        with patch('student.views.cert_info', side_effect=self.mock_cert):
            response = self.client.post(
                reverse('change_enrollment'),
                {'enrollment_action': 'unenroll', 'course_id': self.course.id}
            )

            self.assertEqual(response.status_code, status_code)
            if status_code == 200:
                course_enrollment.assert_called_with(self.user, self.course.id)
            else:
                course_enrollment.assert_not_called()

    def test_no_cert_status(self):
        """ Assert that the dashboard loads when cert_status is None."""
        with patch('student.views.cert_info', return_value=None):
            response = self.client.get(reverse('dashboard'))

            self.assertEqual(response.status_code, 200)

    def test_cant_unenroll_status(self):
        """ Assert that the dashboard loads when cert_status does not allow for unenrollment"""
        with patch('certificates.models.certificate_status_for_student', return_value={'status': 'ready'}):
            response = self.client.get(reverse('dashboard'))

            self.assertEqual(response.status_code, 200)


TODAY = datetime.now(pytz.UTC)
YESTERDAY = TODAY - timedelta(days=1)


@ddt.ddt
@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class TestCertInfo(ModuleStoreTestCase):

    @ddt.data(
        ('early_with_info', None, CertificateStatuses.deleted, None),
        ('early_with_info', None, CertificateStatuses.deleting, None),
        ('early_with_info', None, CertificateStatuses.downloadable, 'ready'),
        ('early_with_info', None, CertificateStatuses.error, None),
        ('early_with_info', None, CertificateStatuses.generating, None),
        ('early_with_info', None, CertificateStatuses.notpassing, 'notpassing'),
        ('early_with_info', None, CertificateStatuses.regenerating, None),
        ('early_with_info', None, CertificateStatuses.restricted, 'restricted'),
        ('early_with_info', None, CertificateStatuses.unavailable, None),
        ('early_with_info', None, CertificateStatuses.auditing, None),
        ('early_with_info', None, CertificateStatuses.audit_passing, None),
        ('early_with_info', None, CertificateStatuses.audit_notpassing, None),
        ('early_no_info', None, CertificateStatuses.deleted, None),
        ('early_no_info', None, CertificateStatuses.deleting, None),
        ('early_no_info', None, CertificateStatuses.downloadable, 'ready'),
        ('early_no_info', None, CertificateStatuses.error, None),
        ('early_no_info', None, CertificateStatuses.generating, None),
        ('early_no_info', None, CertificateStatuses.notpassing, None),
        ('early_no_info', None, CertificateStatuses.regenerating, None),
        ('early_no_info', None, CertificateStatuses.restricted, 'restricted'),
        ('early_no_info', None, CertificateStatuses.unavailable, None),
        ('early_no_info', None, CertificateStatuses.auditing, None),
        ('early_no_info', None, CertificateStatuses.audit_passing, None),
        ('early_no_info', None, CertificateStatuses.audit_notpassing, None),
        ('end', None, CertificateStatuses.deleted, None),
        ('end', None, CertificateStatuses.deleting, None),
        ('end', None, CertificateStatuses.downloadable, None),
        ('end', None, CertificateStatuses.error, None),
        ('end', None, CertificateStatuses.generating, None),
        ('end', None, CertificateStatuses.notpassing, None),
        ('end', None, CertificateStatuses.regenerating, None),
        ('end', None, CertificateStatuses.restricted, None),
        ('end', None, CertificateStatuses.unavailable, None),
        ('end', None, CertificateStatuses.auditing, None),
        ('end', None, CertificateStatuses.audit_passing, None),
        ('end', None, CertificateStatuses.audit_notpassing, None),
        ('early_with_info', YESTERDAY, CertificateStatuses.deleted, None),
        ('early_with_info', YESTERDAY, CertificateStatuses.deleting, None),
        ('early_with_info', YESTERDAY, CertificateStatuses.downloadable, 'ready'),
        ('early_with_info', YESTERDAY, CertificateStatuses.error, None),
        ('early_with_info', YESTERDAY, CertificateStatuses.generating, None),
        ('early_with_info', YESTERDAY, CertificateStatuses.notpassing, 'notpassing'),
        ('early_with_info', YESTERDAY, CertificateStatuses.regenerating, None),
        ('early_with_info', YESTERDAY, CertificateStatuses.restricted, 'restricted'),
        ('early_with_info', YESTERDAY, CertificateStatuses.unavailable, None),
        ('early_with_info', YESTERDAY, CertificateStatuses.auditing, None),
        ('early_with_info', YESTERDAY, CertificateStatuses.audit_passing, None),
        ('early_with_info', YESTERDAY, CertificateStatuses.audit_notpassing, None),
        ('early_no_info', YESTERDAY, CertificateStatuses.deleted, None),
        ('early_no_info', YESTERDAY, CertificateStatuses.deleting, None),
        ('early_no_info', YESTERDAY, CertificateStatuses.downloadable, 'ready'),
        ('early_no_info', YESTERDAY, CertificateStatuses.error, None),
        ('early_no_info', YESTERDAY, CertificateStatuses.generating, None),
        ('early_no_info', YESTERDAY, CertificateStatuses.notpassing, None),
        ('early_no_info', YESTERDAY, CertificateStatuses.regenerating, None),
        ('early_no_info', YESTERDAY, CertificateStatuses.restricted, 'restricted'),
        ('early_no_info', YESTERDAY, CertificateStatuses.unavailable, None),
        ('early_no_info', YESTERDAY, CertificateStatuses.auditing, None),
        ('early_no_info', YESTERDAY, CertificateStatuses.audit_passing, None),
        ('early_no_info', YESTERDAY, CertificateStatuses.audit_notpassing, None),
        ('end', YESTERDAY, CertificateStatuses.deleted, 'processing'),
        ('end', YESTERDAY, CertificateStatuses.deleting, 'processing'),
        ('end', YESTERDAY, CertificateStatuses.downloadable, 'ready'),
        ('end', YESTERDAY, CertificateStatuses.error, 'processing'),
        ('end', YESTERDAY, CertificateStatuses.generating, 'generating'),
        ('end', YESTERDAY, CertificateStatuses.notpassing, 'notpassing'),
        ('end', YESTERDAY, CertificateStatuses.regenerating, 'generating'),
        ('end', YESTERDAY, CertificateStatuses.restricted, 'restricted'),
        ('end', YESTERDAY, CertificateStatuses.unavailable, 'processing'),
        ('end', YESTERDAY, CertificateStatuses.auditing, 'auditing'),
        ('end', YESTERDAY, CertificateStatuses.audit_passing, 'auditing'),
        ('end', YESTERDAY, CertificateStatuses.audit_notpassing, 'auditing'),
    )
    @ddt.unpack
    def test_certificates_display_behavior(self, certificates_display_behavior, course_end, status, cert_info_status):
        user = UserFactory.create()
        course = CourseFactory.create(end=course_end, certificates_display_behavior=certificates_display_behavior)
        GeneratedCertificateFactory.create(
            user=user,
            course_id=course.id,
            status=status,
            mode='honor',
            download_url='http://test_certificate_url',
            grade='1.0',
        )

        status_dict = cert_info(user, CourseOverview.get_from_id(course.id), None)
        if cert_info_status:
            self.assertEqual(cert_info_status, status_dict['status']);
        else:
            self.assertEqual({}, status_dict);


@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class TestBizStudentDashboardUnenrollments(BizContractTestBase):
    """
    Test to unenroll course of biz.
    """
    @patch.object(CourseEnrollment, 'unenroll')
    def test_unenroll_available(self, course_enrollment):
        self.setup_user()
        CourseEnrollmentFactory(course_id=self.course_spoc7.id, user=self.user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(pq(response.content)("#actions-item-unenroll-0").length, 0)

        response = self.client.post(
            reverse('change_enrollment'),
            {'enrollment_action': 'unenroll', 'course_id': self.course_spoc7.id}
        )
        course_enrollment.assert_not_called()


@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class TestNoticeUnactivated(TestCase):
    """
    Test to notice_unactivated.
    """
    USERNAME = 'foo'
    PASSWORD = 'bar'

    def test_user_is_active(self):
        # Create a user account
        self.user = UserFactory.create(
            username=self.USERNAME,
            password=self.PASSWORD,
            is_active=True,
        )
        self.client.login(username=self.USERNAME, password=self.PASSWORD)
        response = self.client.get(reverse('notice_unactivated'))
        self.assertRedirects(response, '/dashboard', status_code=302, target_status_code=200)

    def test_user_is_not_active(self):
        # Create a user account
        self.user = UserFactory.create(
            username=self.USERNAME,
            password=self.PASSWORD,
            is_active=False,
        )
        self.client.login(username=self.USERNAME, password=self.PASSWORD)
        response = self.client.get(reverse('notice_unactivated'))
        self.assertRedirects(response, '/login?unactivated=true', status_code=302, target_status_code=200)


@ddt.ddt
@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class TestOrderGlobalCourse(ModuleStoreTestCase):

    def setUp(self):
        super(TestOrderGlobalCourse, self).setUp()

        user = UserFactory.create()

        course = CourseFactory.create()
        self.course_enrollment = CourseEnrollmentFactory.create(course_id=course.id, user=user)
        self.course_id = str(course.id)

        global_course = CourseFactory.create()
        CourseGlobalSettingFactory.create(course_id=global_course.id)
        self.global_course_enrollment = CourseEnrollmentFactory.create(course_id=global_course.id, user=user)
        self.global_course_id = str(global_course.id)

        self.client.login(username=user.username, password='test')

    @ddt.data(
        (YESTERDAY, TODAY),
        (TODAY, YESTERDAY),
    )
    @ddt.unpack
    def test_order(self, course_enrollment_created, global_course_enrollment_created):
        # mod created of course_enrollment
        self.course_enrollment.created = course_enrollment_created
        self.course_enrollment.save()

        # mod created of global_course_enrollment
        self.global_course_enrollment.created = global_course_enrollment_created
        self.global_course_enrollment.save()

        response = self.client.get(reverse('dashboard'))

        self.assertIn(self.course_id, response.content)
        self.assertIn(self.global_course_id, response.content)

        self.assertTrue(response.content.find(self.course_id) < response.content.find(self.global_course_id))

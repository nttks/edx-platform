"""Tests for the pdfgen API. """
from datetime import datetime
from mock import patch

from django.test import RequestFactory

from certificates import api as certs_api
from certificates.models import CertificateGenerationConfiguration, CertificateStatuses, GeneratedCertificate
from certificates.tests.factories import GeneratedCertificateFactory
from config_models.models import cache
from openedx.core.djangoapps.ga_self_paced import api as self_paced_api
from openedx.core.djangoapps.ga_task.api import AlreadyRunningError
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin
from pdfgen import api as pdfgen_api
from student.tests.factories import CourseEnrollmentFactory, UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


class GenerateUserCertificateTest(ModuleStoreTestCase, TaskTestMixin):
    def setUp(self):
        super(GenerateUserCertificateTest, self).setUp()

        # Enable the certificate generation feature
        cache.clear()
        CertificateGenerationConfiguration.objects.create(enabled=True)

        self.user = UserFactory.create()
        self.course = self._create_course()
        self.request = RequestFactory().request()

        # Setup mock
        patcher_is_course_closed = patch.object(self_paced_api, 'is_course_closed')
        self.mock_is_course_closed = patcher_is_course_closed.start()
        self.mock_is_course_closed.return_value = False
        self.addCleanup(patcher_is_course_closed.stop)

        patcher_submit_task = patch('pdfgen.api.submit_task')
        self.mock_submit_task = patcher_submit_task.start()
        self.addCleanup(patcher_submit_task.stop)

    def _create_course(self, is_self_paced=True, **options):
        course = CourseFactory.create(
            self_paced=is_self_paced,
            start=datetime(2013, 9, 16, 7, 17, 28),
            grade_cutoffs={'Pass': 0.5},
            **options
        )
        # Enable certificate generation for this course
        certs_api.set_cert_generation_enabled(course.id, is_self_paced)

        CourseEnrollmentFactory(user=self.user, course_id=course.id)
        return course

    def _create_task(self, course, student):
        task_input = {
            'course_id': unicode(course.id),
            'student_ids': [student.id],
        }
        return self._create_input_entry(task_input=task_input)

    def _create_cert(self, status):
        return GeneratedCertificateFactory.create(
            user=self.user,
            course_id=self.course.id,
            status=status,
            download_url='http://www.example.com/cert.pdf' if status == CertificateStatuses.downloadable else '',
            mode='honor',
        )

    def _get_cert(self, course, student):
        try:
            return GeneratedCertificate.objects.get(course_id=course.id, user=student)
        except GeneratedCertificate.DoesNotExist:
            return None

    def test_successful(self):
        task = self._create_task(self.course, self.user)
        self.mock_submit_task.return_value = task

        self.assertEqual(
            pdfgen_api.generate_user_certificate(self.request, self.user, self.course),
            {
                'success': True,
                'message': "Certificate self-generation task(task_id={task_id}) has been started.".format(
                    task_id=task.id),
            }
        )

    def test_check_error_course_is_not_self_paced(self):
        not_self_paced_course = self._create_course(is_self_paced=False)

        self.assertEqual(
            pdfgen_api.generate_user_certificate(self.request, self.user, not_self_paced_course),
            {
                'success': False,
                'message': "Couldn't submit a certificate self-generation task because the course is not self-paced.",
            }
        )
        cert = self._get_cert(not_self_paced_course, self.user)
        self.assertEqual(cert.course_id, not_self_paced_course.id)
        self.assertEqual(cert.user, self.user)
        self.assertEqual(cert.status, CertificateStatuses.error)
        self.assertEqual(cert.error_reason, "This course is not self-paced.")

    def test_check_error_enroll_has_expired(self):
        self.mock_is_course_closed.return_value = True

        self.assertEqual(
            pdfgen_api.generate_user_certificate(self.request, self.user, self.course),
            {
                'success': False,
                'message': "Couldn't submit a certificate self-generation task because student's enrollment has already expired.",
            }
        )
        cert = self._get_cert(self.course, self.user)
        self.assertEqual(cert.course_id, self.course.id)
        self.assertEqual(cert.user, self.user)
        self.assertEqual(cert.status, CertificateStatuses.error)
        self.assertEqual(cert.error_reason, "Student's enrollment has already expired")

    def test_check_error_cert_has_already_created(self):
        before_cert = self._create_cert(CertificateStatuses.generating)

        self.assertEqual(
            pdfgen_api.generate_user_certificate(self.request, self.user, self.course),
            {
                'success': False,
                'message': "Couldn't submit a certificate self-generation task because certificate status has already created."
            }
        )
        cert = self._get_cert(self.course, self.user)
        self.assertEqual(cert.course_id, before_cert.course_id)
        self.assertEqual(cert.user, before_cert.user)
        self.assertEqual(cert.status, before_cert.status)
        self.assertEqual(cert.error_reason, before_cert.error_reason)

    def test_already_running_error(self):
        self.mock_submit_task.side_effect = AlreadyRunningError()

        self.assertEqual(
            pdfgen_api.generate_user_certificate(self.request, self.user, self.course),
            {
                'success': False,
                'message': "Task is already running.",
            }
        )

    def test_unexpected_error(self):
        ex = Exception('a' * 1000)
        self.mock_submit_task.side_effect = ex

        self.assertEqual(
            pdfgen_api.generate_user_certificate(self.request, self.user, self.course),
            {
                'success': False,
                'message': "An unexpected error occurred.",
            }
        )
        cert = self._get_cert(self.course, self.user)
        self.assertEqual(cert.course_id, self.course.id)
        self.assertEqual(cert.user, self.user)
        self.assertEqual(cert.status, CertificateStatuses.error)
        self.assertEqual(cert.error_reason, str(ex)[:512])

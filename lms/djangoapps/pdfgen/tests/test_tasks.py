"""Tests for task"""
from datetime import datetime
import json
from mock import patch

from certificates import api as certs_api
from certificates.models import CertificateGenerationConfiguration, CertificateStatuses, GeneratedCertificate
from certificates.tests.factories import GeneratedCertificateFactory
from config_models.models import cache
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin
from student.tests.factories import CourseEnrollmentFactory, UserFactory
from ..tasks import self_generate_certificate
from ..views import PDFBaseNotFound
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


class SelfGenerateCertificateTest(ModuleStoreTestCase, TaskTestMixin):

    def setUp(self):
        super(SelfGenerateCertificateTest, self).setUp()

        # Enable the certificate generation feature
        cache.clear()
        CertificateGenerationConfiguration.objects.create(enabled=True)

        self.user = UserFactory.create()
        self.course = self._create_course()

        # Setup mock
        patcher_grade = patch('pdfgen.certificate.grades.grade')
        self.mock_grade = patcher_grade.start()
        self.mock_grade.return_value = {
            'grade': 'Pass',
            'percent': 1,
        }
        self.addCleanup(patcher_grade.stop)

        patcher_create_cert_pdf = patch('pdfgen.certificate.create_cert_pdf')
        self.mock_create_cert_pdf = patcher_create_cert_pdf.start()
        self.mock_create_cert_pdf.return_value = json.dumps({'download_url': 'http://www.example.com/cert.pdf'})
        self.addCleanup(patcher_create_cert_pdf.stop)

        patcher_log = patch('pdfgen.tasks_helper.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

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

    def _get_cert_status(self, course, student):
        try:
            cert = GeneratedCertificate.objects.get(course_id=course.id, user=student)
            return cert.status
        except GeneratedCertificate.DoesNotExist:
            return None

    def _create_input_entry(self, course=None, student=None):
        task_input = {
            'course_id': unicode(course.id),
            'student_ids': [student.id],
        }
        return TaskTestMixin._create_input_entry(self, task_input=task_input)

    def test_successful(self):
        entry = self._create_input_entry(course=self.course, student=self.user)
        self._test_run_with_task(self_generate_certificate, 'self_generate_certificate', 1, 0, 0, 1, 1, entry)

        self.mock_log.info.assert_called_once()
        self.assertEqual(self._get_cert_status(self.course, self.user), CertificateStatuses.downloadable)

    def test_error_status_is_not_downloadable(self):
        self.mock_create_cert_pdf.return_value = json.dumps({'error': True})

        entry = self._create_input_entry(course=self.course, student=self.user)
        self._test_run_with_task(self_generate_certificate, 'self_generate_certificate', 0, 0, 1, 1, 1, entry)

        self.mock_log.error.assert_called_once()
        self.assertEqual(self._get_cert_status(self.course, self.user), CertificateStatuses.error)

    def test_error_with_unexpected_error(self):
        self.mock_create_cert_pdf.side_effect = PDFBaseNotFound('pdf is not exists')

        entry = self._create_input_entry(course=self.course, student=self.user)
        self._test_run_with_task(self_generate_certificate, 'self_generate_certificate', 0, 0, 1, 1, 1, entry)

        self.mock_log.exception.assert_called_once()
        self.assertEqual(self._get_cert_status(self.course, self.user), CertificateStatuses.error)

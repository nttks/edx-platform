from django.test import TestCase
from mock import MagicMock, patch, ANY
from django.contrib.auth.models import User
from student.tests.factories import UserFactory
from pdfgen.tests.factories import GeneratedCertificateFactory
from pdfgen.certificate import CertificatePDF, CertPDFException
import json

"""
class GenerateCertCommandTestCase(ModuleStoreTestCase):
from django.core.management.base import CommandError
from pdfgen.tests.factories import CertificateWhitelistFactory
from certificates.models import CertificateStatuses
from django.test.client import RequestFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from courseware.tests.modulestore_config import TEST_DATA_MIXED_MODULESTORE
from django.conf import settings
from django.test.utils import override_settings
@override_settings(MODULESTORE=TEST_DATA_MIXED_MODULESTORE)
from xmodule.modulestore.tests.factories import CourseFactory
"""


class CertificatePDF_create_TestCase(TestCase):
    """"""
    def setUp(self):
        self.user = "testusername"
        self.course_id = "org/num/run"
        self.debug = False
        self.noop = False
        self.student = UserFactory.create()
        self.course_name = "testcoursename"
        self.cert = GeneratedCertificateFactory.build(status="downloadable")
        self.grade = {"grade": "Pass", "percent": 1}
        self.invalid_grade = {"grade": None, "percent": 1}

        """
        patcher0 = patch('pdfgen.views.logging')
        self.log_mock = patcher0.start()
        self.addCleanup(patcher0.stop)
        """

    @patch('pdfgen.certificate.CertificatePDF._create_cert_pdf')
    @patch('pdfgen.certificate.grades.grade')
    @patch('pdfgen.certificate.GeneratedCertificate.objects.get_or_create',
        return_value=(GeneratedCertificateFactory.create(
            status="downloadable"), True))
    @patch('pdfgen.certificate.CertificatePDF._create_request')
    @patch('pdfgen.certificate.courses.get_course_by_id')
    @patch('pdfgen.certificate.CertificatePDF._get_students',
        return_value=[UserFactory.create()])
    def test_create(self, students_mock, course_mock, request_mock,
            gencert_mock, grade_mock, create_cert_mock):
        cert = CertificatePDF(self.user, self.course_id, self.debug,
            self.noop)
        cert.create()

        students_mock.assert_called_once_with()
        course_mock.assert_called_once_with(self.course_id)
        request_mock.assert_called_once_with()
        gencert_mock.assert_called_once_with(
            user=ANY, course_id=self.course_id)
        grade_mock.assert_called_once_with(ANY, ANY, ANY)
        create_cert_mock.assert_called_once_with(ANY, ANY, ANY, ANY)

    @patch('pdfgen.certificate.CertificatePDF._get_students',
        return_value=[UserFactory.create()])
    def test_create_not_ended(self, students_mock):
        mock = MagicMock()
        mock.has_ended = lambda: False
        with patch('pdfgen.certificate.courses.get_course_by_id',
            return_value=mock) as get_course_mock:
            with self.assertRaises(CertPDFException):
                cert = CertificatePDF(
                    self.user, self.course_id, self.debug, self.noop)
                cert.create()

        students_mock.assert_called_once_with()
        get_course_mock.assert_called_once_with(self.course_id)

    @patch('pdfgen.certificate.create_cert_pdf',
        return_value=json.dumps({"download_url": "http://s3/test.pdf"}))
    @patch('pdfgen.certificate.CertificatePDF._make_hashkey')
    @patch('pdfgen.certificate.UserProfile.objects.get')
    def test_create_cert_pdf(self, profile_mock, hash_mock, create_cert_mock):
        mock = MagicMock()
        mock.exists = lambda: True
        with patch('pdfgen.certificate.CertificateWhitelist.objects.filter',
            return_value=mock) as whitelist_mock:
            cert = CertificatePDF(
                self.user, self.course_id, self.debug, self.noop)
            cert._create_cert_pdf(
                self.student, self.course_name, self.cert, self.grade)

        profile_mock.assert_called_once_with(user=self.student)
        whitelist_mock.assert_called_once_with(user=self.student,
            course_id=self.course_id, whitelist=True)
        hash_mock.assert_called_once_with(ANY)
        create_cert_mock.assert_called_once_with(self.student.username,
            self.course_id, self.cert.name, self.course_name,
            self.grade['percent'], ANY)

    @patch('pdfgen.certificate.create_cert_pdf',
        return_value=json.dumps({"download_url": ""}))
    @patch('pdfgen.certificate.CertificatePDF._make_hashkey')
    @patch('pdfgen.certificate.UserProfile.objects.get')
    def test_create_cert_pdf_no_download_url(self, profile_mock, hash_mock,
        create_cert_mock):

        mock = MagicMock()
        mock.exists = lambda: True
        with patch('pdfgen.certificate.CertificateWhitelist.objects.filter',
            return_value=mock) as whitelist_mock:
            cert = CertificatePDF(
                self.user, self.course_id, self.debug, self.noop)
            cert._create_cert_pdf(
                self.student, self.course_name, self.cert, self.grade)

        profile_mock.assert_called_once_with(user=self.student)
        whitelist_mock.assert_called_once_with(user=self.student,
            course_id=self.course_id, whitelist=True)
        hash_mock.assert_called_once_with(ANY)
        create_cert_mock.assert_called_once_with(self.student.username,
            self.course_id, self.cert.name, self.course_name,
            self.grade['percent'], ANY)

    @patch('pdfgen.certificate.CertificatePDF._make_hashkey')
    @patch('pdfgen.certificate.UserProfile.objects.get')
    def test_create_cert_pdf_noop(self, profile_mock, hash_mock):
        mock = MagicMock()
        mock.exists = lambda: True
        with patch('pdfgen.certificate.CertificateWhitelist.objects.filter',
            return_value=mock) as whitelist_mock:
            cert = CertificatePDF(self.user, self.course_id, self.debug, True)
            cert._create_cert_pdf(
                self.student, self.course_name, self.cert, self.grade)

        profile_mock.assert_called_once_with(user=self.student)
        whitelist_mock.assert_called_once_with(user=self.student,
            course_id=self.course_id, whitelist=True)
        hash_mock.assert_called_once_with(ANY)

    @patch('pdfgen.certificate.UserProfile.objects.get')
    def test_create_cert_pdf_not_whitelist(self, profile_mock):
        mock = MagicMock()
        mock.exists = lambda: False
        with patch('pdfgen.certificate.CertificateWhitelist.objects.filter',
            return_value=mock) as whitelist_mock:
            cert = CertificatePDF(
                self.user, self.course_id, self.debug, self.noop)
            cert._create_cert_pdf(
                self.student, self.course_name, self.cert, self.invalid_grade)

        profile_mock.assert_called_once_with(user=self.student)
        whitelist_mock.assert_called_once_with(user=self.student,
            course_id=self.course_id, whitelist=True)

    @patch('pdfgen.certificate.UserProfile.objects.get')
    def test_create_cert_pdf_not_whitelist_noop(self, profile_mock):
        mock = MagicMock()
        mock.exists = lambda: False
        with patch('pdfgen.certificate.CertificateWhitelist.objects.filter',
            return_value=mock) as whitelist_mock:
            cert = CertificatePDF(self.user, self.course_id, self.debug, True)
            cert._create_cert_pdf(
                self.student, self.course_name, self.cert, self.invalid_grade)

        profile_mock.assert_called_once_with(user=self.student)
        whitelist_mock.assert_called_once_with(user=self.student,
            course_id=self.course_id, whitelist=True)

    @patch('pdfgen.certificate.UserProfile.objects.get')
    def test_create_cert_pdf_allow_certificate_false(self, profile_mock):
        mock = MagicMock()
        mock.exists = lambda: True
        with patch('pdfgen.certificate.CertificateWhitelist.objects.filter',
            return_value=mock) as whitelist_mock:

            mock2 = MagicMock()
            mock2.exists = lambda: False
            with patch('pdfgen.certificate.UserProfile.objects.filter',
                mock) as profile_mock2:
                cert = CertificatePDF(
                    self.user, self.course_id, self.debug, self.noop)
                cert._create_cert_pdf(
                    self.student, self.course_name, self.cert, self.grade)

        profile_mock.assert_called_once_with(user=self.student)
        whitelist_mock.assert_called_once_with(user=self.student,
            course_id=self.course_id, whitelist=True)
        profile_mock2.assert_called_once_with(
            allow_certificate=False, user=self.student)

    @patch('pdfgen.certificate.UserProfile.objects.get')
    def test_create_cert_pdf_allow_certificate_false_noop(self, profile_mock):
        mock = MagicMock()
        mock.exists = lambda: True
        with patch('pdfgen.certificate.CertificateWhitelist.objects.filter',
            return_value=mock) as whitelist_mock:

            mock2 = MagicMock()
            mock2.exists = lambda: False
            with patch('pdfgen.certificate.UserProfile.objects.filter',
                mock) as profile_mock2:
                cert = CertificatePDF(
                    self.user, self.course_id, self.debug, True)
                cert._create_cert_pdf(
                    self.student, self.course_name, self.cert, self.grade)

        profile_mock.assert_called_once_with(user=self.student)
        whitelist_mock.assert_called_once_with(user=self.student,
            course_id=self.course_id, whitelist=True)
        profile_mock2.assert_called_once_with(
            allow_certificate=False, user=self.student)


class CertificatePDF_delete_TestCase(TestCase):

    def setUp(self):
        self.user = "testusername"
        self.course_id = "org/num/run"
        self.debug = False
        self.noop = False

    @patch('pdfgen.certificate.delete_cert_pdf',
        return_value=json.dumps({"error": None}))
    @patch('pdfgen.certificate.GeneratedCertificate.objects.get_or_create',
        return_value=(GeneratedCertificateFactory.create(
        status="downloadable"), True))
    @patch('pdfgen.certificate.CertificatePDF._get_students',
        return_value=[UserFactory.create()])
    def test_delete(self, students_mock, generate_mock, delete_mock):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert.delete()

        students_mock.assert_called_once_with()
        generate_mock.assert_called_once_with(
            user=ANY, course_id=self.course_id)
        delete_mock.assert_called_once_with(ANY, self.course_id)

    @patch('pdfgen.certificate.GeneratedCertificate.objects.get_or_create',
        return_value=(GeneratedCertificateFactory.create(
        status="downloadable"), True))
    @patch('pdfgen.certificate.CertificatePDF._get_students',
        return_value=[UserFactory.create()])
    def test_delete_noop(self, students_mock, generate_mock):
        cert = CertificatePDF(self.user, self.course_id, self.debug, True)
        cert.delete()

        students_mock.assert_called_once_with()
        generate_mock.assert_called_once_with(
            user=ANY, course_id=self.course_id)

    @patch('pdfgen.certificate.delete_cert_pdf',
        return_value=json.dumps({"error": "error"}))
    @patch('pdfgen.certificate.GeneratedCertificate.objects.get_or_create',
        return_value=(GeneratedCertificateFactory.create(
        status="downloadable"), True))
    @patch('pdfgen.certificate.CertificatePDF._get_students',
        return_value=[UserFactory.create()])
    def test_delete_error(self, students_mock, generate_mock, delete_mock):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert.delete()

        students_mock.assert_called_once_with()
        generate_mock.assert_called_once_with(
            user=ANY, course_id=self.course_id)
        delete_mock.assert_called_once_with(ANY, self.course_id)

    @patch('pdfgen.certificate.GeneratedCertificate.objects.get_or_create',
        return_value=(GeneratedCertificateFactory.create(
        status="unavailable"), True))
    @patch('pdfgen.certificate.CertificatePDF._get_students',
        return_value=[UserFactory.create()])
    def test_delete_not_much(self, students_mock, generate_mock):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert.delete()

        students_mock.assert_called_once_with()
        generate_mock.assert_called_once_with(
            user=ANY, course_id=self.course_id)


class CertificatePDF_report_TestCase(TestCase):

    def setUp(self):
        self.user = "testusername"
        self.course_id = "org/num/run"
        self.debug = False
        self.noop = False

        self.summary = [{"display_name": "section_name",
            "sections": [{"display_name": "subsec_name", "format": "HW",
            "section_total": [10, 10], "scores": [
            (10, 10, True, "unit_name")]}]}]
        self.grade = {"grade": "Pass", "percent": 1}
        self.invalid_grade = {"grade": None, "percent": 1}
        self.total = {'users': 0, 'pass': 0, 'notpass': 0}
        self.total_with_grade = {
            'users': 0, 'pass': 0, 'notpass': 0, 'Pass': 0}
        self.total_items = {
            'users': 3, 'pass': 2, 'notpass': 1, 'A': 1, 'B': 1}

    @patch('pdfgen.certificate.CertificatePDF._report_total')
    @patch('pdfgen.certificate.CertificatePDF._add_total')
    @patch('pdfgen.certificate.CertificatePDF._report_summary')
    @patch('pdfgen.certificate.grades.progress_summary')
    @patch('pdfgen.certificate.grades.grade')
    @patch('pdfgen.certificate.GeneratedCertificate.objects.get_or_create',
        return_value=(GeneratedCertificateFactory.create(
        status="downloadable"), True))
    @patch('pdfgen.certificate.CertificatePDF._create_request')
    @patch('pdfgen.certificate.courses.get_course_by_id')
    @patch('pdfgen.certificate.CertificatePDF._get_students',
        return_value=[UserFactory.create()])
    def test_report(self, students_mock, course_mock, request_mock,
        generate_mock, grade_mock, progress_mock, summary_mock,
         total_mock, report_mock):

        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert.report()

        students_mock.assert_called_once_with()
        course_mock.assert_called_once_with(self.course_id)
        request_mock.assert_called_once_with()
        generate_mock.assert_called_once_with(
            user=ANY, course_id=self.course_id)
        grade_mock.assert_called_once_with(ANY, ANY, ANY)
        progress_mock.assert_called_once_with(ANY, ANY, ANY)
        summary_mock.assert_called_once_with(ANY)
        total_mock.assert_called_once_with(ANY, ANY, ANY)
        report_mock.assert_called_once_with(ANY)

    @patch('pdfgen.certificate.CertificatePDF._dprint')
    def test_report_summary(self, dprint_mock):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert._report_summary(self.summary)

        dprint_mock.assert_called_once_with(ANY)

    def test_add_total(self):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert._add_total(self.user, self.grade, self.total)
        self.assertEqual(
            self.total, {'Pass': 1, 'notpass': 0, 'users': 0, 'pass': 1})

    def test_add_total_with_grade(self):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert._add_total(self.user, self.grade, self.total_with_grade)
        self.assertEqual(self.total_with_grade,
            {'Pass': 1, 'notpass': 0, 'users': 0, 'pass': 1})

    def test_add_total_invalid_grade(self):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert._add_total(self.user, self.invalid_grade, self.total_with_grade)
        self.assertEqual(self.total_with_grade,
            {'Pass': 0, 'notpass': 1, 'users': 0, 'pass': 0})

    def test_report_total(self):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert._report_total(self.total_items)
        self.assertEqual(self.total_items, {'A': 1, 'B': 1})

    def test_report_total_none(self):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert._report_total(self.total)
        self.assertEqual(self.total, {})


class CertificatePDF_other_TestCase(TestCase):

    def setUp(self):
        self.user = "testusername"
        self.course_id = "org/num/run"
        self.debug = False
        self.noop = False
        self.mail = "testusername@example.com"
        self.seed = "seed"

    def test_dprint(self):
        cert = CertificatePDF(self.user, self.course_id, True, self.noop)
        cert._dprint(msg="message")

    def test_dprint_newline_false(self):
        cert = CertificatePDF(self.user, self.course_id, True, self.noop)
        cert._dprint(msg="message", newline=False)

    def test_create_request(self):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert._create_request()

    @patch('pdfgen.certificate.User.objects.filter',
        return_value=[UserFactory.create()])
    def test_get_students_all(self, user_moc):
        cert = CertificatePDF(None, self.course_id, self.debug, self.noop)
        cert._get_students()
        user_moc.assert_called_once_with(
            courseenrollment__course_id__exact=self.course_id)

    @patch('pdfgen.certificate.User.objects.get',
        return_value=[UserFactory.create()])
    def test_get_students_by_username(self, user_moc):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        cert._get_students()
        user_moc.assert_called_once_with(username=self.user,
            courseenrollment__course_id=self.course_id)

    @patch('pdfgen.certificate.User.objects.get',
        return_value=[UserFactory.create()])
    def test_get_students_by_email(self, user_moc):
        cert = CertificatePDF(self.mail, self.course_id, self.debug, self.noop)
        cert._get_students()
        user_moc.assert_called_once_with(email=self.mail,
            courseenrollment__course_id=self.course_id)

    @patch('pdfgen.certificate.User.objects.filter', return_value=[])
    def test_get_students_dose_not_exists(self, user_moc):
        with self.assertRaises(CertPDFException):
            cert = CertificatePDF(None, self.course_id, self.debug, self.noop)
            cert._get_students()

    @patch('pdfgen.certificate.User.objects.get',
        side_effect=User.DoesNotExist)
    def test_get_students_by_username_DoseNotExist(self, user_moc):
        with self.assertRaises(CertPDFException):
            cert = CertificatePDF(
                self.user, self.course_id, self.debug, self.noop)
            cert._get_students()
        user_moc.assert_called_once_with(username=self.user,
            courseenrollment__course_id=self.course_id)

    @patch('pdfgen.certificate.User.objects.get',
        side_effect=User.DoesNotExist)
    def test_get_students_by_email_DoseNotExist(self, user_moc):
        with self.assertRaises(CertPDFException):
            cert = CertificatePDF(
                self.mail, self.course_id, self.debug, self.noop)
            cert._get_students()
        user_moc.assert_called_once_with(email=self.mail,
            courseenrollment__course_id=self.course_id)

    def test_make_hashkey(self):
        cert = CertificatePDF(self.user, self.course_id, self.debug, self.noop)
        result = cert._make_hashkey(self.seed)
        self.assertRegexpMatches(result, '[a-zA-Z0-9]{32}')

    def test_make_hashkey_no_args(self):
        with self.assertRaises(TypeError):
            cert = CertificatePDF(
                self.user, self.course_id, self.debug, self.noop)
            cert._make_hashkey()

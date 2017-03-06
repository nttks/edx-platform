import ddt
import hashlib
import json
from mock import Mock, patch, ANY, create_autospec, mock_open
import StringIO
import tempfile

from boto.exception import BotoClientError, BotoServerError, S3ResponseError
from boto.s3.connection import S3Connection, Location
from boto.s3.key import Key
from django.test import TestCase
from django.conf import settings
from django.test.utils import override_settings

from opaque_keys.edx.locator import CourseLocator
from pdfgen.views import (
    CertificateBase, CertificateHonor, CertStoreBase,
    CertS3Store, create_cert_pdf, delete_cert_pdf, CertPDF,
    PDFBaseNotFound, PDFBaseIsNotPDF, PDFBaseIsNotImage,
    InvalidSettings
)


class CertificationBaseTestCase(TestCase):

    def setUp(self):
        self.cert = CertificateBase()

    def test_create(self):
        with self.assertRaises(NotImplementedError):
            self.cert.create()

    def test_get(self):
        with self.assertRaises(NotImplementedError):
            self.cert.get()

    def test_delete(self):
        with self.assertRaises(NotImplementedError):
            self.cert.delete()

    def test_verify(self):
        with self.assertRaises(NotImplementedError):
            self.cert.verify()


@override_settings(PDFGEN_CERT_AUTHOR="author", PDFGEN_CERT_TITLE="title")
class CertificateHonorTestCase(TestCase):

    def setUp(self):
        self.username = "username"
        self.display_name = "display_name"
        self.course_id = CourseLocator.from_string("org/num/run")
        self.course_name = "course_name"
        self.file_prefix = "prefix-"
        self.grade = 1

        md5 = hashlib.md5()
        self.key = md5.hexdigest()

        patcher0 = patch('pdfgen.views.logging')
        self.log_mock = patcher0.start()
        self.addCleanup(patcher0.stop)

        patcher1 = patch('pdfgen.views.CertS3Store')
        self.s3_mock = patcher1.start()
        self.addCleanup(patcher1.stop)

    def teerDown(self):
        pass

    @patch('pdfgen.views.json')
    @patch('pdfgen.views.os')
    @patch('pdfgen.views.CertPDF')
    @patch('pdfgen.views.mkstemp', return_value=[Mock(), "/tmp/test"])
    def test_create(self, mkst_mock, cert_mock, os_mock, json_mock):
        m = mock_open()
        with patch('pdfgen.views.open', m, create=True):
            cert = CertificateHonor(
                self.username, self.course_id, self.key, self.display_name,
                self.course_name, self.grade, self.file_prefix)
            cert.create()

        mkst_mock.assert_called_once_with(suffix="-certificate.pdf")
        cert_mock.assert_called_once_with(
            ANY, self.display_name, self.course_id,
            self.course_name, self.file_prefix)
        os_mock.close.assert_called_once_with(ANY)
        os_mock.remove.assert_called_once_with(ANY)
        self.s3_mock().save.assert_called_once_with(
            "_".join([self.username, self.key[:5]]), self.course_id, ANY)

    @patch('pdfgen.views.json')
    @patch('pdfgen.views.os')
    @patch('pdfgen.views.CertPDF')
    @patch('pdfgen.views.mkstemp', side_effect=OSError())
    def test_create_raise_oserror(self, mkst_mock, cert_mock, os_mock, json_mock):
        m = mock_open()
        with patch('pdfgen.views.open', m, create=True):
            cert = CertificateHonor(
                self.username, self.course_id, self.key, self.display_name,
                self.course_name, self.grade, self.file_prefix)
            cert.create()

        msg = "OS Error: ()"
        json_mock.dumps.assert_called_once_with({"error": msg})

    @patch('pdfgen.views.json')
    def test_create_course_name_is_none(self, json_mock):
        cert = CertificateHonor(
            self.username, self.course_id, self.key, self.display_name,
            None, self.grade, self.file_prefix)
        response = cert.create()
        msg = "course_name is required."
        json_mock.dumps.assert_called_once_with({"error": msg})

    @patch('pdfgen.views.json')
    def test_create_grade_is_none(self, json_mock):
        cert = CertificateHonor(
            self.username, self.course_id, self.key, self.display_name,
            self.course_name, None, self.file_prefix)
        response = cert.create()
        msg = "grade is required."
        json_mock.dumps.assert_called_once_with({"error": msg})

    def test_delete(self):
        cert = CertificateHonor(
            self.username, self.course_id, self.key, self.display_name,
            self.course_name, self.grade, self.file_prefix)
        cert.delete()

        self.s3_mock().delete.assert_called_once_with(
            "_".join([self.username, self.key[:5]]), self.course_id)


@ddt.ddt
@override_settings(PDFGEN_CERT_AUTHOR="author", PDFGEN_CERT_TITLE="title")
class CertPDFTestCase(TestCase):

    def setUp(self):
        self.fp = StringIO.StringIO()
        self.username = "testusername"
        self.course_id = CourseLocator.from_string("org/num/run")
        self.course_name = "testcoursename"
        self.file_prefix = "prefix-"

        patcher0 = patch('pdfgen.views.logging')
        self.log_mock = patcher0.start()
        self.addCleanup(patcher0.stop)

        self.base_pdf = tempfile.TemporaryFile()
        self.base_pdf.write(b'test\n')
        self.addCleanup(self.base_pdf.close)

    @patch('pdfgen.views.get_file_from_s3', return_value=None)
    @patch('pdfgen.views.CertPDF.create_based_on_pdf')
    @ddt.data(True, False)
    def test_create_pdf(self, has_prefix, pdf_mock, get_file_from_s3_mock):
        prefix = self.file_prefix if has_prefix else ''
        get_file_from_s3_mock.return_value = self.base_pdf
        certpdf = CertPDF(
            self.fp, self.username, self.course_id,
            self.course_name, prefix)
        certpdf.create_pdf()

        if has_prefix:
            get_file_from_s3_mock.assert_called_once_with('prefix-org-num-run.pdf')
        else:
            get_file_from_s3_mock.assert_called_once_with('org-num-run.pdf')
        pdf_mock.assert_called_once_with(self.base_pdf)

    @patch('pdfgen.views.get_file_from_s3', return_value=None)
    def test_create_pdf_base_pdf_not_found(self, get_file_from_s3_mock):
        with self.assertRaises(PDFBaseNotFound):
            certpdf = CertPDF(
                self.fp, self.username, self.course_id,
                self.course_name, self.file_prefix)
            certpdf.create_pdf()

    @patch('pdfgen.views.PdfFileWriter')
    @patch('pdfgen.views.PdfFileReader')
    @patch('pdfgen.views.canvas')
    def test_create_based_on_pdf(self, cavs_mock, reader_mock_class, writer_mock_class):
        writer_mock = Mock()
        writer_mock_class.return_value = writer_mock
        merge_reader_mock = Mock()
        base_reader_mock = Mock()
        reader_mock_class.side_effect = [merge_reader_mock, base_reader_mock]
        merge_page_mock = Mock()
        merge_reader_mock.getPage.return_value = merge_page_mock
        base_page_mock = Mock()
        base_reader_mock.getPage.return_value = base_page_mock

        certpdf = CertPDF(
            self.fp, self.username, self.course_id,
            self.course_name, self.file_prefix)
        certpdf.create_based_on_pdf(self.base_pdf)

        cavs_mock.Canvas.assert_called_once_with(
            ANY, bottomup=True, pageCompression=1, pagesize=ANY)
        self.assertEqual(reader_mock_class.call_count, 2)
        writer_mock_class.assert_called_once_with()
        merge_reader_mock.getPage.assert_called_once_with(0)
        base_reader_mock.getPage.assert_called_once_with(0)
        base_page_mock.mergePage.assert_called_once_with(merge_page_mock)
        writer_mock.addMetadata.assert_called_once_with({'/Title': 'title', '/Author': 'author', '/Subject': self.course_name})
        writer_mock.addPage.assert_called_once_with(base_page_mock)
        writer_mock.write.assert_called_once_with(self.fp)

    def test_create_based_on_pdf_not_file(self):
        with self.assertRaises(PDFBaseIsNotPDF):
            certpdf = CertPDF(
                self.fp, self.username, self.course_id,
                self.course_name, self.file_prefix)
            certpdf.create_based_on_pdf(self.base_pdf)


class CertStoreBaseTestCase(TestCase):

    def setUp(self):
        self.store = CertStoreBase()

    def test_save(self):
        with self.assertRaises(NotImplementedError):
            self.store.save()

    def test_get(self):
        with self.assertRaises(NotImplementedError):
            self.store.get()

    def test_get_url(self):
        with self.assertRaises(NotImplementedError):
            self.store.get_url()

    def test_get_all(self):
        with self.assertRaises(NotImplementedError):
            self.store.get_all()

    def test_delete(self):
        with self.assertRaises(NotImplementedError):
            self.store.delete()


@override_settings(
    PDFGEN_BUCKET_NAME="bucket", PDFGEN_ACCESS_KEY_ID="akey",
    PDFGEN_SECRET_ACCESS_KEY="skey")
class CertS3StoreSuccesses(TestCase):

    def setUp(self):
        self.username = "testusername"
        self.course_id = CourseLocator.from_string("org/num/run")
        self.filepath = "/file/is/not/exists"
        self.bucket_name = settings.PDFGEN_BUCKET_NAME

        patcher0 = patch('pdfgen.views.logging')
        self.log = patcher0.start()
        self.addCleanup(patcher0.stop)

        self.s3class = create_autospec(S3Connection)
        config = {'return_value': self.s3class}
        patcher1 = patch('pdfgen.views.CertS3Store._connect', **config)
        self.s3conn = patcher1.start()
        self.addCleanup(patcher1.stop)

        self.keymethod = create_autospec(Key.set_contents_from_filename)
        patcher2 = patch('pdfgen.views.Key')
        self.s3key = patcher2.start()
        self.s3key().set_contents_from_filename.return_value = self.keymethod
        self.s3key().generate_url.return_value = "http://example.com/"
        self.addCleanup(patcher2.stop)

    def test_save(self):
        s3 = CertS3Store()
        response_json = s3.save(self.username, self.course_id, self.filepath)
        self.assertEqual(
            response_json, json.dumps({"download_url": "http://example.com/"}))
        self.s3key().set_contents_from_filename.assert_called_once_with(self.filepath)
        self.s3key().generate_url.assert_called_once_with(
            expires_in=0, query_auth=False, force_http=True)

    def test_delete(self):
        s3 = CertS3Store()
        response_json = s3.delete(self.username, self.course_id)
        self.assertEqual(response_json, json.dumps({"error": None}))
        self.s3key().delete.assert_called_once_with()

    def test_delete_file_not_found(self):
        s3 = CertS3Store()
        self.s3key().exists.return_value = False

        response_json = s3.delete(self.username, self.course_id)
        self.assertEqual(response_json, json.dumps(
            {"error": "file does not exists.(org/num/run/testusername.pdf)"}))
        self.assertEqual(self.s3key().delete.call_count, 0)


@override_settings(
    PDFGEN_BUCKET_NAME="bucket", PDFGEN_ACCESS_KEY_ID="akey",
    PDFGEN_SECRET_ACCESS_KEY="skey")
class CertS3StoreErrors(TestCase):
    def setUp(self):
        self.username = "testusername"
        self.course_id = CourseLocator.from_string("org/num/run")
        self.filepath = "/file/is/not/exists"
        self.bucket_name = settings.PDFGEN_BUCKET_NAME
        self.location = Location.APNortheast

        patcher0 = patch('pdfgen.views.logging')
        self.log = patcher0.start()
        self.addCleanup(patcher0.stop)

    @patch.multiple(settings, PDFGEN_BUCKET_NAME=None)
    def test_init_settings_None(self):
        with self.assertRaises(InvalidSettings):
            s3 = CertS3Store()

    @patch('pdfgen.views.Key.generate_url', return_value="http://example.com/")
    @patch('pdfgen.views.connect_to_region')
    @patch('pdfgen.views.Key.set_contents_from_filename')
    def test_save_raise_S3ResponseError_with_404(self, moc1, moc2, moc3):
        s3conn = Mock()
        s3conn.get_bucket.side_effect = S3ResponseError(status=404, reason="reason")
        moc2.return_value = s3conn

        response_json = CertS3Store().save(
            self.username, self.course_id, self.filepath)
        self.assertEqual(response_json, json.dumps(
            {"download_url": "http://example.com/"}))
        s3conn.get_bucket.assert_called_once_with(self.bucket_name)
        moc1.assert_called_once_with(self.filepath)
        s3conn.create_bucket.assert_called_once_with(
            self.bucket_name, location=self.location)
        moc3.assert_called_once_with(
            expires_in=0, query_auth=False, force_http=True)

    @patch('pdfgen.views.connect_to_region')
    def test_save_raise_S3ResponseError(self, moc2):
        s3exception = S3ResponseError(status="status", reason="reason")
        s3conn = Mock()
        s3conn.get_bucket.side_effect = s3exception
        moc2.return_value = s3conn

        response_json = CertS3Store().save(
            self.username, self.course_id, self.filepath)
        self.assertEqual(response_json, json.dumps(
            {"error": "{}".format(s3exception)}))
        s3conn.get_bucket.assert_called_once_with(self.bucket_name)


@override_settings(
    PDFGEN_BUCKET_NAME="bucket", PDFGEN_ACCESS_KEY_ID="akey",
    PDFGEN_SECRET_ACCESS_KEY="skey")
class MethodTestCase(TestCase):

    def setUp(self):
        self.display_name = "testusername"
        self.username = "testusername"
        self.course_id = CourseLocator.from_string("org/num/run")
        self.course_name = "testcoursename"
        self.grade = 1
        self.key = hashlib.md5()
        self.file_prefix = "prefix-"
        self.result = {"download_url": "http://exapmle.com"}
        self.result2 = {"error": None}

        patcher0 = patch('pdfgen.views.logging')
        self.log = patcher0.start()
        self.addCleanup(patcher0.stop)

    def test_create_cert_pdf(self):
        with patch('pdfgen.views.CertificateHonor.create', spec=True,
                   return_value=self.result) as moc1:
            contents = create_cert_pdf(self.username, self.course_id, self.key,
                                       self.display_name, self.course_name,
                                       self.grade, self.file_prefix)

        self.assertEqual(contents, self.result)
        moc1.assert_called_once_with()

    def test_create_cert_pdf_raise_BotoServerError(self):
        botoexception = BotoServerError(status=500, reason="reason")
        with patch('pdfgen.views.CertificateHonor.create', spec=True,
                   side_effect=botoexception) as moc1:

            contents = create_cert_pdf(self.username, self.course_id, self.key,
                                       self.display_name, self.course_name,
                                       self.grade, self.file_prefix)

        self.assertEqual(
            contents, json.dumps({"error": "BotoServerError: 500 reason\n"}))
        moc1.assert_called_once_with()

    def test_create_cert_pdf_raise_BotoClientError(self):
        botoexception = BotoClientError(reason="reason")
        with patch('pdfgen.views.CertificateHonor.create', spec=True,
                   side_effect=botoexception) as moc1:

            contents = create_cert_pdf(self.username, self.course_id, self.key,
                                       self.display_name, self.course_name,
                                       self.grade, self.file_prefix)

        self.assertEqual(
            contents, json.dumps({"error": "BotoClientError: reason"}))
        moc1.assert_called_once_with()

    def test_delete_pdf(self):
        with patch('pdfgen.views.CertificateHonor.delete', spec=True,
                   return_value=self.result2) as moc1:
            contents = delete_cert_pdf(self.username, self.course_id, self.key)

        self.assertEqual(contents, self.result2)
        moc1.assert_called_once_with()

    def test_delete_pdf_raise_BotoServerError(self):
        botoexception = BotoServerError(status=500, reason="reason")
        with patch('pdfgen.views.CertificateHonor.delete', spec=True,
                   side_effect=botoexception) as moc1:
            contents = delete_cert_pdf(self.username, self.course_id, self.key)

        self.assertEqual(
            contents, json.dumps({"error": "BotoServerError: 500 reason\n"}))
        moc1.assert_called_once_with()

    def test_delete_cert_pdf_raise_BotoClientError(self):
        botoexception = BotoClientError(reason="reason")
        with patch('pdfgen.views.CertificateHonor.delete', spec=True,
                   side_effect=botoexception) as moc1:
            contents = delete_cert_pdf(self.username, self.course_id, self.key)

        self.assertEqual(
            contents, json.dumps({"error": "BotoClientError: reason"}))
        moc1.assert_called_once_with()

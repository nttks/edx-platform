from django.test import TestCase
from django.conf import settings
from mock import patch, ANY, create_autospec, mock_open
from pdfgen.views import (CertificateBase, CertificateHonor, CertStoreBase,
     CertS3Store, create_cert_pdf, delete_cert_pdf, CertPDF,
     PDFBaseNotFound, PDFBaseIsNotPDF, PDFBaseIsNotImage)
from boto.s3.connection import Location
from boto.exception import BotoClientError, BotoServerError, S3ResponseError
from boto.s3.key import Key
import hashlib
import json
import StringIO
"""
from django.test.utils import override_settings
"""


# with
# patch.object('pdfgen.management.commands.create_certs.CertificatePDF',
# 'create') as createmock:

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


class CertificateHonorTestCase(TestCase):

    def setUp(self):
        self.username = "testusername"
        self.display_name = "testusername"
        self.course_id = "org/num/run"
        self.course_name = "testcoursename"
        self.grade = 1
        self.key = hashlib.md5()

        patcher0 = patch('pdfgen.views.logging')
        self.log_mock = patcher0.start()
        self.addCleanup(patcher0.stop)

        patcher1 = patch('pdfgen.views.CertS3Store')
        self.s3_mock = patcher1.start()
        self.addCleanup(patcher1.stop)

        """
        patcher2 = patch('pdfgen.views.CertPDF')
        self.certpdf_mock  = patcher2.start()
        self.addCleanup(patcher2.stop)
        """

    def teerDown(self):
        pass

    def test_init_invalid_args(self):
        with self.assertRaises(TypeError):
            cert = CertificateHonor()
            response = cert.create()

        with self.assertRaises(TypeError):
            cert = CertificateHonor(self.username)
            response = cert.create()

    @patch('os.remove')
    @patch('pdfgen.views.CertPDF')
    @patch('pdfgen.views.mkstemp', return_value="/tmp/test")
    def test_create_success(self, mkstemp_moc, cert_mock, remove_mock):
        m = mock_open()
        with patch('__main__.open', m, create=True):
            cert = CertificateHonor(self.display_name, self.course_id,
                self.username, self.course_name, self.grade, self.key)
            cert.create()

    def test_create_mkstemp_raise_oserror(self):
        with patch('pdfgen.views.mkstemp', side_effect=OSError):
            cert = CertificateHonor(self.display_name, self.course_id,
                self.username, self.course_name, self.grade, self.key)
            response = cert.create()
            msg = "OS Error: ()"
            self.assertEqual(response, json.dumps({"error": msg}))

    def test_create_create_pdf_raise_oserror(self):
        with patch('pdfgen.views.CertPDF.create_pdf', side_effect=OSError):
            cert = CertificateHonor(self.display_name, self.course_id,
                self.username, self.course_name, self.grade, self.key)
            response = cert.create()
            msg = "OS Error: ()"
            self.assertEqual(response, json.dumps({"error": msg}))

    def test_create_course_name_is_none(self):
        cert = CertificateHonor(self.username, self.course_id,
            self.display_name, None, self.grade, self.key)
        response = cert.create()
        msg = "course_name is required."
        self.assertEqual(response, json.dumps({"error": msg}))

    def test_create_grade_is_none(self):
        cert = CertificateHonor(self.username, self.course_id,
            self.display_name, self.course_name, None, self.key)
        response = cert.create()
        msg = "grade is required."
        self.assertEqual(response, json.dumps({"error": msg}))

    def test_delete(self):
        cert = CertificateHonor(self.username, self.course_id,
            self.display_name, self.course_name, self.grade, self.key)
        cert.delete()


class CertPDFTestCase(TestCase):

    def setUp(self):
        self.fp = StringIO.StringIO()
        self.username = "testusername"
        self.course_id = "org/num/run"
        self.course_name = "testcoursename"

        patcher0 = patch('pdfgen.views.logging')
        self.log_mock = patcher0.start()
        self.addCleanup(patcher0.stop)

    @patch('pdfgen.views.CertPDF.create_based_on_pdf')
    @patch.multiple(settings, PDFGEN_BASE_PDF_DIR="/tmp",
        PDFGEN_BASE_IMG_DIR="/tmp")
    def test_create_based_on_pdf(self, pdf_mock):
        certpdf = CertPDF(
            self.fp, self.username, self.course_id, self.course_name)
        certpdf.create_pdf()
        pdf_mock.assert_called_once_with("/tmp/org-num-run.pdf")

    @patch('pdfgen.views.CertPDF.create_based_on_image')
    @patch.multiple(settings, PDFGEN_BASE_PDF_DIR="not found",
        PDFGEN_BASE_IMG_DIR="/tmp")
    def test_create_based_on_image(self, img_mock):
        certpdf = CertPDF(
            self.fp, self.username, self.course_id, self.course_name)
        certpdf.create_pdf()
        img_mock.assert_called_once_with("/tmp/org-num-run.pdf")

    @patch.multiple(settings, PDFGEN_BASE_PDF_DIR="not found",
        PDFGEN_BASE_IMG_DIR="not found")
    def test_create_based_on_pdf_directory_not_found(self):
        with self.assertRaises(PDFBaseNotFound):
            certpdf = CertPDF(
                self.fp, self.username, self.course_id, self.course_name)
            certpdf.create_pdf()

    @patch('pdfgen.views.PdfFileWriter')
    @patch('pdfgen.views.PdfFileReader')
    @patch('__builtin__.file')
    @patch('pdfgen.views.os.path.isfile', return_value=True)
    @patch.multiple(settings, PDFGEN_BASE_PDF_DIR="/tmp")
    def test_create_based_on_pdf(self, isfile_mock, file_mock, reader_mock,
        writer_mock):

        certpdf = CertPDF(
            self.fp, self.username, self.course_id, self.course_name)
        certpdf.create_based_on_pdf(self.fp)
        isfile_mock.assert_called_once_with(self.fp)
        reader_mock.assert_called_with(ANY)
        writer_mock.assert_called_once_with()

    @patch('pdfgen.views.os.path.isfile', return_value=False)
    @patch.multiple(settings, PDFGEN_BASE_PDF_DIR="/tmp")
    def test_create_based_on_pdf_not_exists(self, isfile_mock):
        with self.assertRaises(PDFBaseNotFound):
            certpdf = CertPDF(
                self.fp, self.username, self.course_id, self.course_name)
            certpdf.create_based_on_pdf(self.fp)

    @patch('pdfgen.views.os.path.isfile', return_value=True)
    @patch.multiple(settings, PDFGEN_BASE_PDF_DIR="/tmp")
    def test_create_based_on_pdf_not_file(self, isfile_mock):
        with self.assertRaises(PDFBaseIsNotPDF):
            certpdf = CertPDF(
                self.fp, self.username, self.course_id, self.course_name)
            certpdf.create_based_on_pdf(self.fp)

    @patch('pdfgen.views.canvas.Canvas.drawImage')
    @patch('pdfgen.views.ImageReader')
    @patch('pdfgen.views.os.path.isfile', return_value=True)
    @patch.multiple(settings, PDFGEN_BASE_IMG_DIR="/tmp")
    def test_create_based_on_image(self, isfile_mock, reader_mock, draw_mock):
        certpdf = CertPDF(
            self.fp, self.username, self.course_id, self.course_name)
        certpdf.create_based_on_image(self.fp)
        isfile_mock.assert_called_once_with(self.fp)
        reader_mock.assert_called_once_with(self.fp)
        draw_mock.assert_called_once_with(ANY, 0, 0)

    @patch('pdfgen.views.os.path.isfile', return_value=False)
    @patch.multiple(settings, PDFGEN_BASE_IMG_DIR="/tmp")
    def test_create_based_on_image_not_exists(self, isfile_mock):
        with self.assertRaises(PDFBaseNotFound):
            certpdf = CertPDF(
                self.fp, self.username, self.course_id, self.course_name)
            certpdf.create_based_on_image(self.fp)

    @patch('pdfgen.views.os.path.isfile', return_value=True)
    @patch.multiple(settings, PDFGEN_BASE_IMG_DIR="/tmp")
    def test_create_based_on_image_isnot_image(self, isfile_mock):
        with self.assertRaises(PDFBaseIsNotImage):
            certpdf = CertPDF(
                self.fp, self.username, self.course_id, self.course_name)
            certpdf.create_based_on_image(self.fp)


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


class CertS3StoreSuccesses(TestCase):

    def setUp(self):
        self.username = "testusername"
        self.course_id = "org/num/run"
        self.filepath = "/file/is/not/exists"
        self.bucket_name = settings.PDFGEN_BUCKENT_NAME

        patcher0 = patch('pdfgen.views.logging')
        self.log = patcher0.start()
        self.addCleanup(patcher0.stop)

        """
        self.s3class = create_autospec(S3Connection)
        config = {'return_value': self.s3class}
        patcher1 = patch('pdfgen.views.CertS3Store._connect', **config)
        self.s3conn = patcher1.start()
        self.addCleanup(patcher1.stop)
        """

        self.keymethod = create_autospec(Key.set_contents_from_filename)
        config = {'return_value': self.keymethod}
        patcher2 = patch(
            'pdfgen.views.Key.set_contents_from_filename', **config)
        self.s3setcontents = patcher2.start()
        self.addCleanup(patcher2.stop)

        self.url = {"return_value": "http://example.com/"}
        patcher3 = patch('pdfgen.views.Key.generate_url', **self.url)
        self.s3generateurl = patcher3.start()
        self.addCleanup(patcher3.stop)

        patcher4 = patch('pdfgen.views.Key.delete')
        self.s3delete = patcher4.start()
        self.addCleanup(patcher4.stop)

    def test_save(self):
        s3 = CertS3Store()
        response_json = s3.save(self.username, self.course_id, self.filepath)
        self.assertEqual(
            response_json, json.dumps({"download_url": "http://example.com/"}))
        self.s3setcontents.assert_called_once_with(self.filepath)
        self.s3generateurl.assert_called_once_with(
            expires_in=0, query_auth=False, force_http=True)

    def test_delete_success(self):
        s3 = CertS3Store()
        response_json = s3.delete(self.username, self.course_id)
        self.assertEqual(response_json, json.dumps({"error": None}))
        self.s3delete.assert_called_once_with()


class CertS3StoreErrors(TestCase):

    def setUp(self):
        self.username = "testusername"
        self.course_id = "org/num/run"
        self.filepath = "/file/is/not/exists"
        self.bucket_name = settings.PDFGEN_BUCKENT_NAME
        self.location = Location.APNortheast

        patcher0 = patch('pdfgen.views.logging')
        self.log = patcher0.start()
        self.addCleanup(patcher0.stop)

    @patch('pdfgen.views.Key.generate_url', return_value="http://example.com/")
    @patch('pdfgen.views.S3Connection.create_bucket')
    @patch('pdfgen.views.Key.set_contents_from_filename')
    def test_save_raise_S3ResponseError_with_404(self, moc1, moc2, moc3):
        s3 = CertS3Store()
        s3exception = S3ResponseError(status=404, reason="reason")
        with patch('pdfgen.views.S3Connection.get_bucket',
            side_effect=s3exception) as bucket:

            response_json = s3.save(
                self.username, self.course_id, self.filepath)
            self.assertEqual(response_json, json.dumps(
                {"download_url": "http://example.com/"}))
            bucket.assert_called_once_with(self.bucket_name)
            moc1.assert_called_once_with(self.filepath)
            moc2.assert_called_once_with(
                self.bucket_name, location=self.location)
            moc3.assert_called_once_with(
                expires_in=0, query_auth=False, force_http=True)

    def test_save_raise_S3ResponseError(self):
        s3 = CertS3Store()
        s3exception = S3ResponseError(status="status", reason="reason")
        with patch('pdfgen.views.S3Connection.get_bucket',
            side_effect=s3exception) as bucket:

            response_json = s3.save(
                self.username, self.course_id, self.filepath)
            self.assertEqual(response_json, json.dumps(
                {"error": "{}".format(s3exception)}))
            bucket.assert_called_once_with(self.bucket_name)


class MethodTestCase(TestCase):

    def setUp(self):
        self.display_name = "testusername"
        self.username = "testusername"
        self.course_id = "org/num/run"
        self.course_name = "testcoursename"
        self.grade = 1
        self.key = hashlib.md5()
        self.result = {"download_url": "http://exapmle.com"}
        self.result2 = {"error": None}

        patcher0 = patch('pdfgen.views.logging')
        self.log = patcher0.start()
        self.addCleanup(patcher0.stop)

    def test_create_cert_pdf(self):
        with patch('pdfgen.views.CertificateHonor.create', spec=True,
            return_value=self.result) as moc1:
            contents = create_cert_pdf(self.username, self.display_name,
                self.course_id, self.course_name, self.grade, self.key)

        self.assertEqual(contents, self.result)
        moc1.assert_called_once_with()

    def test_create_cert_pdf_raise_BotoServerError(self):
        botoexception = BotoServerError(status=500, reason="reason")
        with patch('pdfgen.views.CertificateHonor.create', spec=True,
            side_effect=botoexception) as moc1:

            contents = create_cert_pdf(self.username, self.display_name,
                self.course_id, self.course_name, self.grade, self.key)

        self.assertEqual(
            contents, json.dumps({"error": "BotoServerError: 500 reason\n"}))
        moc1.assert_called_once_with()

    def test_create_cert_pdf_raise_BotoClientError(self):
        botoexception = BotoClientError(reason="reason")
        with patch('pdfgen.views.CertificateHonor.create', spec=True,
            side_effect=botoexception) as moc1:

            contents = create_cert_pdf(self.username, self.display_name,
                self.course_id, self.course_name, self.grade, self.key)

        self.assertEqual(
            contents, json.dumps({"error": "BotoClientError: reason"}))
        moc1.assert_called_once_with()

    def test_delete_pdf(self):
        with patch('pdfgen.views.CertificateHonor.delete', spec=True,
            return_value=self.result2) as moc1:
            contents = delete_cert_pdf(self.username, self.course_id,)

        self.assertEqual(contents, self.result2)
        moc1.assert_called_once_with()

    def test_delete_pdf_raise_BotoServerError(self):
        botoexception = BotoServerError(status=500, reason="reason")
        with patch('pdfgen.views.CertificateHonor.delete', spec=True,
            side_effect=botoexception) as moc1:
            contents = delete_cert_pdf(self.username, self.course_id,)

        self.assertEqual(
            contents, json.dumps({"error": "BotoServerError: 500 reason\n"}))
        moc1.assert_called_once_with()

    def test_delete_cert_pdf_raise_BotoClientError(self):
        botoexception = BotoClientError(reason="reason")
        with patch('pdfgen.views.CertificateHonor.delete', spec=True,
            side_effect=botoexception) as moc1:
            contents = delete_cert_pdf(self.username, self.course_id,)

        self.assertEqual(
            contents, json.dumps({"error": "BotoClientError: reason"}))
        moc1.assert_called_once_with()

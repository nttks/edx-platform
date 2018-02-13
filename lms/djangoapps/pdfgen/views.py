"""
pdfgen views
"""
from datetime import datetime
import json
import logging
import os
import StringIO
from tempfile import mkstemp

from boto.exception import BotoClientError, BotoServerError, S3ResponseError
from boto.s3 import connect_to_region
from boto.s3.connection import Location, OrdinaryCallingFormat
from boto.s3.key import Key
from django.conf import settings
from PyPDF2 import PdfFileWriter, PdfFileReader
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from pdfgen.utils import course_filename, get_file_from_s3

log = logging.getLogger("pdfgen")


class CertException(Exception):
    pass


class InvalidSettings(CertException):
    pass


class PDFBaseNotFound(CertException):
    pass


class PDFBaseIsNotPDF(CertException):
    pass


class PDFBaseIsNotImage(CertException):
    pass


class CertificateBase(object):
    """Certificate base class."""
    def create(self):
        """Create certificate."""
        raise NotImplementedError

    def get(self):
        """Get certificate."""
        raise NotImplementedError

    def delete(self):
        """Delete certificate."""
        raise NotImplementedError

    def verify(self):
        """Verify certificate."""
        raise NotImplementedError


class CertificateHonor(CertificateBase):
    """Certificate of Honor"""

    def __init__(self, username, course_id, key, display_name=None,
                 course_name=None, grade=None, file_prefix=""):

        self.username = username
        self.display_name = display_name
        self.course_id = course_id
        self.course_name = course_name
        self.grade = grade
        self.key = key
        self.file_prefix = file_prefix
        self.store = CertS3Store()
        """
        self.enroll_mode = "honor"
        self.is_staff = False
        """

    def create(self):
        """Create certificate."""
        if not self.course_name:
            msg = "course_name is required."
            log.error(msg)
            return json.dumps({"error": msg})

        if self.grade is None:
            msg = "grade is required."
            log.error(msg)
            return json.dumps({"error": msg})

        try:
            fd, path = mkstemp(suffix="-certificate.pdf")

            with open(path, 'wb') as fp:
                form = CertPDF(
                    fp, self.display_name, self.course_id,
                    self.course_name, self.file_prefix)
                form.create_pdf()

            response_json = self.store.save(
                "_".join([self.username, self.key[:5]]),
                self.course_id, path)

        except OSError, e:
            msg = "OS Error: ({})".format(e)
            return json.dumps({"error": msg})
        finally:
            try:
                os.close(fd)
                os.remove(path)
            except UnboundLocalError:
                pass

        return response_json

    def delete(self):
        """Delete certificate."""
        return self.store.delete("_".join([self.username, self.key[:5]]), self.course_id)


class CertPDF(object):
    def __init__(self, fp, username, course_id, course_name, file_prefix=""):
        self.fp = fp
        self.username = username
        self.course_id = course_id
        self.course_name = course_name
        self.author = settings.PDFGEN_CERT_AUTHOR
        self.title = settings.PDFGEN_CERT_TITLE
        self.prefix = file_prefix

        pdfmetrics.registerFont(
            TTFont(
                "Ubuntu-R",
                "/usr/share/fonts/truetype/ubuntu-font-family/Ubuntu-R.ttf"))
        pdfmetrics.registerFont(
            TTFont(
                "VL-Gothic-Regular",
                "/usr/share/fonts/truetype/vlgothic/VL-Gothic-Regular.ttf"))

    def create_pdf(self):
        """ crate pdf """
        base_pdf_name = course_filename(self.course_id) + '.pdf'
        if self.prefix:
            base_pdf_name = self.prefix + base_pdf_name

        base_pdf = get_file_from_s3(base_pdf_name)
        if base_pdf is None:
            msg = "{} is not exists.".format(base_pdf_name)
            log.error(msg)
            raise PDFBaseNotFound(msg)

        self.create_based_on_pdf(base_pdf)

    def create_based_on_pdf(self, base_pdf):
        """create pdf based on pdf"""
        fileobj = StringIO.StringIO()
        pdf = canvas.Canvas(
            fileobj, bottomup=True,
            pageCompression=1, pagesize=landscape(A4))

        pdf.setFont("VL-Gothic-Regular", 27)
        pdf.drawString(260, 450, self.username)
        now = datetime.now()
        pdf.setFont("Ubuntu-R", 15)
        pdf.drawRightString(750, 125, now.strftime('%B %d, %Y'))

        pdf.showPage()
        pdf.save()

        fileobj.seek(0)
        merge = PdfFileReader(fileobj)

        try:
            base = PdfFileReader(base_pdf)
            page = base.getPage(0)
            page.mergePage(merge.getPage(0))

            output = PdfFileWriter()
            output.addMetadata(
                {'/Title': self.title, '/Author': self.author,
                 '/Subject': u"{}".format(self.course_name)})

            output.addPage(page)
            output.write(self.fp)
        except (IOError, TypeError, AssertionError), e:
            log.error(e)
            raise PDFBaseIsNotPDF(e)


class CertStoreBase(object):
    """Certificate Store."""
    def save(self):
        """Save certificate."""
        raise NotImplementedError

    def get(self):
        """Get certificate."""
        raise NotImplementedError

    def get_url(self):
        """Get download url of the certificate"""
        raise NotImplementedError

    def get_all(self):
        """Get all certificates."""
        raise NotImplementedError

    def delete(self):
        """Delete certificate."""
        raise NotImplementedError


class CertS3Store(CertStoreBase):
    """S3 store."""
    def __init__(self):
        if None in (settings.PDFGEN_BUCKET_NAME,
                    settings.PDFGEN_ACCESS_KEY_ID,
                    settings.PDFGEN_SECRET_ACCESS_KEY):

            raise InvalidSettings(
                "PDFGEN_BUCKET_NAME, PDFGEN_ACCESS_KEY_ID or PDFGEN_SECRET_ACCESS_KEY is None.")

        self.bucket_name = settings.PDFGEN_BUCKET_NAME
        self.access_key = settings.PDFGEN_ACCESS_KEY_ID
        self.secret_key = settings.PDFGEN_SECRET_ACCESS_KEY
        self.location = Location.APNortheast
        self.conn = self._connect()

    def _connect(self):
        return connect_to_region(
            self.location,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            calling_format=OrdinaryCallingFormat(),
        )

    def save(self, username, course_id, filepath):
        """Save certificate."""
        try:
            bucket = self.conn.get_bucket(self.bucket_name)
        except S3ResponseError as e:
            if e.status == 404:
                bucket = self.conn.create_bucket(
                    self.bucket_name,
                    location=self.location)
                log.info("Cresate bucket(%s)", self.bucket_name)
            else:
                return json.dumps({"error": "{}".format(e)})

        try:
            s3key = Key(bucket)
            s3key.key = "{cid}/{name}.pdf".format(
                cid=course_id, name=username)

            # headers meta? encrypt_key true?
            s3key.set_contents_from_filename(filepath)
            url = s3key.generate_url(
                expires_in=0, query_auth=False, force_http=True)
        finally:
            s3key.close()

        return json.dumps({'download_url': url, })

    def delete(self, username, course_id):
        """Delete certificate."""
        try:
            bucket = self.conn.get_bucket(self.bucket_name)
            s3key = Key(bucket)
            s3key.key = "{cid}/{name}.pdf".format(
                cid=course_id, name=username)
            if s3key.exists():
                s3key.delete()
            else:
                return json.dumps({'error': "file does not exists.({})".format(
                    s3key.key)})
        finally:
            s3key.close()

        return json.dumps({'error': None})


def create_cert_pdf(username, course_id, key, display_name,
                    course_name, grade, file_prefix=""):
    """Create pdf of certificate."""
    try:
        cert = CertificateHonor(username, course_id, key, display_name,
                                course_name, grade, file_prefix)
        contents = cert.create()
    except BotoServerError as e:
        log.error("Cannot get bucket: BotoServerError = %s", e)
        contents = json.dumps({"error": "{}".format(e)})
    except BotoClientError as e:
        log.error("Cannot access S3: BotoClientError = %s", e)
        contents = json.dumps({"error": "{}".format(e)})

    return contents


def delete_cert_pdf(username, course_id, key):
    """Delete pdf of certificate."""
    try:
        cert = CertificateHonor(username, course_id, key)
        contents = cert.delete()
    except BotoServerError as e:
        log.error("Cannot get bucket: BotoServerError = %s", e)
        contents = json.dumps({"error": "{}".format(e)})
    except BotoClientError as e:
        log.error("Cannot access S3: BotoClientError = %s", e)
        contents = json.dumps({"error": "{}".format(e)})

    return contents

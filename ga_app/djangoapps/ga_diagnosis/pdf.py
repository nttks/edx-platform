"""
ga_diagnosis pdf views
"""
import io
import json
import logging
import os
import StringIO
from datetime import datetime
from tempfile import mkstemp

from boto.exception import BotoClientError, BotoServerError, S3ResponseError
from boto.s3 import connect_to_region
from boto.s3.connection import Location, OrdinaryCallingFormat
from boto.s3.key import Key
from django.conf import settings
from PyPDF2 import PdfFileWriter, PdfFileReader
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import DiagnosisInfo
from radar_chart import get_radar_chart
from pdfgen.utils import course_filename, get_file_from_s3
from pdfgen.views import CertS3Store as DiagnosisS3Store

log = logging.getLogger(__name__)


class DiagnosisException(Exception):
    pass


class InvalidSettings(DiagnosisException):
    pass


class PDFBaseNotFound(DiagnosisException):
    pass


class PDFBaseIsNotPDF(DiagnosisException):
    pass


class PDFBaseIsNotImage(DiagnosisException):
    pass


class Diagnosis(object):
    def __init__(self, diagnosis_info, key):
        self.username = diagnosis_info.user.username
        self.course_id = diagnosis_info.course_id
        self.key = key
        self.diagnosis_info = diagnosis_info
        self.store = DiagnosisS3Store()

    def create(self):
        """Create diagnosis report."""
        try:
            fd, path = mkstemp(suffix='-diagnosis.pdf')

            with open(path, 'wb') as fp:
                pdf = DiagnosisPDF(fp, self.diagnosis_info)
                pdf.create_pdf()

            response_json = self.store.save(
                '_'.join([self.username, self.key[:5]]),
                self.course_id, path)

        except OSError, e:
            msg = u'OS Error: ({})'.format(e)
            return json.dumps({'error': msg})
        finally:
            try:
                os.close(fd)
                os.remove(path)
            except UnboundLocalError:
                pass

        return response_json


class DiagnosisPDF(object):
    def __init__(self, fp, diagnosis_info):
        self.fp = fp
        self.username = diagnosis_info.user.username
        self.course_id = diagnosis_info.course_id
        self.chart_data = diagnosis_info.get_chart_data(is_pre_result=False)
        self.own_score = diagnosis_info.get_score()
        self.average_score = diagnosis_info.get_average(is_pre_result=False)
        self.author = settings.PDFGEN_CERT_AUTHOR
        self.title = settings.PDFGEN_CERT_TITLE

        pdfmetrics.registerFont(
            TTFont(
                'Ubuntu-R',
                '/usr/share/fonts/truetype/ubuntu-font-family/Ubuntu-R.ttf'))

    def create_pdf(self):
        """ crate pdf """
        base_pdf_name = course_filename(self.course_id) + '.pdf'
        base_pdf = get_file_from_s3(base_pdf_name)
        if base_pdf is None:
            msg = '{} is not exists.'.format(base_pdf_name)
            log.error(msg)
            raise PDFBaseNotFound(msg)

        self.create_based_on_pdf(base_pdf)

    def create_based_on_pdf(self, base_pdf):
        """create pdf based on pdf"""
        fileobj = StringIO.StringIO()
        pdf = canvas.Canvas(
            fileobj, bottomup=True,
            pageCompression=1, pagesize=portrait(A4))

        # Date
        pdf.setFont('Ubuntu-R', 14)
        now = datetime.now()
        pdf.drawRightString(539, 810.5, now.strftime('%Y/%m/%d'))

        # username
        pdf.setFont('Ubuntu-R', 16)
        pdf.drawString(30, 780, self.username)

        # params1
        pdf.setFont('Ubuntu-R', 24)
        y = 692
        for point_a, point_b in zip([v for _, v in self.own_score.iteritems()],
                                    [v for _, v in self.average_score.iteritems()]):
            pdf.drawRightString(478, y, str(point_a))
            pdf.drawRightString(565, y, str(point_b))
            y -= 50.5

        # radar chart
        chart = get_radar_chart(self.chart_data)
        im = ImageReader(io.BytesIO(chart))
        pdf.drawImage(im, 90, 85, width=420, height=350, mask='auto', preserveAspectRatio=True)

        # params2
        pdf.setFont('Ubuntu-R', 17)
        x1 = 156
        x2 = 251
        think_score = DiagnosisInfo.get_think(self.own_score)
        for think1, think2 in [[DiagnosisInfo.THINK_AD, DiagnosisInfo.THINK_BC],
                               [DiagnosisInfo.THINK_AB, DiagnosisInfo.THINK_CD]]:
            pdf.drawRightString(x1, 38, str(think_score[think1]))
            pdf.drawRightString(x2, 38, str(think_score[think2]))
            x1 += 296
            x2 += 296

        pdf.showPage()
        pdf.save()

        fileobj.seek(0)
        merge = PdfFileReader(fileobj)

        try:
            base = PdfFileReader(base_pdf)
            page = base.getPage(0)
            page.mergePage(merge.getPage(0))

            output = PdfFileWriter()

            output.addPage(page)
            output.write(self.fp)
        except (IOError, TypeError, AssertionError), e:
            log.error(e)
            raise PDFBaseIsNotPDF(e)


def create_pdf(diagnosis_info, key):
    """Create pdf of diagnosis."""
    try:
        diagnosis = Diagnosis(diagnosis_info, key)
        contents = diagnosis.create()
    except BotoServerError as e:
        log.error(u'Cannot get bucket: BotoServerError = {}'.format(e))
        contents = json.dumps({'error': '{}'.format(e)})
    except BotoClientError as e:
        log.error(u'Cannot access S3: BotoClientError = {}'.format(e))
        contents = json.dumps({'error': '{}'.format(e)})

    return contents

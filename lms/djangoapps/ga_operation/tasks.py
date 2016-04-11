# -*- coding: utf-8 -*-
import urllib
import logging
from smtplib import SMTPException

from django.core.mail import send_mail
from django.core.management import call_command
from django.conf import settings

from pdfgen.certificate import CertPDFException
from lms import CELERY_APP
from opaque_keys.edx.keys import CourseKey
from certificates.models import GeneratedCertificate
from ga_operation.utils import handle_downloaded_file_from_s3, delete_files

log = logging.getLogger(__name__)


@CELERY_APP.task
def create_certs_task(course_id, email, file_name_list, is_meeting=False):
    """create_certs_task main."""
    CreateCerts(course_id, email, file_name_list, is_meeting).run()


class CreateCerts(object):
    """Generate certificate class"""
    def __init__(self, course_id, email, file_name_list, is_meeting=False):
        super(CreateCerts, self).__init__()
        self.course_id = course_id
        self.email = email
        self.operation = "create"
        self.is_meeting = is_meeting
        self.file_name_list = file_name_list

    def run(self):
        err_msg = None
        try:
            handle_downloaded_file_from_s3(self.file_name_list, settings.GA_OPERATION_CERTIFICATE_BUCKET_NAME)
            if self.is_meeting:
                # normal : prefix='verified-', exclude=None
                # meeting: prefix='', exclude='../verified-course-v1:gacco+gaXXX+YYYY_MM.list'
                for prefix, exclude in zip(["verified-", ""], [None, settings.PDFGEN_BASE_PDF_DIR + "/verified-{}.list".format(self.course_id)]):
                    self._call_commands(prefix, exclude)
            else:
                call_command(self.get_command_name(),
                             self.operation, self.course_id,
                             username=False, debug=False, noop=False, prefix='', exclude=None)
        except CertPDFException as e:
            log.exception("Failure to generate the PDF files from create_certs command")
            err_msg = "{}".format(e)
        except Exception as e:
            log.exception('Caught the exception: ' + type(e).__name__)
            err_msg = "{}".format(e)
        finally:
            self._send_email(err_msg)
            delete_files(self.file_name_list)

    def _call_commands(self, prefix, exclude):
        try:
            call_command(self.get_command_name(),
                         self.operation, self.course_id,
                         username=False, debug=False, noop=False, prefix=prefix, exclude=exclude)
        except CertPDFException as e:
            # If you can continue the process when got error that not found certificate user.
            if "certificate does not exist." in "{}".format(e):
                log.info("{}".format(e))
                pass
            else:
                raise

    def _get_download_urls_text(self):
        result = ""
        for gc in GeneratedCertificate.objects.filter(course_id=CourseKey.from_string(self.course_id),
                                                      status="generating"):
            result += "\n" + urllib.unquote(gc.download_url)
        return result

    def _send_email(self, err_msg):
        try:
            if err_msg is None:
                send_mail("create_certs was completed",
                          "create_certs({}) was success{}".format(self.operation, self._get_download_urls_text()),
                          settings.GA_OPERATION_EMAIL_SENDER,
                          [self.email],
                          fail_silently=False)
            else:
                send_mail("create_certs was failure",
                          err_msg,
                          settings.GA_OPERATION_EMAIL_SENDER,
                          [self.email],
                          fail_silently=False)
        except SMTPException:
            log.warning("Failure sending e-mail address: {}".format(self.email))
            log.warning("Failure sending e-mail operation: {}".format(self.operation))
            log.exception("Failed to send a email to a staff.")
        except Exception as e:
            log.exception('Caught the exception: ' + type(e).__name__)

    @staticmethod
    def get_command_name():
        return "create_certs"

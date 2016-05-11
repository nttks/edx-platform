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
from xmodule.modulestore.django import modulestore
from ga_operation.utils import (handle_downloaded_file_from_s3, delete_files, change_behavior_sys,
                                get_std_info_from_local_storage)

log = logging.getLogger(__name__)


class TaskBase(object):
    """ Each Task Class's BaseClass """

    def __init__(self, email):
        super(TaskBase, self).__init__()
        self.err_msg = ''
        self.out_msg = ''
        self.email = email

    def _send_email(self):
        try:
            subject, body = self._get_email_subject(), self._get_email_body()
            send_mail(subject,
                      body,
                      settings.GA_OPERATION_EMAIL_SENDER,
                      [self.email],
                      fail_silently=False)
        except SMTPException:
            log.warning("Failure sending e-mail address: {}".format(self.email))
            log.exception("Failed to send a email to a staff.")
        except Exception as e:
            log.exception('Caught the exception: ' + type(e).__name__)

    def _get_email_subject(self):
        if len(self.err_msg):
            return "{} was failure".format(self.get_command_name())
        else:
            return "{} was completed.".format(self.get_command_name())

    def _get_email_body(self):
        if len(self.err_msg):
            return self.err_msg
        else:
            return "{} was succeeded.\n\n{}".format(self.get_command_name(), self.out_msg)

    @staticmethod
    def get_command_name():
        raise NotImplementedError


@CELERY_APP.task
def create_certs_task(course_id, email, file_name_list, is_meeting=False):
    """create_certs_task main."""
    CreateCerts(course_id, email, file_name_list, is_meeting).run()


class CreateCerts(TaskBase):
    """Generate certificate class"""

    def __init__(self, course_id, email, file_name_list, is_meeting=False):
        super(CreateCerts, self).__init__(email)
        self.course_id = course_id
        self.operation = "create"
        self.is_meeting = is_meeting
        self.file_name_list = file_name_list

    def run(self):
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
            self.err_msg = "{}".format(e)
        except Exception as e:
            log.exception('Caught the exception: ' + type(e).__name__)
            self.err_msg = "{}".format(e)
        finally:
            if not len(self.err_msg):
                self.out_msg = self._get_download_urls_text()
            self._send_email()
            delete_files(self.file_name_list, settings.PDFGEN_BASE_PDF_DIR)

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

    def _get_email_body(self):
        if len(self.err_msg):
            return "{}({}) was failed.\n\n{}".format(self.get_command_name(),
                                                     self.operation,
                                                     self.err_msg)
        else:
            return "{}({}) was success{}".format(self.get_command_name(),
                                                 self.operation,
                                                 self._get_download_urls_text())

    @staticmethod
    def get_command_name():
        return "create_certs"


@CELERY_APP.task
def dump_oa_scores_task(course_id, email):
    """dump_oa_scores_task main."""
    DumpOaScores(course_id, email).run()


class DumpOaScores(TaskBase):
    """DumpOaScores class."""

    def __init__(self, course_id, email):
        super(DumpOaScores, self).__init__(email)
        self.course_id = course_id

    def run(self):
        oa_items = None
        try:
            course_key = CourseKey.from_string(self.course_id)
            oa_items = modulestore().get_items(course_key, qualifiers={'category': 'openassessment'})
            with change_behavior_sys():
                # Change behavior raw_input method while take the all dump files
                # The raw_input's behavior has been changed and if call it, return the increment value.
                for _ in range(0, len(oa_items)):
                    call_command(self.get_command_name(), self.course_id, dump_dir=self._get_dump_dir())
        except Exception as e:
            log.exception('Caught the exception: ' + type(e).__name__)
        finally:
            if oa_items:
                self.err_msg, self.out_msg = get_std_info_from_local_storage()
                self._send_email()

    @staticmethod
    def _get_dump_dir():
        return settings.GA_OPERATION_WORK_DIR + "/" + DumpOaScores.get_command_name()

    @staticmethod
    def get_command_name():
        return "dump_oa_scores"

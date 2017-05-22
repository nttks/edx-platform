import logging
from smtplib import SMTPException

from django.core.mail import send_mail
from django.conf import settings

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
            log.exception("Failed to send an email to staff.")
        except Exception as e:
            log.exception('Caught the exception: ' + type(e).__name__)

    def _get_email_subject(self):
        if self.err_msg:
            return "{} was failure.".format(self.get_command_name())
        else:
            return "{} was completed.".format(self.get_command_name())

    def _get_email_body(self):
        if self.err_msg:
            return self.err_msg
        else:
            return "{} was succeeded.\n\n{}".format(self.get_command_name(), self.out_msg)

    @staticmethod
    def get_command_name():
        raise NotImplementedError

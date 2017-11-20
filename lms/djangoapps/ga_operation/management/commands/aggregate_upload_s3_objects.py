import logging
import pytz
import traceback
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from openedx.core.djangoapps.ga_operation.utils import open_bucket_from_s3

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    This command allows you to aggregate S3 objects in specific S3 buckets.

    Usage: python manage.py lms --settings=aws aggregate_upload_s3_objects [--yyyymm YYYYmm]
    """
    help = 'Usage: aggregate_upload_s3_objects [--yyyymm YYYYmm]'

    def add_arguments(self, _parser):
        _parser.add_argument(
            '--yyyymm',
            action='store',
            default=None,
            help='Year and month. format: YYYYmm',
        )

    @staticmethod
    def _get_target_month(str_ym):
        """
        If you specify a date, return the specified date.
        Or if you not specified, return the date of the previous month.
        """
        target_month = datetime.strptime(str_ym, '%Y%m') if str_ym else datetime.now() - relativedelta(months=1)
        return pytz.timezone(settings.TIME_ZONE).localize(target_month)

    @staticmethod
    def _is_target_object(key, target_year_and_month):
        """ Check if S3 object was uploaded during the target month of the year. """
        last_modified = parser.parse(key.last_modified).astimezone(pytz.timezone(settings.TIME_ZONE))
        return target_year_and_month.year == last_modified.year and target_year_and_month.month == last_modified.month

    @staticmethod
    def _get_email_body(target_count):
        return 'Number of the upload files: {}'.format(target_count)

    @staticmethod
    def _get_email_subject(target_month, is_success):
        return 'aggregate_upload_s3_objects has {0}({1:%Y/%m})'.format(
            'succeeded' if is_success else 'failed',
            target_month,
        )

    def _aggregate_file_count(self, bucket_name, prefix, target_month):
        with open_bucket_from_s3(bucket_name) as bucket:
            return sum(
                [int(self._is_target_object(key, target_month)) for key in bucket.list(prefix)]
            )

    def handle(self, *args, **options):
        subject = body = None
        str_ym = options.get('yyyymm')
        target_month = self._get_target_month(str_ym)

        log.info('target_month: {0:%Y/%m}'.format(target_month))

        try:
            target_count = sum([
                self._aggregate_file_count(bucket_name, prefix, target_month)
                for bucket_name, prefix in settings.GA_OPERATION_TARGET_BUCKETS_OF_AGGREGATE_UPLOAD_S3_OBJECTS.iteritems()
            ])
            subject, body = self._get_email_subject(target_month, is_success=True), self._get_email_body(target_count)
            log.info(body)
        except Exception as e:
            log.exception('Caught the exception: ' + type(e).__name__)
            subject, body = self._get_email_subject(target_month, is_success=False), traceback.format_exc()
        finally:
            send_mail(
                subject,
                body,
                settings.GA_OPERATION_EMAIL_SENDER_FSECURE_REPORT,
                settings.GA_OPERATION_CALLBACK_EMAIL_SERVICE_SUPPORT,
                fail_silently=False
            )

import argparse
import csv
import json
import logging
import os
import shutil
import urllib
from datetime import datetime, timedelta
from tempfile import mkdtemp, mkstemp

import easywebdav
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from ...models import DiagnosisInfo
from biz.djangoapps.util import datetime_utils
from opaque_keys import InvalidKeyError
from opaque_keys.edx.locator import CourseLocator
from openedx.core.djangoapps.ga_operation.utils import open_bucket_from_s3
from pdfgen.views import CertS3Store

log = logging.getLogger(__name__)


class TrackinglogDoesNotExist(Exception):
    pass


def check_course_id(course_id):
    """Check course_id."""
    try:
        CourseLocator.from_string(course_id)
    except InvalidKeyError:
        raise CommandError(
            "'{}' is an invalid course_id".format(course_id)
        )


def check_target_date(target_date):
    """Check target_date."""
    try:
        if target_date:
            datetime.strptime(target_date, '%Y%m%d')
    except ValueError:
        raise CommandError(
            "'{}' is an invalid target_date".format(target_date)
        )


def get_target_date(target_date):
    if target_date:
        base_date = datetime.strptime(target_date, '%Y%m%d').date()
    else:
        base_date = datetime.today().date() - timedelta(days=1)
    return datetime_utils.min_and_max_of_date(base_date)


class Command(BaseCommand):
    help = 'Usage: python manage.py lms --settings=aws ga_diagnosis_send_data [--target_date=<yyyymmdd>] <course_id>'
    webdav = easywebdav.connect(
        settings.GA_DIAGNOSIS_WEBDAV_SERVER['HOST'],
        username=settings.GA_DIAGNOSIS_WEBDAV_SERVER['USERNAME'],
        password=settings.GA_DIAGNOSIS_WEBDAV_SERVER['PASSWORD'],
        protocol=settings.GA_DIAGNOSIS_WEBDAV_SERVER['PROTOCOL'],
        path=settings.GA_DIAGNOSIS_WEBDAV_SERVER['PATH'],
    )

    def add_arguments(self, parser):
        parser.add_argument('--target_date')
        parser.add_argument('args', nargs=argparse.REMAINDER)

    def handle(self, *args, **options):
        if len(args) != 1:
            self.print_help('manage.py', 'ga_diagnosis_send_data')
            raise CommandError('course_id is not specified.')
        course_id = args[0]
        if not self.webdav.exists(settings.GA_DIAGNOSIS_DESTINATION_ROOT_PATH):
            raise CommandError(
                "Root Path: {} is not exists".format(settings.GA_DIAGNOSIS_DESTINATION_ROOT_PATH)
            )

        check_course_id(course_id)

        target_date = options.get('target_date', '')
        check_target_date(target_date)

        log.info('Command ga_diagnosis_send_data target_date={} Start'.format(target_date))

        self.perform_operation(target_date, CourseLocator.from_string(course_id))

        log.info('Command ga_diagnosis_send_data End')

    @staticmethod
    def _mask_data(rec, column):
        if column in settings.GA_DIAGNOSIS_MASK_TARGET_LIST:
            return u''
        return unicode(getattr(rec, column)).encode('utf-8') if getattr(rec, column) else u''

    def perform_operation(self, target_date, course_id):
        start_date, _ = get_target_date(target_date)
        try:
            header = [f.column.encode('utf-8') for f in DiagnosisInfo._meta.fields]
            records = [header]
            for rec in DiagnosisInfo.objects.all():
                records.append(
                    [self._mask_data(rec, column) for column in header]
                )
            directory_list = self._get_destination_directory_list_for_webdav_server(start_date)

            self._send_csv(records, start_date, directory_list)

            self._send_tracking_log(start_date, directory_list, course_id)
        except Exception as e:
            msg = 'Caught some exception: {}'.format(e)
            log.exception(msg)
            send_mail(
                subject='ga_diagnosis_send_data was failed ({year}/{month:02d}/{day:02d})'.format(
                    year=start_date.year,
                    month=start_date.month,
                    day=start_date.day,
                ),
                message=msg,
                from_email=settings.GA_DIAGNOSIS_SERVICE_SUPPORT_SENDER,
                recipient_list=settings.GA_DIAGNOSIS_SERVICE_SUPPORT_EMAIL,
            )

    def _get_destination_directory_list_for_webdav_server(self, start_date):
        directory_list = []
        for param in [settings.GA_DIAGNOSIS_DESTINATION_ROOT_PATH, str(start_date.year),
                      '{:02d}'.format(start_date.month),
                      '{:02d}'.format(start_date.day)]:
            directory_list.append(param)
            # Create the directory if not exists.
            if not self.webdav.exists(os.path.join(*directory_list)):
                self.webdav.mkdir(os.path.join(*directory_list))
        return directory_list

    def _upload_file(self, local_path, remote_path):
        # Delete the csv file if exists.
        if self.webdav.exists(remote_path):
            self.webdav.delete(remote_path)
        self.webdav.upload(local_path, remote_path)

    def _send_csv(self, records, start_date, directory_list):
        fd = path = None
        try:
            fd, path = mkstemp(suffix='-diagnosis-send-data.csv')

            with open(path, 'w') as fp:
                writer = csv.writer(fp, lineterminator='\r\n', quoting=csv.QUOTE_NONNUMERIC)
                for r in records:
                    writer.writerow(r)

            trackinglog_file_name = settings.GA_DIAGNOSIS_SEND_LOG_FILE_NAME.format(
                year=start_date.year,
                month=start_date.month,
                day=start_date.day,
            )
            csv_file_path = os.path.join(*directory_list + [trackinglog_file_name])
            self._upload_file(path, csv_file_path)
        finally:
            if fd:
                os.close(fd)
            if path:
                os.remove(path)

    @staticmethod
    def _fetch_tracking_log(start_date, course_id, download_dir_path):
        path_list = []
        with open_bucket_from_s3(settings.GA_DIAGNOSIS_S3_BUCKET_NAME_FROM_TRACKINGLOG) as bucket:
            prefix = os.path.join(
                urllib.quote(str(course_id)),
                settings.GA_DIAGNOSIS_S3_PREFIX_FROM_TRACKINGLOG.format(
                    year=start_date.year,
                    month=start_date.month,
                    day=start_date.day,
                )
            )
            for k in bucket.list(prefix, '/'):
                download_file_path = os.path.join(download_dir_path, str(k.key.split('/')[-1]))
                k.get_contents_to_filename(download_file_path)
                path_list.append(download_file_path)
        return path_list

    def _send_tracking_log(self, start_date, directory_list, course_id):
        download_dir_path = mkdtemp()
        path_list = self._fetch_tracking_log(start_date, course_id, download_dir_path)
        try:
            if path_list:
                for path in path_list:
                    self._upload_file(path, os.path.join(*directory_list + [path.split('/')[-1]]))
            else:
                raise TrackinglogDoesNotExist('trackinglog was not found')
        finally:
            shutil.rmtree(download_dir_path)

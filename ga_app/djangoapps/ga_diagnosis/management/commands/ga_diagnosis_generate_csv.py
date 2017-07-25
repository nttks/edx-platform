# -*- coding: utf-8 -*-
import argparse
import json
import logging
import os
import re
from datetime import datetime, time, timedelta
from optparse import make_option
from pytz import timezone
from tempfile import mkstemp

from boto.exception import S3ResponseError
from boto.s3 import connect_to_region
from boto.s3.connection import Location, OrdinaryCallingFormat
from boto.s3.key import Key
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from ...models import DiagnosisInfo
from biz.djangoapps.util import datetime_utils
from opaque_keys import InvalidKeyError
from opaque_keys.edx.locator import CourseLocator
from pdfgen.views import CertS3Store

log = logging.getLogger(__name__)


class S3Store(CertS3Store):
    """S3 store."""

    def __init__(self):
        super(S3Store, self).__init__()
        if None in (settings.GA_DIAGNOSIS_OUTPUT_BUCKET_NAME,
                    settings.AWS_ACCESS_KEY_ID,
                    settings.AWS_SECRET_ACCESS_KEY):
            raise InvalidSettings(
                'GA_DIAGNOSIS_OUTPUT_BUCKET_NAME, AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY is None.'
            )

        self.bucket_name = settings.GA_DIAGNOSIS_OUTPUT_BUCKET_NAME
        self.access_key = settings.AWS_ACCESS_KEY_ID
        self.secret_key = settings.AWS_SECRET_ACCESS_KEY

    def save(self, username, course_id, filepath):
        """Save diagnosis csv."""
        s3key = None
        try:
            bucket = self.conn.get_bucket(self.bucket_name)
        except S3ResponseError as e:
            if e.status == 404:
                bucket = self.conn.create_bucket(
                    self.bucket_name,
                    location=self.location)
                log.info('Create bucket({})'.format(self.bucket_name))
            else:
                return json.dumps({'error': '{}'.format(e)})

        try:
            s3key = Key(bucket)
            s3key.key = '{cid}/{name}'.format(
                cid=course_id, name=username)

            s3key.set_contents_from_filename(filepath)
            url = s3key.generate_url(
                expires_in=0, query_auth=False, force_http=True)
        finally:
            if s3key:
                s3key.close()

        return json.dumps({'download_url': url, })


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
    help = 'Usage: python manage.py lms --settings=aws ga_diagnosis_generate_csv [--target_date=<yyyymmdd>] <course_id>'

    store = S3Store()

    def add_arguments(self, parser):
        parser.add_argument('--target_date')
        parser.add_argument('args', nargs=argparse.REMAINDER)

    def handle(self, *args, **options):
        if len(args) != 1:
            self.print_help('manage.py', 'ga_diagnosis_generate_csv')
            raise CommandError('course_id is not specified.')
        course_id = args[0]
        target_date = options.get('target_date', '')
        check_course_id(course_id)
        check_target_date(target_date)
        log.info('Command ga_diagnosis_generate_csv course_id={}, target_date={} Start'.format(course_id, target_date))
        course_id = CourseLocator.from_string(course_id)
        try:
            self.generate_csv(course_id, target_date)
        except Exception as e:
            log.exception('Caught some exception: {}'.format(e))

        log.info('Command ga_diagnosis_generate_csv End')

    def generate_csv(self, course_id, target_date):
        start_date, end_date = get_target_date(target_date)
        log.info('start_date: {}'.format(start_date))
        log.info('  end_date: {}'.format(end_date))
        query = DiagnosisInfo.objects.filter(
            finished=True,
            course_id=course_id,
            finished_date__gte=start_date,
            finished_date__lte=end_date,
            regulation_state=int(DiagnosisInfo.REGULATION_A),
        )
        records = [settings.GA_DIAGNOSIS_CSV_HEADER.encode('utf-8')]
        for rec in query:
            records.append(
                settings.GA_DIAGNOSIS_CSV_FORMAT_BASE.format(
                    self._trim_white_space(rec.block1_01_1 + rec.block1_01_2),
                    self._trim_white_space(rec.block1_02_1 + rec.block1_02_2),
                    rec.block3_01,
                    rec.block3_02,
                    u'{}-{}-{}'.format(rec.block3_03_1, rec.block3_03_2, rec.block3_03_3),
                    rec.block1_05,
                    u'{}/{:02d}/{:02d}'.format(rec.block1_04_1, int(rec.block1_04_2), int(rec.block1_04_3)),
                    rec.block1_03,
                    settings.GA_DIAGNOSIS_CONVERT_VALUE['block1_05'].format(rec.block1_05),
                    rec.block3_04,
                    u'' if rec.block3_05 == settings.GA_DIAGNOSIS_EXCLUDE_TARGET_DATA['block3_05'] else rec.block3_05,
                    rec.block3_06,
                    rec.block3_07,
                    rec.block3_09_1,
                    rec.block3_09_2,
                    u'' if rec.block3_07 == settings.GA_DIAGNOSIS_EXCLUDE_TARGET_DATA['block3_09'] else rec.block3_09_3,
                    u'' if rec.block3_07 == settings.GA_DIAGNOSIS_EXCLUDE_TARGET_DATA['block3_09'] else rec.block3_09_4,
                    rec.block3_08,
                    rec.block3_11,
                    rec.block3_10,
                    int(rec.block3_19) - 1,
                    rec.block3_12,
                    settings.GA_DIAGNOSIS_MAPPING_TABLE[rec.block3_13],
                    rec.block3_13,
                    rec.block3_14,
                    int(rec.block3_15),
                    int(rec.block2_01),
                    rec.block3_18,
                    self._get_block3_16_1(rec.block3_16),
                    rec.block3_17,
                    u' - '.join([getattr(rec, 'block2_{:02d}'.format(i)) for i in range(2, 28)]),
                    u'\n'.join([i for i in rec.block3_16.split('\n') if
                               i not in settings.GA_DIAGNOSIS_EXCLUDE_TARGET_DATA['block3_16_2']])
                ).encode('utf-8')
            )
        self._create_csv(course_id, records, start_date)
        send_mail(
            subject=settings.GA_DIAGNOSIS_DAILY_REPORT['SUBJECT'].format(
                year=start_date.year,
                month=start_date.month,
                day=start_date.day,
            ),
            message=settings.GA_DIAGNOSIS_DAILY_REPORT['MESSAGE'].format(len(records) - 1),
            from_email=settings.GA_DIAGNOSIS_DAILY_REPORT['FROM_EMAIL'],
            recipient_list=settings.GA_DIAGNOSIS_DAILY_REPORT['RECIPIENT_LIST'],
        )

    @staticmethod
    def _trim_white_space(value):
        return re.sub(r'[ |　]', '', value)

    @staticmethod
    def _get_block3_16_1(block3_16):
        result = []
        found = False
        for val in block3_16.split('\n'):
            if val in settings.GA_DIAGNOSIS_EXCLUDE_TARGET_DATA['block3_16_1']:
                found = True
            else:
                result.append(val)
        if found:
            result.append(settings.GA_DIAGNOSIS_BLOCK3_16_REPLACE_VALUE)
        return '\n'.join(result)

    def _create_csv(self, course_id, records, start_date):
        fd = path = None
        try:
            fd, path = mkstemp(suffix='-diagnosis.csv')

            with open(path, 'w') as fp:
                fp.writelines(records)

            response_json = self.store.save(
                settings.GA_DIAGNOSIS_OUTPUT_FILE_FORMAT.format(now=start_date),
                course_id,
                path
            )
            log.info(response_json)
        finally:
            if fd:
                os.close(fd)
            if path:
                os.remove(path)

import ddt
import pytz
from datetime import datetime
from mock import MagicMock, patch, PropertyMock

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings

from ga_operation.management.commands.aggregate_upload_s3_objects import Command


@ddt.ddt
@override_settings(
    TIME_ZONE='Asia/Tokyo',
    GA_OPERATION_EMAIL_SENDER_FSECURE_REPORT='sender@example.com',
    GA_OPERATION_CALLBACK_EMAIL_SERVICE_SUPPORT=['receiver@example.com'],
)
class AggregateUploadS3ObjectsTest(TestCase):

    def setUp(self):
        self.cmd = Command()

    @ddt.data(
        ('201712', None, datetime(2017, 12, 1)),
        ('', datetime(2017, 1, 1), datetime(2016, 12, 1)),
        ('', datetime(2017, 2, 1), datetime(2017, 1, 1)),
        ('', datetime(2017, 3, 1), datetime(2017, 2, 1)),
        ('', datetime(2017, 4, 1), datetime(2017, 3, 1)),
        ('', datetime(2017, 5, 1), datetime(2017, 4, 1)),
        ('', datetime(2017, 6, 1), datetime(2017, 5, 1)),
        ('', datetime(2017, 7, 1), datetime(2017, 6, 1)),
        ('', datetime(2017, 8, 1), datetime(2017, 7, 1)),
        ('', datetime(2017, 9, 1), datetime(2017, 8, 1)),
        ('', datetime(2017, 10, 1), datetime(2017, 9, 1)),
        ('', datetime(2017, 11, 1), datetime(2017, 10, 1)),
        ('', datetime(2017, 12, 1), datetime(2017, 11, 1)),
        ('dummy', None, ValueError),
        ('2017-12', None, ValueError),
    )
    @ddt.unpack
    def test_get_target_date(self, str_ym, now, expect_value):
        if type(expect_value) == datetime:
            if str_ym:
                actual_date = self.cmd._get_target_month(str_ym)
            else:
                with patch('ga_operation.management.commands.aggregate_upload_s3_objects.datetime') as mock_datetime:
                    mock_datetime.now.return_value = now
                    actual_date = self.cmd._get_target_month(str_ym)
            self.assertEqual(actual_date, pytz.timezone(settings.TIME_ZONE).localize(expect_value))
        else:
            with self.assertRaises(expect_value):
                self.cmd._get_target_month(str_ym)

    @ddt.data(
        ('202007', '2020-07-04T06:50:47.000Z', True),
        ('202007', '2020-07-05T06:50:47.000Z', True),
        ('202007', '2020-07-04T07:50:47.000Z', True),
        ('202007', '2020-07-04T06:51:47.000Z', True),
        ('202007', '2020-07-04T06:50:48.000Z', True),
        ('202007', '2020-07-04T06:50:47.001Z', True),
        ('202007', '2020-08-04T06:50:47.000Z', False),
        ('202007', '2019-07-04T06:50:47.000Z', False),
    )
    @ddt.unpack
    def test_is_target_object(self, str_ym, last_modified, is_target):
        mock_key = MagicMock()
        type(mock_key).last_modified = PropertyMock(return_value=last_modified)
        self.assertEqual(
            self.cmd._is_target_object(mock_key, datetime.strptime(str_ym, '%Y%m')),
            is_target
        )

    @ddt.data(
        (0, 'Number of the upload files: 0'),
        (9999999, 'Number of the upload files: 9999999'),
    )
    @ddt.unpack
    def test_get_email_body(self, target_count, expect_value):
        self.assertEqual(self.cmd._get_email_body(target_count), expect_value)

    @ddt.data(
        ('201711', True),
        ('201812', False),
    )
    @ddt.unpack
    def test_get_email_subject(self, str_ym, is_success):
        ym = datetime.strptime(str_ym, '%Y%m')

        actual_subject = self.cmd._get_email_subject(ym, is_success)

        if is_success:
            self.assertEqual(actual_subject, 'aggregate_upload_s3_objects has succeeded({0:%Y/%m})'.format(ym))
        else:
            self.assertEqual(actual_subject, 'aggregate_upload_s3_objects has failed({0:%Y/%m})'.format(ym))

    @patch('ga_operation.management.commands.aggregate_upload_s3_objects.open_bucket_from_s3')
    @ddt.data(
        (True, 3, 3),
        (False, 3, 0),
    )
    @ddt.unpack
    def test_aggregate_file_count(self, is_target, s3_object_count, expect_count, mock_open_bucket_from_s3):
        s3_object_list = [MagicMock() for _ in range(s3_object_count)]
        mock_open_bucket_from_s3().__enter__().list.return_value = s3_object_list
        mock_open_bucket_from_s3.reset_mock()
        self.cmd._is_target_object = MagicMock(return_value=is_target)

        actual_count = self.cmd._aggregate_file_count('dummy_bucket_name', 'dummy_prefix', datetime.now())

        self.assertEqual(actual_count, expect_count)
        mock_open_bucket_from_s3.assert_called_once_with('dummy_bucket_name')
        self.assertEqual(self.cmd._is_target_object.call_count, s3_object_count)

    @patch('ga_operation.management.commands.aggregate_upload_s3_objects.traceback.format_exc', return_value='dummy_traceback')
    @patch('ga_operation.management.commands.aggregate_upload_s3_objects.send_mail')
    @ddt.data(
        ({}, {'bucket_1': 'prefix_1'}, 5, None),
        ({'yyyymm': '202008'}, {'bucket_1': 'prefix_1', 'bucket_2': 'prefix_2'}, 10, None),
        ({}, {'bucket_1': 'prefix_1'}, 5, Exception),
        ({'yyyymm': '202008'}, {'bucket_1': 'prefix_1', 'bucket_2': 'prefix_2'}, 10, Exception),
    )
    @ddt.unpack
    def test_handle(self, options, target_buckets, expect_file_count, exception, mock_send_mail, mock_traceback):
        self.cmd._aggregate_file_count = MagicMock(side_effect=Exception()) if exception else MagicMock(
            return_value=expect_file_count / len(target_buckets)
        )

        with override_settings(GA_OPERATION_TARGET_BUCKETS_OF_AGGREGATE_UPLOAD_S3_OBJECTS=target_buckets):
            self.cmd.handle(*[], **options)

        target_month = self.cmd._get_target_month(options.get('yyyymm'))
        if exception:
            mock_traceback.assert_called_once()
            mock_send_mail.assert_called_once_with(
                'aggregate_upload_s3_objects has failed({0:%Y/%m})'.format(target_month),
                'dummy_traceback',
                settings.GA_OPERATION_EMAIL_SENDER_FSECURE_REPORT,
                settings.GA_OPERATION_CALLBACK_EMAIL_SERVICE_SUPPORT,
                fail_silently=False,
            )
        else:
            mock_traceback.assert_not_called_once()
            mock_send_mail.assert_called_once_with(
                'aggregate_upload_s3_objects has succeeded({0:%Y/%m})'.format(target_month),
                'Number of the upload files: {}'.format(expect_file_count),
                settings.GA_OPERATION_EMAIL_SENDER_FSECURE_REPORT,
                settings.GA_OPERATION_CALLBACK_EMAIL_SERVICE_SUPPORT,
                fail_silently=False,
            )

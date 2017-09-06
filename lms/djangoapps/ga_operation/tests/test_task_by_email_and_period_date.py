# -*- coding: utf-8 -*-
import datetime
import ddt
from mock import patch, MagicMock

from django.test import TestCase
from django.test.utils import override_settings

from ga_operation.tasks import (all_users_info_task, AllUsersInfo,
                                create_certs_status_task, CreateCertsStatus,
                                enrollment_status_task, EnrollmentStatus,
                                disabled_account_info_task, DisabledAccountInfo)


@ddt.ddt
@override_settings(AWS_ACCESS_KEY_ID='', AWS_SECRET_ACCESS_KEY='', GA_OPERATION_ANALYZE_UPLOAD_BUCKET_NAME='')
@override_settings(GA_OPERATION_WORK_DIR='/tmp')
@override_settings(GA_OPERATION_EMAIL_SENDER='sender@example.com')
class TaskByEmailAndPeriodDateTest(TestCase):

    # https://stackoverflow.com/questions/4481954/python-trying-to-mock-datetime-date-today-but-not-working
    class FakeDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.datetime(2017, 8, 31, 12, 34, 56)

    def setUp(self):
        super(TaskByEmailAndPeriodDateTest, self).setUp()

    @staticmethod
    def choose_task_cls(key):
        return {
            'all_users_info_task': 'ga_operation.tasks.AllUsersInfo',
            'create_certs_status_task': 'ga_operation.tasks.CreateCertsStatus',
            'enrollment_status_task': 'ga_operation.tasks.EnrollmentStatus',
            'disabled_account_info_task': 'ga_operation.tasks.DisabledAccountInfo'
        }[key]

    @ddt.data(
        'all_users_info_task',
        'create_certs_status_task',
        'enrollment_status_task',
        'disabled_account_info_task'
    )
    def test_call_run(self, task_func_name):
        task_cls = self.choose_task_cls(task_func_name)
        with patch(task_cls) as mock_cls:
            mock_cls.run = MagicMock()
            task_call_func = globals()[task_func_name]
            task_call_func('2016-01-01', '2017-07-31', 'test@example.com')
            mock_cls.run.assert_called()

    @patch('ga_operation.tasks.datetime', FakeDateTime)
    @ddt.data(
        ('all_users_info_task', 'auth_userprofile'),
        ('create_certs_status_task', 'certificates_generatedcertificate'),
        ('enrollment_status_task', 'student_courseenrollment'),
        ('disabled_account_info_task', 'student_userstanding')
    )
    @ddt.unpack
    def test_csv_filename(self, task_func_name, table_name):
        task_cls_str = self.choose_task_cls(task_func_name).split('.')[-1]
        task_cls = globals()[task_cls_str]
        task = task_cls('2016-01-01', '2017-07-31', 'test@example.com')
        self.assertEqual(task._csv_filename(), '{}-20170831_123456-20160101-20170731.csv'.format(table_name))

    @patch('ga_operation.tasks.connect_s3')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @ddt.data(
        ('all_users_info_task', 'auth_userprofile'),
        ('create_certs_status_task', 'certificates_generatedcertificate'),
        ('enrollment_status_task', 'student_courseenrollment'),
        ('disabled_account_info_task', 'student_userstanding')
    )
    @ddt.unpack
    def test_run_success(self, task_func_name, msg, mock_send_mail, mock_connect_s3):
        task_cls_str = self.choose_task_cls(task_func_name).split('.')[-1]
        task_cls = globals()[task_cls_str]
        task = task_cls('2016-01-01', '2017-07-31', 'test@example.com')
        task._fetch_data = MagicMock()
        task._fetch_data.return_value = [
            [1, 'test1', 'test1@example.com', 1, '2017-01-01 00:00:00', '2016-01-01 01:22:33', None, None, None],
            [2, 'test2', 'test2@example.com', 1, '2017-02-02 00:00:00', '2016-02-02 02:00:00', None, None, None],
        ]
        mock_bucket = MagicMock()
        mock_conn = MagicMock()
        mock_conn.get_bucket.return_value = mock_bucket
        mock_connect_s3 = MagicMock(return_value=mock_conn)
        task._upload_file_to_s3 = MagicMock(return_value='DUMMY_URL')

        task.run()

        mock_connect_s3.assert_called()
        mock_conn.get_bucket.assert_called()
        mock_send_mail.assert_called_once_with(
            '{} was completed.'.format(msg),
            'Successfully created csv file: {}'.format('DUMMY_URL'),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )

    @patch('ga_operation.tasks.connect_s3')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @ddt.data(
        ('all_users_info_task', 'auth_userprofile'),
        ('create_certs_status_task', 'certificates_generatedcertificate'),
        ('enrollment_status_task', 'student_courseenrollment'),
        ('disabled_account_info_task', 'student_userstanding')
    )
    @ddt.unpack
    def test_run_error(self, task_func_name, msg, mock_send_mail, mock_connect_s3):
        task_cls_str = self.choose_task_cls(task_func_name).split('.')[-1]
        task_cls = globals()[task_cls_str]
        task = task_cls('2016-01-01', '2017-07-31', 'test@example.com')
        task._fetch_data = MagicMock()
        task._fetch_data.side_effect = Exception('DUMMY ERROR')
        mock_bucket = MagicMock()
        mock_conn = MagicMock()
        mock_conn.get_bucket.return_value = mock_bucket
        mock_connect_s3 = MagicMock(return_value=mock_conn)
        task._upload_file_to_s3 = MagicMock(return_value='DUMMY_URL')

        with self.assertRaises(Exception):
            task.run()

        mock_connect_s3.assert_not_called()
        mock_conn.get_bucket.assert_not_called()
        mock_send_mail.assert_called_once_with(
            '{} was failure.'.format(msg),
            '{} was failed.\n\nError reason\nDUMMY ERROR'.format(msg),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )

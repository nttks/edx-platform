import ddt
import tempfile
from datetime import datetime
from mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from biz.djangoapps.ga_achievement.log_store import PlaybackLogStore
from biz.djangoapps.ga_achievement.management.commands import import_playback_log
from biz.djangoapps.util.tests.testcase import BizStoreTestBase

command_output_file = tempfile.NamedTemporaryFile()


class TestArgParsing(TestCase):

    def setUp(self):
        super(TestArgParsing, self).setUp()
        self.command = import_playback_log.Command()

    def test_args_too_much(self):
        errstring = "This command requires no arguments. Use target_date option if you want."
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, 2)

    def test_option_target_date_invalid(self):
        errstring = "Option target_date must be 'yyyymmdd' format."
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, target_date='11112233')


@ddt.ddt
@override_settings(
    BIZ_IMPORT_PLAYBACK_LOG_COMMAND_OUTPUT=command_output_file.name,
    BIZ_PLAYBACK_LOG_BUCKET_NAME='playback-log-bucket',
    AWS_ACCESS_KEY_ID='aws-access-key',
    AWS_SECRET_ACCESS_KEY='aws-secret-access-key',
)
class ImportPlaybackLogTest(BizStoreTestBase):

    def setUp(self):
        super(ImportPlaybackLogTest, self).setUp()

        patcher_log = patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

        patcher_decorators_log = patch('biz.djangoapps.util.decorators.log')
        self.mock_decorators_log = patcher_decorators_log.start()
        self.addCleanup(patcher_decorators_log.stop)

    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.open_bucket_from_s3')
    def test_no_csv_file(self, mock_open_bucket_from_s3):
        mock_open_bucket_from_s3.return_value.__enter__.return_value.get_key.return_value = None
        call_command('import_playback_log', target_date='20180404')

        self.mock_log.info.assert_any_call('Command import_playback_log started for 2018-04-04 00:00:00.')
        self.assertEqual(1, self.mock_decorators_log.info.call_count)
        self.assertEqual(1, self.mock_decorators_log.error.call_count)

    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.open_bucket_from_s3')
    def test_no_csv_data(self, mock_open_bucket_from_s3):
        mock_open_bucket_from_s3.return_value.__enter__.return_value.get_key.return_value.get_contents_as_string.return_value = "\n".join([
            'skip-first-line',
        ])
        call_command('import_playback_log', target_date='20180404')

        self.mock_log.info.assert_any_call('Command import_playback_log started for 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log get data from [playback-log-bucket/playbacklog/2018/04/04/mv_play_log_20180404.csv], record count(0), skip row count(0).')
        self.mock_log.info.assert_any_call('Command import_playback_log removed mongo records of 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log finished for 2018-04-04 00:00:00.')

        self.assertEqual(2, self.mock_decorators_log.info.call_count)
        self.assertEqual(0, self.mock_decorators_log.error.call_count)

    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.open_bucket_from_s3')
    def test_one_data(self, mock_open_bucket_from_s3):
        mock_open_bucket_from_s3.return_value.__enter__.return_value.get_key.return_value.get_contents_as_string.return_value = "\n".join([
            'skip-first-line',
            'col-0,col-1,00:00:01,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
        ])
        call_command('import_playback_log', target_date='20180404')

        self.mock_log.info.assert_any_call('Command import_playback_log started for 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log get data from [playback-log-bucket/playbacklog/2018/04/04/mv_play_log_20180404.csv], record count(1), skip row count(0).')
        self.mock_log.info.assert_any_call('Command import_playback_log removed mongo records of 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log stored mongo records of 2018-04-04 00:00:00, record count(1).')
        self.mock_log.info.assert_any_call('Command import_playback_log finished for 2018-04-04 00:00:00.')

        self.assertEqual(2, self.mock_decorators_log.info.call_count)
        self.assertEqual(0, self.mock_decorators_log.error.call_count)

    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.open_bucket_from_s3')
    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.datetime_utils.timezone_yesterday')
    def test_one_data_yesterday(self, mock_timezone_yesterday, mock_open_bucket_from_s3):
        mock_timezone_yesterday.return_value.strftime.return_value = '20180404'
        mock_open_bucket_from_s3.return_value.__enter__.return_value.get_key.return_value.get_contents_as_string.return_value = "\n".join([
            'skip-first-line',
            'col-0,col-1,00:00:01,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
        ])
        call_command('import_playback_log')

        self.mock_log.info.assert_any_call('Command import_playback_log started for 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log get data from [playback-log-bucket/playbacklog/2018/04/04/mv_play_log_20180404.csv], record count(1), skip row count(0).')
        self.mock_log.info.assert_any_call('Command import_playback_log removed mongo records of 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log stored mongo records of 2018-04-04 00:00:00, record count(1).')
        self.mock_log.info.assert_any_call('Command import_playback_log finished for 2018-04-04 00:00:00.')

        self.assertEqual(2, self.mock_decorators_log.info.call_count)
        self.assertEqual(0, self.mock_decorators_log.error.call_count)

    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.open_bucket_from_s3')
    def test_skip_data(self, mock_open_bucket_from_s3):
        mock_open_bucket_from_s3.return_value.__enter__.return_value.get_key.return_value.get_contents_as_string.return_value = "\n".join([
            'skip-first-line',
            'col-0,col-1,col-2,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
            'col-0,col-1,00:00:00,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
            'col-0,col-1,99:99:99,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
            'col-0,col-1,00:00:01,col-3,col-4,target_id=target-id&vertical_id=vertical-id',
            'col-0,col-1,00:00:01,col-3,col-4,course_id=course-id&vertical_id=vertical-id',
            'col-0,col-1,00:00:01,col-3,col-4,course_id=course-id&target_id=target-id',
        ])
        call_command('import_playback_log', target_date='20180404')

        self.mock_log.info.assert_any_call('Command import_playback_log started for 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log get data from [playback-log-bucket/playbacklog/2018/04/04/mv_play_log_20180404.csv], record count(0), skip row count(6).')
        self.mock_log.info.assert_any_call('Command import_playback_log removed mongo records of 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log finished for 2018-04-04 00:00:00.')

        self.assertEqual(2, self.mock_decorators_log.info.call_count)
        self.assertEqual(0, self.mock_decorators_log.error.call_count)

    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.open_bucket_from_s3')
    def test_merge_data(self, mock_open_bucket_from_s3):
        mock_open_bucket_from_s3.return_value.__enter__.return_value.get_key.return_value.get_contents_as_string.return_value = "\n".join([
            'skip-first-line',
            'col-0,col-1,00:00:01,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
            'col-0,col-1,00:00:02,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
        ])
        call_command('import_playback_log', target_date='20180404')

        self.mock_log.info.assert_any_call('Command import_playback_log started for 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log get data from [playback-log-bucket/playbacklog/2018/04/04/mv_play_log_20180404.csv], record count(1), skip row count(0).')
        self.mock_log.info.assert_any_call('Command import_playback_log removed mongo records of 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log stored mongo records of 2018-04-04 00:00:00, record count(1).')
        self.mock_log.info.assert_any_call('Command import_playback_log finished for 2018-04-04 00:00:00.')

        self.assertEqual(2, self.mock_decorators_log.info.call_count)
        self.assertEqual(0, self.mock_decorators_log.error.call_count)

    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.open_bucket_from_s3')
    def test_calc_duration(self, mock_open_bucket_from_s3):
        mock_open_bucket_from_s3.return_value.__enter__.return_value.get_key.return_value.get_contents_as_string.return_value = "\n".join([
            'skip-first-line',
            'col-0,col-1,01:01:01,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
            'col-0,col-1,10:10:10,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
            'col-0,col-1,00:00:00,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
            'col-0,col-1,99:59:59,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
        ])
        with patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.PlaybackLogStore.set_documents') as mock_set_documents:
            call_command('import_playback_log', target_date='20180404')

        mock_set_documents.assert_called_once_with([
            {
                PlaybackLogStore.FIELD_COURSE_ID: 'course-id',
                PlaybackLogStore.FIELD_VERTICAL_ID: 'vertical-id',
                PlaybackLogStore.FIELD_TARGET_ID: 'target-id',
                PlaybackLogStore.FIELD_DURATION: 3600 * 110 + 60 * 70 + 70,
                PlaybackLogStore.FIELD_CREATED_AT: datetime.strptime('20180404', '%Y%m%d'),
            }
        ])

    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.open_bucket_from_s3')
    def test_can_not_remove(self, mock_open_bucket_from_s3):
        mock_open_bucket_from_s3.return_value.__enter__.return_value.get_key.return_value.get_contents_as_string.return_value = "\n".join([
            'skip-first-line',
            'col-0,col-1,00:00:01,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
        ])
        with patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.PlaybackLogStore.get_count', return_value=100):
            call_command('import_playback_log', target_date='20180404')

        self.mock_log.info.assert_any_call('Command import_playback_log started for 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log get data from [playback-log-bucket/playbacklog/2018/04/04/mv_play_log_20180404.csv], record count(1), skip row count(0).')

        self.assertEqual(1, self.mock_decorators_log.info.call_count)
        self.assertEqual(1, self.mock_decorators_log.error.call_count)

    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.open_bucket_from_s3')
    def test_can_not_store(self, mock_open_bucket_from_s3):
        mock_open_bucket_from_s3.return_value.__enter__.return_value.get_key.return_value.get_contents_as_string.return_value = "\n".join([
            'skip-first-line',
            'col-0,col-1,00:00:01,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
        ])
        with patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.PlaybackLogStore.get_count', return_value=0):
            call_command('import_playback_log', target_date='20180404')

        self.mock_log.info.assert_any_call('Command import_playback_log started for 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log get data from [playback-log-bucket/playbacklog/2018/04/04/mv_play_log_20180404.csv], record count(1), skip row count(0).')
        self.mock_log.info.assert_any_call('Command import_playback_log removed mongo records of 2018-04-04 00:00:00.')

        self.assertEqual(1, self.mock_decorators_log.info.call_count)
        self.assertEqual(1, self.mock_decorators_log.error.call_count)

    @patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.open_bucket_from_s3')
    def test_has_duplicate(self, mock_open_bucket_from_s3):
        mock_open_bucket_from_s3.return_value.__enter__.return_value.get_key.return_value.get_contents_as_string.return_value = "\n".join([
            'skip-first-line',
            'col-0,col-1,00:00:01,col-3,col-4,course_id=course-id&target_id=target-id&vertical_id=vertical-id',
        ])
        with patch('biz.djangoapps.ga_achievement.management.commands.import_playback_log.PlaybackLogStore.has_duplicate', return_value=True):
            call_command('import_playback_log', target_date='20180404')

        self.mock_log.info.assert_any_call('Command import_playback_log started for 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log get data from [playback-log-bucket/playbacklog/2018/04/04/mv_play_log_20180404.csv], record count(1), skip row count(0).')
        self.mock_log.info.assert_any_call('Command import_playback_log removed mongo records of 2018-04-04 00:00:00.')
        self.mock_log.info.assert_any_call('Command import_playback_log stored mongo records of 2018-04-04 00:00:00, record count(1).')

        self.assertEqual(1, self.mock_decorators_log.info.call_count)
        self.assertEqual(1, self.mock_decorators_log.error.call_count)

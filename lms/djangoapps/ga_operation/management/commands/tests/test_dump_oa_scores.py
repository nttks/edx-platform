
from collections import namedtuple
import csv
import ddt
from mock import MagicMock, patch
import os
import shutil

from django.core.management import call_command, CommandError
from django.test.utils import override_settings

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory

from ga_operation.management.commands import dump_oa_scores


MockUser = namedtuple('MockUser', 'username')


def mock_user_by_anonymous_id(anonymous_id):
    return MockUser(anonymous_id)


@ddt.ddt
@override_settings(AWS_ACCESS_KEY_ID='', AWS_SECRET_ACCESS_KEY='')
class DumpOaScoresTest(ModuleStoreTestCase):

    def setUp(self):
        super(DumpOaScoresTest, self).setUp()

        self.mock_conn = MagicMock()
        self.mock_bucket = MagicMock()
        self.mock_conn.get_bucket.return_value = self.mock_bucket
        self.mock_key = MagicMock()
        self.mock_bucket.get_key.return_value = self.mock_key

        self.course = CourseFactory.create()

        self.dump_dir = None

    def tearDown(self):
        dump_dir = self._get_dump_dir()
        if os.path.exists(dump_dir):
            shutil.rmtree(dump_dir)

        super(DumpOaScoresTest, self).tearDown()

    def _get_dump_dir(self):
        return self.dump_dir or '/tmp/dump_oa_scores'

    def _create_items(self):
        chapter = ItemFactory.create(parent_location=self.course.location, category='chapter', user_id=self.user.id)
        sequential = ItemFactory.create(parent_location=chapter.location, category='sequential', user_id=self.user.id)
        vertical1 = ItemFactory.create(parent_location=sequential.location, category='vertical', user_id=self.user.id)
        vertical2 = ItemFactory.create(parent_location=sequential.location, category='vertical', user_id=self.user.id)
        self.openassessment1 = ItemFactory.create(
            parent_location=vertical1.location, category='openassessment', title='openassessment1', user_id=self.user.id
        )
        self.openassessment2 = ItemFactory.create(
            parent_location=vertical2.location, category='openassessment', title='openassessment2', user_id=self.user.id
        )

    def test_no_course_id(self):
        error_message = "The course_id is not of the right format. It should be like 'org/course/run' or 'course-v1:org+course+run'"
        with self.assertRaises(CommandError) as e:
            call_command('dump_oa_scores')
            self.assertEqual(e.message, error_message)

    def test_invalid_course_id(self):
        error_message = "The course_id is not of the right format. It should be like 'org/course/run' or 'course-v1:org+course+run'"
        with self.assertRaises(CommandError) as e:
            call_command('dump_oa_scores', 'invalid-course-id')
            self.assertEqual(e.message, error_message)

    def test_course_not_exists(self):
        error_message = "No such course was found."
        with self.assertRaises(CommandError) as e:
            call_command('dump_oa_scores', 'course-v1:org+not-exists-course+run')
            self.assertEqual(e.message, error_message)

    def test_s3_connect_not_establish(self):
        error_message = "No openassessment item was found."
        with self.assertRaises(CommandError) as e:
            call_command('dump_oa_scores', unicode(self.course.id))
            self.assertEqual(e.message, error_message)

    @patch('ga_operation.management.commands.dump_oa_scores.connect_s3')
    def test_item_not_exists(self, mock_connect_s3):
        mock_connect_s3.return_value = self.mock_conn

        error_message = "No openassessment item was found."
        with self.assertRaises(CommandError) as e:
            call_command('dump_oa_scores', unicode(self.course.id))
            self.assertEqual(e.message, error_message)

    @patch('ga_operation.management.commands.dump_oa_scores.connect_s3')
    def test_no_submissions(self, mock_connect_s3):
        self._create_items()

        mock_connect_s3.return_value = self.mock_conn
        dump_oa_scores.raw_input = MagicMock(return_value='1')

        error_message = "No submission was found.."
        with self.assertRaises(CommandError) as e:
            call_command('dump_oa_scores', unicode(self.course.id))
            self.assertEqual(e.message, error_message)

    @patch('ga_operation.management.commands.dump_oa_scores.user_by_anonymous_id', side_effect=mock_user_by_anonymous_id)
    @patch('ga_operation.management.commands.dump_oa_scores.OraAggregateData.collect_ora2_data')
    @patch('ga_operation.management.commands.dump_oa_scores.connect_s3')
    @ddt.data(
        (None, False),
        ('/tmp/test_dump_oa_scores', True),
    )
    @ddt.unpack
    def test_success(self, dump_dir, is_attachments, mock_connect_s3, mock_collect_ora2_data, user_by_anonymous_id):
        self._create_items()
        self.dump_dir = dump_dir

        mock_connect_s3.return_value = self.mock_conn
        dump_oa_scores.raw_input = MagicMock(return_value='1')
        dump_oa_scores.upload_file_to_s3 = MagicMock()
        mock_collect_ora2_data.return_value = (
            [
                {'uuid': 'test-uuid1', 'student_id': 'student1'},
                {'uuid': 'test-uuid2', 'student_id': 'student2'},
            ],
            ['Test Header1', 'Test Header2'],
            [
                ['Test Value1-1', 'Test Value1-2'],
                ['Test Value2-1', 'Test Value2-2'],
            ]
        )

        options = {}
        if dump_dir:
            options['dump_dir'] = dump_dir
        if is_attachments:
            options['with_attachments'] = True
        call_command('dump_oa_scores', unicode(self.course.id), **options)

        csv_filename = 'oa_scores-%s-#%d.csv' % ('-'.join([self.course.id.org, self.course.id.course, self.course.id.run]), 1)
        csv_filepath = os.path.join(self._get_dump_dir(), csv_filename)
        with open(csv_filepath, 'rb') as f:
            csv_data = [row for row in csv.reader(f)]

        self.assertItemsEqual(csv_data, [
            ['Title', 'Test Header1', 'Test Header2'],
            ['openassessment2', 'Test Value1-1', 'Test Value1-2'],
            ['openassessment2', 'Test Value2-1', 'Test Value2-2'],
        ])

        tar_filename = 'oa_scores-%s-#%d.tar.gz' % ('-'.join([self.course.id.org, self.course.id.course, self.course.id.run]), 1)
        tar_filepath = os.path.join(self._get_dump_dir(), tar_filename)
        if is_attachments:
            self.assertEqual(2, dump_oa_scores.upload_file_to_s3.call_count)
            self.assertEqual(2, self.mock_bucket.get_key.call_count)
            self.assertEqual(2, self.mock_key.get_contents_to_filename.call_count)
            self.assertTrue(os.path.exists(tar_filepath))
        else:
            self.assertEqual(1, dump_oa_scores.upload_file_to_s3.call_count)
            self.mock_bucket.get_key.assert_not_called()
            self.assertFalse(os.path.exists(tar_filepath))

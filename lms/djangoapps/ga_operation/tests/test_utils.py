
from mock import Mock, patch
import tempfile

from django.test import TestCase

from opaque_keys.edx.keys import CourseKey

from ga_operation.utils import (
    course_filename, handle_file_from_s3, handle_uploaded_received_file_to_s3
)


class UtilsTest(TestCase):

    def setUp(self):
        super(UtilsTest, self).setUp()
        self.bucket_name = 'test_bucket'

        self.mock_conn = Mock()
        self.mock_bucket = Mock()
        self.mock_conn.get_bucket.return_value = self.mock_bucket

        patch_get_s3_connection = patch('ga_operation.utils.get_s3_connection')
        mock_get_s3_connection = patch_get_s3_connection.start()
        mock_get_s3_connection.return_value = self.mock_conn
        self.addCleanup(patch_get_s3_connection.stop)

    def test_handle_file_from_s3(self):
        mock_key = Mock()
        self.mock_bucket.get_key.return_value = mock_key

        ret = handle_file_from_s3('test_key', self.bucket_name)

        self.assertEqual(ret, mock_key)
        self.mock_conn.get_bucket.assert_called_once_with(self.bucket_name)
        self.mock_bucket.get_key.assert_called_once_with('test_key')
        mock_key.exists.assert_called_once()

    def test_handle_file_from_s3_file_not_found(self):
        mock_key = Mock()
        mock_key.exists.return_value = False
        self.mock_bucket.get_key.return_value = mock_key

        self.assertIsNone(handle_file_from_s3('test_key', self.bucket_name))
        self.mock_conn.get_bucket.assert_called_once_with(self.bucket_name)
        self.mock_bucket.get_key.assert_called_once_with('test_key')
        mock_key.exists.assert_called_once()

    @patch('ga_operation.utils.Key')
    def test_handle_uploaded_received_file_to_s3(self, mock_key):
        file_obj = tempfile.TemporaryFile()
        ret = handle_uploaded_received_file_to_s3(file_obj, 'test_key', self.bucket_name)

        self.assertEqual('test_key', ret.key)
        mock_key.assert_called_once_with(self.mock_bucket)
        mock_key.return_value.set_contents_from_file.assert_called_once_with(file_obj)
        self.mock_conn.get_bucket.assert_called_once_with(self.bucket_name)

    def test_course_filename(self):
        course_key = CourseKey.from_string('course-v1:test_org+test_course+test_run')
        self.assertEqual('test_org-test_course-test_run', course_filename(course_key))

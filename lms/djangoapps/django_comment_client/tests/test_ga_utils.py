# -*- coding: utf-8 -*-
import boto
from mock import patch, Mock
from moto import mock_s3
from nose.tools import raises

import django_comment_client.settings as cc_settings
from django_comment_client.utils import DiscussionS3Store, DiscussionFileUploadInternalError
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpRequest
from django.test.utils import override_settings

from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


class DiscussionS3StoreTestCase(ModuleStoreTestCase):

    @mock_s3
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        DISCUSSION_IMAGE_BACKEND_AWS_BUCKET_NAME='mybucket',
        DISCUSSION_IMAGE_BACKEND_LOCATION='/',
        DISCUSSION_ENABLE_WAF_PROXY=False,
        DISCUSSION_WAF_PROXY_SERVER_IP='100.0.0.1',
        DISCUSSION_WAF_PROXY_SERVER_PORT='9900',
    )
    def test_connect_to_s3(self):
        self.course_id = 'course-v1:org+course+run'
        conn = boto.connect_s3()
        conn.create_bucket('mybucket')

        waf_proxy_enabled = True
        downloadUrl = None
        downloadUrl = DiscussionS3Store()._connect_to_s3(waf_proxy_enabled)
        self.assertIsNotNone(downloadUrl)

        waf_proxy_enabled = False
        downloadUrl = None
        downloadUrl = DiscussionS3Store()._connect_to_s3(waf_proxy_enabled)
        self.assertIsNotNone(downloadUrl)

    @mock_s3
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        DISCUSSION_IMAGE_BACKEND_AWS_BUCKET_NAME='mybucket',
        DISCUSSION_IMAGE_BACKEND_LOCATION='/',
        DISCUSSION_ENABLE_WAF_PROXY=False,
        DISCUSSION_WAF_PROXY_SERVER_IP='None',
        DISCUSSION_WAF_PROXY_SERVER_PORT='9900',
    )
    def test_connect_to_s3_error(self):
        self.course_id = 'course-v1:org+course+run'
        conn = boto.connect_s3()
        conn.create_bucket('mybucket')

        waf_proxy_enabled = True
        try:
            DiscussionS3Store()._connect_to_s3(waf_proxy_enabled)
        except Exception as err:
            self.assertIn('WAF proxy feature for Disccusion image upload is enabled, but WAF server ip or port is not configured.', err)

    @mock_s3
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        DISCUSSION_IMAGE_BACKEND_AWS_BUCKET_NAME='mybucket',
        DISCUSSION_IMAGE_BACKEND_LOCATION='/',
        DISCUSSION_ENABLE_WAF_PROXY=True,
        DISCUSSION_WAF_PROXY_SERVER_IP='None',
        DISCUSSION_WAF_PROXY_SERVER_PORT='9900',
    )
    def test_connect_to_s3_error_proxy(self):
        self.course_id = 'course-v1:org+course+run'
        conn = boto.connect_s3()
        conn.create_bucket('mybucket')

        waf_proxy_enabled = True
        try:
            DiscussionS3Store()._connect_to_s3(waf_proxy_enabled)
        except Exception as err:
            self.assertIn('WAF proxy feature for Disccusion image upload is enabled, but WAF server ip or port is not configured.', err)

    @mock_s3
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        DISCUSSION_IMAGE_BACKEND_AWS_BUCKET_NAME='mybucket',
        DISCUSSION_IMAGE_BACKEND_LOCATION='/',
        DISCUSSION_ENABLE_WAF_PROXY=False,
        DISCUSSION_WAF_PROXY_SERVER_IP='100.0.0.1',
        DISCUSSION_WAF_PROXY_SERVER_PORT='9900',
    )
    def test_upload_file(self):
        self.course_id = 'course-v1:org+course+run'
        conn = boto.connect_s3()
        conn.create_bucket('mybucket')
        fp = SimpleUploadedFile('test.jpg', 'test', 'image/jpeg')
        file_name = 'test.jpg'
        downloadUrl = DiscussionS3Store().upload_file(fp, file_name, self.course_id)
        self.assertIn("https://mybucket.s3.amazonaws.com/course-v1%3Aorg%2Bcourse%2Brun/test.jpg", downloadUrl)

    @mock_s3
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        DISCUSSION_IMAGE_BACKEND_AWS_BUCKET_NAME='mybucket',
        DISCUSSION_IMAGE_BACKEND_LOCATION='/',
        DISCUSSION_ENABLE_WAF_PROXY=False,
        DISCUSSION_WAF_PROXY_SERVER_IP='100.0.0.1',
        DISCUSSION_WAF_PROXY_SERVER_PORT='9900',
    )
    @patch.object(boto, 'connect_s3')
    @raises(DiscussionFileUploadInternalError)
    def test_upload_file_file_exception(self, mock_s3):
        self.course_id = 'course-v1:org+course+run'
        mock_s3.side_effect = Exception("Oh noes")
        fp = SimpleUploadedFile('test.jpg', 'test', 'image/jpeg')
        file_name = 'test.jpg'
        DiscussionS3Store().upload_file(fp, file_name, self.course_id)

    @mock_s3
    @patch('magic.from_buffer', return_value='image/jpeg')
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        DISCUSSION_IMAGE_BACKEND_AWS_BUCKET_NAME='mybucket',
        DISCUSSION_IMAGE_BACKEND_LOCATION='/',
        DISCUSSION_ENABLE_WAF_PROXY=False,
        DISCUSSION_WAF_PROXY_SERVER_IP='100.0.0.1',
        DISCUSSION_WAF_PROXY_SERVER_PORT='9900',
        DISCUSSION_ALLOWED_UPLOAD_FILE_TYPES=['.jpg', '.jpeg', '.png', '.pdf'],
        DISCUSSION_ALLOWED_IMAGE_MIME_TYPES=['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'],
    )
    def test_store_uploaded_file_for_discussion(self, mock_store_uploaded):
        self.create_non_staff_user()
        self.course_id = 'course-v1:org+course+run'
        course_key = CourseKey.from_string(self.course_id)
        CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='disccusion-image-upload-settings',
            course_key=course_key,
            changed_by_id=self.user.id
        ).save()

        fp = SimpleUploadedFile('test.jpg', 'test', 'image/jpeg')
        file_key = 'file-upload'
        self.request = Mock(spec=HttpRequest)
        self.request.FILES = {file_key: fp}

        conn = boto.connect_s3()
        conn.create_bucket('mybucket')

        base_storage_filename = 'test'
        generate_url, stored_file_name = DiscussionS3Store().store_uploaded_file_for_discussion(self.request, file_key,
                                                                                                base_storage_filename,
                                                                                                self.course_id, cc_settings.MAX_UPLOAD_FILE_SIZE)

        self.assertIn("https://mybucket.s3.amazonaws.com/course-v1%3Aorg%2Bcourse%2Brun", generate_url)

    def test_store_uploaded_file_for_discussion_error_authority(self):
        self.create_non_staff_user()
        self.course_id = 'course-v1:org+course+run'
        course_key = CourseKey.from_string(self.course_id)
        CourseOptionalConfiguration(
            id=2,
            change_date="2015-06-18 11:02:13",
            enabled=False,
            key='disccusion-image-upload-settings',
            course_key=course_key,
            changed_by_id=self.user.id
        ).save()

        fp = SimpleUploadedFile('test.jpg', 'test', 'image/jpeg')
        file_key = 'file-upload'
        self.request = Mock(spec=HttpRequest)
        self.request.FILES = {file_key: fp}

        base_storage_filename = 'test'
        try:
            generate_url, stored_file_name = DiscussionS3Store().store_uploaded_file_for_discussion(self.request, file_key,
                                                                                                    base_storage_filename,
                                                                                                    course_key, cc_settings.MAX_UPLOAD_FILE_SIZE)
        except PermissionDenied as err:
            self.assertIn('An error has occurred with file upload, please reload this screen and upload image file again. The discussion data are erased without submit.',
                          err.message)

    def test_store_uploaded_file_for_discussion_error_file_key(self):
        self.create_non_staff_user()
        self.course_id = 'course-v1:org+course+run'
        course_key = CourseKey.from_string(self.course_id)
        fp = SimpleUploadedFile('test.jpg', 'test', 'image/jpeg')
        file_key = 'file-upload'
        CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='disccusion-image-upload-settings',
            course_key=course_key,
            changed_by_id=self.user.id
        ).save()
        self.request = Mock(spec=HttpRequest)
        self.request.FILES = {'test': fp}

        base_storage_filename = 'test'
        try:
            generate_url, stored_file_name = DiscussionS3Store().store_uploaded_file_for_discussion(self.request, file_key,
                                                                                                    base_storage_filename,
                                                                                                    self.course_id, cc_settings.MAX_UPLOAD_FILE_SIZE)
        except ValueError as err:
            self.assertIn('No file uploaded with key \'' + file_key + '\'.', err.message)

    def test_store_uploaded_file_for_discussion_error_file_extension(self):
        self.create_non_staff_user()
        self.course_id = 'course-v1:org+course+run'
        course_key = CourseKey.from_string(self.course_id)
        fp = SimpleUploadedFile('test.txt', 'test', 'text/plain')
        file_key = 'file-upload'
        CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='disccusion-image-upload-settings',
            course_key=course_key,
            changed_by_id=self.user.id
        ).save()
        self.request = Mock(spec=HttpRequest)
        self.request.FILES = {file_key: fp}

        base_storage_filename = 'test'
        try:
            generate_url, stored_file_name = DiscussionS3Store().store_uploaded_file_for_discussion(self.request, file_key,
                                                                                                    base_storage_filename,
                                                                                                    self.course_id, cc_settings.MAX_UPLOAD_FILE_SIZE)
        except PermissionDenied as err:
            self.assertIn(u'The file ending in', err.message)

    @override_settings(
        DISCUSSION_ALLOWED_UPLOAD_FILE_TYPES=['.jpg', '.jpeg', '.png', '.pdf'],
        DISCUSSION_ALLOWED_IMAGE_MIME_TYPES=['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'],
    )
    def test_store_uploaded_file_for_discussion_error_image_file(self):
        self.create_non_staff_user()
        self.course_id = 'course-v1:org+course+run'
        course_key = CourseKey.from_string(self.course_id)
        fp = SimpleUploadedFile('test.jpg', 'test', 'image/jpeg')
        file_key = 'file-upload'
        CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='disccusion-image-upload-settings',
            course_key=course_key,
            changed_by_id=self.user.id
        ).save()
        self.request = Mock(spec=HttpRequest)
        self.request.FILES = {file_key: fp}

        base_storage_filename = 'test'
        try:
            generate_url, stored_file_name = DiscussionS3Store().store_uploaded_file_for_discussion(self.request, file_key,
                                                                                                    base_storage_filename,
                                                                                                    self.course_id, cc_settings.MAX_UPLOAD_FILE_SIZE)
        except PermissionDenied as err:
            self.assertIn('An invalid file, please upload valid image file.', err.message)

    @mock_s3
    @patch('magic.from_buffer', return_value='image/jpeg')
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        DISCUSSION_IMAGE_BACKEND_AWS_BUCKET_NAME='mybucket',
        DISCUSSION_IMAGE_BACKEND_LOCATION='/',
        DISCUSSION_ENABLE_WAF_PROXY=False,
        DISCUSSION_WAF_PROXY_SERVER_IP='100.0.0.1',
        DISCUSSION_WAF_PROXY_SERVER_PORT='9900',
        DISCUSSION_ALLOWED_UPLOAD_FILE_TYPES=['.jpg', '.jpeg', '.png', '.pdf'],
        DISCUSSION_ALLOWED_IMAGE_MIME_TYPES=['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'],
    )
    def test_store_uploaded_file_for_discussion_error_max_size(self, mock_store_uploaded):
        self.create_non_staff_user()
        self.course_id = 'course-v1:org+course+run'
        course_key = CourseKey.from_string(self.course_id)
        fp = SimpleUploadedFile('test.jpg', 'test', 'image/jpeg')
        file_key = 'file-upload'
        CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='disccusion-image-upload-settings',
            course_key=course_key,
            changed_by_id=self.user.id
        ).save()
        self.request = Mock(spec=HttpRequest)
        self.request.FILES = {file_key: fp}

        base_storage_filename = 'test'
        try:
            generate_url, stored_file_name = DiscussionS3Store().store_uploaded_file_for_discussion(self.request, file_key,
                                                                                                    base_storage_filename,
                                                                                                    self.course_id, 1)
        except PermissionDenied as err:
            self.assertIn('Maximum upload file size', err.message)

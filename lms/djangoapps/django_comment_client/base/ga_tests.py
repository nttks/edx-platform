"""Tests for django comment client views."""
import boto
from mock import patch
from moto import mock_s3

from django_comment_client.base import views
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import RequestFactory
from django.test.utils import override_settings

from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


class FileUploadTestCase(ModuleStoreTestCase):

    USERNAME = u"user"
    PASSWORD = "password"

    @mock_s3
    @override_settings(
        AWS_ACCESS_KEY_ID='foobar',
        AWS_SECRET_ACCESS_KEY='bizbaz',
        DISCUSSION_IMAGE_BACKEND_AWS_BUCKET_NAME='mybucket',
        DISCUSSION_IMAGE_BACKEND_LOCATION='/',
        DISCUSSION_ENABLE_WAF_PROXY=False,
        DISCUSSION_WAF_PROXY_SERVER_IP='100.0.0.1',
        DISCUSSION_WAF_PROXY_SERVER_PORT='9900',
        DISCUSSION_WAF_VIRUS_DETECTION_KEYWORD='VIRUS DETECTION'
    )
    @patch('magic.from_buffer', return_value='image/jpeg')
    def test_upload(self, mock_magic):

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
        self.request_factory = RequestFactory()
        self.user = UserFactory.create(username=self.USERNAME, password=self.PASSWORD)
        self.request = self.request_factory.post("foo")
        self.request.user = self.user
        self.request.FILES[file_key] = fp

        conn = boto.connect_s3()
        conn.create_bucket('mybucket')

        responses = views.upload(self.request, course_key)
        self.assertEqual(responses.status_code, 200)

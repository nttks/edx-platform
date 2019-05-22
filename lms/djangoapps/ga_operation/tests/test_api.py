# -*- coding: utf-8 -*-
import ddt
import json
from mock import ANY, MagicMock, patch
from StringIO import StringIO

from django.conf import settings
from django.core.urlresolvers import reverse as django_reverse
from django.test.utils import override_settings

from certificates.tests.factories import GeneratedCertificateFactory
from courseware.tests.factories import GlobalStaffFactory
from courseware.tests.helpers import LoginEnrollmentTestCase
from ga_operation.views.api import RESPONSE_FIELD_ID
from opaque_keys.edx.keys import CourseKey
from pdfgen.certificate import CertPDFException, CertPDFUserNotFoundException
from student.tests.factories import UserFactory, CourseAccessRoleFactory


GA_OPERATION_GET_ENDPOINTS = [
    'discussion_data_download',
    'past_graduates_info',
    'last_login_info',
]

GA_OPERATION_POST_ENDPOINTS = [
    'move_videos',
    'mutual_grading_report',
    'discussion_data',
    'aggregate_g1528',
]

GA_OPERATION_POST_ENDPOINTS_CERTS = [
    'confirm_certs_template',
    'upload_certs_template',
    'create_certs',
    'create_certs_meeting',
    'publish_certs',
]


def reverse(endpoint, args=None, kwargs=None, is_operation_endpoint=True):
    """
    Simple wrapper of Django's reverse that first ensures that we have declared
    each endpoint under test.

    Arguments:
        args: The args to be passed through to reverse.
        endpoint: The endpoint to be passed through to reverse.
        kwargs: The kwargs to be passed through to reverse.
        is_operation_endpoint: True if this is an ga_operation endpoint
            that must be declared in the GA_OPERATION_GET_ENDPOINTS or
            GA_OPERATION_POST_ENDPOINTS sets, or false otherwise.

    Returns:
        The return of Django's reverse function

    """
    is_endpoint_declared = endpoint in GA_OPERATION_GET_ENDPOINTS or endpoint in GA_OPERATION_POST_ENDPOINTS or endpoint in GA_OPERATION_POST_ENDPOINTS_CERTS
    if is_operation_endpoint and is_endpoint_declared is False:
        # Verify that all endpoints are declared so we can ensure they are
        # properly validated elsewhere.
        raise ValueError("The endpoint {} must be declared in ENDPOINTS before use.".format(endpoint))
    return django_reverse('ga_operation_api:' + endpoint, args=args, kwargs=kwargs)


@ddt.ddt
class EndpointMethodTest(LoginEnrollmentTestCase):

    def setUp(self):
        super(EndpointMethodTest, self).setUp()
        global_user = GlobalStaffFactory()
        self.client.login(username=global_user.username, password='test')

    @ddt.data(*GA_OPERATION_POST_ENDPOINTS)
    def test_endpoints_reject_get(self, endpoint):
        """
        Tests that POST endpoints are rejected with 405 when using GET.
        """
        url = reverse(endpoint)
        response = self.client.get(url)

        self.assertEqual(
            response.status_code, 405,
            "Endpoint {} returned status code {} instead of a 405. It should not allow GET.".format(
                endpoint, response.status_code
            )
        )

    @ddt.data(*GA_OPERATION_POST_ENDPOINTS_CERTS)
    def test_endpoints_certs_reject_get(self, endpoint):
        """
        Tests that POST endpoints are rejected with 405 when using GET.
        """
        url = reverse(endpoint)
        response = self.client.get(url)

        self.assertEqual(
            response.status_code, 405,
            "Endpoint {} returned status code {} instead of a 405. It should not allow GET.".format(
                endpoint, response.status_code
            )
        )


@ddt.ddt
class EndpointPermissionTest(LoginEnrollmentTestCase):

    def setUp(self):
        super(EndpointPermissionTest, self).setUp()
        self.setup_user()

    @ddt.data(*GA_OPERATION_POST_ENDPOINTS)
    def test_post_endpoints_reject(self, endpoint):
        """
        Tests that POST endpoints are rejected with 403 when accessed by non global staff.
        """
        url = reverse(endpoint)
        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    @ddt.data(*GA_OPERATION_POST_ENDPOINTS_CERTS)
    def test_post_certs_endpoints_reject(self, endpoint):
        """
        Tests that POST endpoints are rejected with 403 when accessed by non global staff or non studio staff.
        """
        url = reverse(endpoint)
        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    @ddt.data(*GA_OPERATION_GET_ENDPOINTS)
    def test_get_endpoints_reject(self, endpoint):
        """
        Tests that GET endpoints are rejected with 403 when accessed by non global staff.
        """
        url = reverse(endpoint)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    @ddt.data(*GA_OPERATION_POST_ENDPOINTS)
    def test_post_endpoints_reject_certs(self, endpoint):
        """
        Tests that GET endpoints are rejected with 403 when accessed by non global staff.
        """
        CourseAccessRoleFactory(course_id=None, user=self.user, role='instructor')
        url = reverse(endpoint)
        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    @ddt.data(*GA_OPERATION_POST_ENDPOINTS_CERTS)
    def test_post_certs_endpoints_reject_certs(self, endpoint):
        """
        Tests that GET endpoints are rejected with 403 when accessed by non global staff.
        """
        url = reverse(endpoint)
        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    @ddt.data(*GA_OPERATION_GET_ENDPOINTS)
    def test_get_endpoints_reject_certs(self, endpoint):
        """
        Tests that GET endpoints are rejected with 403 when accessed by non global staff.
        """
        CourseAccessRoleFactory(course_id=None, user=self.user, role='instructor')
        url = reverse(endpoint)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)


class ApiTestMixin(object):

    def test_no_course_id(self):
        _url = reverse(self.url)
        response = self.client.post(_url)

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)
        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['course_id'], [u'このフィールドは必須です。'])

    def test_invalid_course_id(self):
        _url = reverse(self.url)
        response = self.client.post(_url, {'course_id': 'invalid-course-id'})

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)
        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['course_id'], [u'講座IDの書式が不正です。'])


class ApiTestBase(LoginEnrollmentTestCase):

    def setUp(self):
        super(ApiTestBase, self).setUp()
        self.user = GlobalStaffFactory()
        self.client.login(username=self.user.username, password='test')

        self.exception = Exception('error')

    @property
    def url(self):
        raise NotImplementedError()

    def _mock_key(self, name, url=None):
        mock_key = MagicMock()
        mock_key.name = name
        mock_key.generate_url.return_value = url
        return mock_key

    def _assert_audit_log(self, logger):
        logger.info.assert_called_with('path:{}, user.id:{} End.'.format(reverse(self.url), self.user.id))

    def _assert_success_message(self, content, message):
        self.assertEqual(content[RESPONSE_FIELD_ID], message)

    def _assert_exception(self, response, logger):
        self.assertEqual(response.status_code, 500)
        content = json.loads(response.content)
        self.assertEqual(content[RESPONSE_FIELD_ID], 'error')
        logger.exception.assert_called_with('Caught the exception: Exception')


@override_settings(PDFGEN_BASE_BUCKET_NAME='test_bucket')
@ddt.ddt
class ConfirmCertsTemplateTest(ApiTestBase, ApiTestMixin):

    def setUp(self):
        super(ConfirmCertsTemplateTest, self).setUp()
        self.mock_key_1 = self._mock_key('name1', 'http://url1')
        self.mock_key_2 = self._mock_key('name2', 'http://url2')

    def _assert_template(self, template, label, url, name):
        self.assertEqual(template['label'], label)
        self.assertEqual(template['url'], url)
        self.assertEqual(template['name'], name)

    @property
    def url(self):
        return 'confirm_certs_template'

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.handle_file_from_s3')
    @ddt.data(
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    )
    @ddt.unpack
    def test_success(self, has_normal, has_verified, mock_handle_file_from_s3, mock_log):
        mock_handle_file_from_s3.side_effect = [
            self.mock_key_1 if has_normal else None,
            self.mock_key_2 if has_verified else None,
        ]

        _url = reverse(self.url)
        response = self.client.post(_url, {'course_id': 'course-v1:org+course+run'})

        self.assertEqual(response.status_code, 200)
        templates = json.loads(response.content)['templates']
        self.assertEqual(len(templates), int(has_normal) + int(has_verified))

        if has_normal:
            self._assert_template(templates[0], u'通常テンプレート', 'http://url1', 'name1')
        if has_verified:
            index = 1 if has_normal else 0
            self._assert_template(templates[index], u'対面学習テンプレート', 'http://url2', 'name2')

        mock_handle_file_from_s3.assert_any_call('org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
        mock_handle_file_from_s3.assert_any_call('verified-org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
        self._assert_audit_log(mock_log)

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.handle_file_from_s3')
    def test_error(self, mock_handle_file_from_s3, mock_log):
        mock_handle_file_from_s3.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
        })
        self._assert_exception(response, mock_log)
        self._assert_audit_log(mock_log)


@override_settings(PDFGEN_BASE_BUCKET_NAME='test_bucket')
@ddt.ddt
class UploadCertsTemplateTest(ApiTestBase, ApiTestMixin):

    def setUp(self):
        super(UploadCertsTemplateTest, self).setUp()
        self.cert_pdf_tmpl = StringIO('cert_pdf_tmpl')
        self.cert_pdf_meeting_tmpl = StringIO('cert_pdf_meeting_tmpl')

    @property
    def url(self):
        return 'upload_certs_template'

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.forms.upload_certs_template_form.handle_uploaded_received_file_to_s3')
    @ddt.data(
        (True, True),
        (True, False),
        (False, True),
    )
    @ddt.unpack
    def test_success(self, has_normal, has_verified, mock_handle_uploaded_received_file_to_s3, mock_log):
        _url = reverse(self.url)
        data = {'course_id': 'course-v1:org+course+run', }
        if has_normal:
            data['cert_pdf_tmpl'] = self.cert_pdf_tmpl
        if has_verified:
            data['cert_pdf_meeting_tmpl'] = self.cert_pdf_meeting_tmpl
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        if has_normal and has_verified:
            mock_handle_uploaded_received_file_to_s3.assert_any_call(ANY, 'org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
            mock_handle_uploaded_received_file_to_s3.assert_any_call(ANY, 'verified-org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
        elif has_normal:
            mock_handle_uploaded_received_file_to_s3.assert_called_once_with(ANY, 'org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
        elif has_verified:
            mock_handle_uploaded_received_file_to_s3.assert_called_once_with(ANY, 'verified-org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
        self._assert_success_message(content, u'テンプレートのアップロードが完了しました。')
        self._assert_audit_log(mock_log)

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.forms.upload_certs_template_form.handle_uploaded_received_file_to_s3')
    def test_no_files(self, mock_handle_uploaded_received_file_to_s3, mock_log):
        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)
        error_message = u'通常テンプレートと対面学習テンプレートのどちらか一方または両方を選択してください。'
        self.assertEqual(content['cert_pdf_tmpl_error'], error_message)

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.forms.upload_certs_template_form.handle_uploaded_received_file_to_s3')
    def test_error(self, mock_handle_uploaded_received_file_to_s3, mock_log):
        mock_handle_uploaded_received_file_to_s3.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'cert_pdf_tmpl': self.cert_pdf_tmpl,
        })
        self._assert_exception(response, mock_log)
        self._assert_audit_log(mock_log)


@ddt.ddt
@override_settings(GA_OPERATION_VALID_DOMAINS_LIST=['example.com'])
class CreateCertsTest(ApiTestBase, ApiTestMixin):

    @property
    def url(self):
        return 'create_certs'

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.create_certs_task')
    @ddt.data(None, ['user1', 'user2'])
    def test_success(self, student_ids, mock_create_certs_task, mock_log):
        _url = reverse(self.url)
        data = {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        }
        if student_ids:
            data['student_ids'] = ','.join(student_ids)
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        mock_create_certs_task.delay.assert_called_once_with(
            course_id='course-v1:org+course+run',
            email='test@example.com',
            student_ids=student_ids if student_ids else []
        )
        self._assert_success_message(
            content, u'修了証の作成（対面なし）を開始しました。\n処理が完了したらtest@example.comのアドレスに処理の完了通知が来ます。'
        )
        self._assert_audit_log(mock_log)

    @patch('ga_operation.views.api.create_certs_task')
    def test_no_email(self, mock_create_certs_task):
        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)

        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['email'], [u'このフィールドは必須です。'])

        mock_create_certs_task.assert_not_called()

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.create_certs_task')
    def test_error(self, mock_create_certs_task, mock_utils_log):
        mock_create_certs_task.delay.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        })
        self._assert_exception(response, mock_utils_log)
        self._assert_audit_log(mock_utils_log)


@override_settings(GA_OPERATION_VALID_DOMAINS_LIST=['example.com'])
class CreateCertsMeetingTest(ApiTestBase, ApiTestMixin):

    @property
    def url(self):
        return 'create_certs_meeting'

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.create_certs_task')
    def test_success(self, mock_create_certs_task, mock_log):
        _url = reverse(self.url)
        data = {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
            'student_ids': ','.join(['user1', 'user2'])
        }
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        mock_create_certs_task.delay.assert_called_once_with(
            course_id='course-v1:org+course+run',
            email='test@example.com',
            student_ids=['user1', 'user2'],
            prefix='verified-'
        )
        self._assert_success_message(
            content, u'修了証の作成（対面あり）を開始しました。\n処理が完了したらtest@example.comのアドレスに処理の完了通知が来ます。'
        )
        self._assert_audit_log(mock_log)

    @patch('ga_operation.views.api.create_certs_task')
    def test_no_email(self, mock_create_certs_task):
        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'student_ids': ','.join(['user1', 'user2'])
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)

        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['email'], [u'このフィールドは必須です。'])

        mock_create_certs_task.assert_not_called()

    @patch('ga_operation.views.api.create_certs_task')
    def test_no_student_ids(self, mock_create_certs_task):
        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)

        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['student_ids'], [u'このフィールドは必須です。'])

        mock_create_certs_task.assert_not_called()

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.create_certs_task')
    def test_error(self, mock_create_certs_task, mock_utils_log):
        mock_create_certs_task.delay.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
            'student_ids': ','.join(['user1', 'user2'])
        })
        self._assert_exception(response, mock_utils_log)
        self._assert_audit_log(mock_utils_log)


@ddt.ddt
@override_settings(GA_OPERATION_MONGO={
    "comment": {
        "collection": "contents",
        "db": "cs_comments_service",
        "host": ["localhost"],
        "password": "password",
        "port": 27017,
        "user": "cs_comments_service"
    }
})
class DiscussionDataDownloadTest(ApiTestBase):

    @property
    def url(self):
        return 'discussion_data_download'

    @patch('ga_operation.views.api.log')
    def test_success(self, mock_log):

        _url = reverse(self.url)
        data = {
            'course_id': 'course-v1:org+course+run',
        }
        response = self.client.get(_url, data)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        # nodate case
        # If you want to do with data, rewrite it
        self.assertEqual(content,[])

        mock_log.exception.assert_not_called()
        self._assert_audit_log(mock_log)

    @patch('ga_operation.views.api.log')
    def test_no_course_id(self, mock_log):
        _url = reverse(self.url)
        response = self.client.get(_url)

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)
        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['course_id'], [u'このフィールドは必須です。'])

        mock_log.info.assert_called_with({'course_id': [u'このフィールドは必須です。'], 'right_content_response':u'入力したフォームの内容が不正です。'})
        mock_log.exception.assert_not_called()

    @patch('ga_operation.views.api.log')
    @patch('ga_operation.views.api.CommentStore')
    def test_error(self, mock_CommentStore, mock_log):
        mock_CommentStore().get_documents.side_effect = self.exception

        _url = reverse(self.url)
        data = {
            'course_id': 'course-v1:org+course+run',
        }

        response = self.client.get(_url, data)

        self.assertEqual(response.status_code, 400)
        mock_log.exception.assert_called_with('Caught the exception: Exception')
        self._assert_audit_log(mock_log)


class CertsApiTestBase(ApiTestBase):

    def setUp(self):
        super(CertsApiTestBase, self).setup_user()
        CourseAccessRoleFactory(course_id='course-v1:org+course+run', user=self.user, role='instructor')
        self.client.login(username=self.user.username, password='test')

        self.exception = Exception('error')


@override_settings(PDFGEN_BASE_BUCKET_NAME='test_bucket')
@ddt.ddt
class CertsConfirmCertsTemplateTest(CertsApiTestBase, ApiTestMixin):

    def setUp(self):
        super(CertsConfirmCertsTemplateTest, self).setUp()
        self.mock_key_1 = self._mock_key('name1', 'http://url1')
        self.mock_key_2 = self._mock_key('name2', 'http://url2')

    def _assert_template(self, template, label, url, name):
        self.assertEqual(template['label'], label)
        self.assertEqual(template['url'], url)
        self.assertEqual(template['name'], name)

    @property
    def url(self):
        return 'confirm_certs_template'

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.handle_file_from_s3')
    @ddt.data(
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    )
    @ddt.unpack
    def test_success(self, has_normal, has_verified, mock_handle_file_from_s3, mock_log):
        mock_handle_file_from_s3.side_effect = [
            self.mock_key_1 if has_normal else None,
            self.mock_key_2 if has_verified else None,
        ]

        _url = reverse(self.url)
        response = self.client.post(_url, {'course_id': 'course-v1:org+course+run'})

        self.assertEqual(response.status_code, 200)
        templates = json.loads(response.content)['templates']
        self.assertEqual(len(templates), int(has_normal) + int(has_verified))

        if has_normal:
            self._assert_template(templates[0], u'通常テンプレート', 'http://url1', 'name1')
        if has_verified:
            index = 1 if has_normal else 0
            self._assert_template(templates[index], u'対面学習テンプレート', 'http://url2', 'name2')

        mock_handle_file_from_s3.assert_any_call('org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
        mock_handle_file_from_s3.assert_any_call('verified-org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
        self._assert_audit_log(mock_log)

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.handle_file_from_s3')
    def test_error(self, mock_handle_file_from_s3, mock_log):
        mock_handle_file_from_s3.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
        })
        self._assert_exception(response, mock_log)
        self._assert_audit_log(mock_log)


@override_settings(PDFGEN_BASE_BUCKET_NAME='test_bucket')
@ddt.ddt
class CertsUploadCertsTemplateTest(CertsApiTestBase, ApiTestMixin):

    def setUp(self):
        super(CertsUploadCertsTemplateTest, self).setUp()
        self.cert_pdf_tmpl = StringIO('cert_pdf_tmpl')
        self.cert_pdf_meeting_tmpl = StringIO('cert_pdf_meeting_tmpl')

    @property
    def url(self):
        return 'upload_certs_template'

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.forms.upload_certs_template_form.handle_uploaded_received_file_to_s3')
    @ddt.data(
        (True, True),
        (True, False),
        (False, True),
    )
    @ddt.unpack
    def test_success(self, has_normal, has_verified, mock_handle_uploaded_received_file_to_s3, mock_log):
        _url = reverse(self.url)
        data = {'course_id': 'course-v1:org+course+run', }
        if has_normal:
            data['cert_pdf_tmpl'] = self.cert_pdf_tmpl
        if has_verified:
            data['cert_pdf_meeting_tmpl'] = self.cert_pdf_meeting_tmpl
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        if has_normal and has_verified:
            mock_handle_uploaded_received_file_to_s3.assert_any_call(ANY, 'org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
            mock_handle_uploaded_received_file_to_s3.assert_any_call(ANY, 'verified-org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
        elif has_normal:
            mock_handle_uploaded_received_file_to_s3.assert_called_once_with(ANY, 'org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
        elif has_verified:
            mock_handle_uploaded_received_file_to_s3.assert_called_once_with(ANY, 'verified-org-course-run.pdf', settings.PDFGEN_BASE_BUCKET_NAME)
        self._assert_success_message(content, u'テンプレートのアップロードが完了しました。')
        self._assert_audit_log(mock_log)

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.forms.upload_certs_template_form.handle_uploaded_received_file_to_s3')
    def test_no_files(self, mock_handle_uploaded_received_file_to_s3, mock_log):
        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)
        error_message = u'通常テンプレートと対面学習テンプレートのどちらか一方または両方を選択してください。'
        self.assertEqual(content['cert_pdf_tmpl_error'], error_message)

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.forms.upload_certs_template_form.handle_uploaded_received_file_to_s3')
    def test_error(self, mock_handle_uploaded_received_file_to_s3, mock_log):
        mock_handle_uploaded_received_file_to_s3.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'cert_pdf_tmpl': self.cert_pdf_tmpl,
        })
        self._assert_exception(response, mock_log)
        self._assert_audit_log(mock_log)


@ddt.ddt
@override_settings(GA_OPERATION_VALID_DOMAINS_LIST=['example.com'])
class CertsCreateCertsTest(CertsApiTestBase, ApiTestMixin):

    @property
    def url(self):
        return 'create_certs'

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.create_certs_task')
    @ddt.data(None, ['user1', 'user2'])
    def test_success(self, student_ids, mock_create_certs_task, mock_log):
        _url = reverse(self.url)
        data = {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        }
        if student_ids:
            data['student_ids'] = ','.join(student_ids)
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        mock_create_certs_task.delay.assert_called_once_with(
            course_id='course-v1:org+course+run',
            email='test@example.com',
            student_ids=student_ids if student_ids else []
        )
        self._assert_success_message(
            content, u'修了証の作成（対面なし）を開始しました。\n処理が完了したらtest@example.comのアドレスに処理の完了通知が来ます。'
        )
        self._assert_audit_log(mock_log)

    @patch('ga_operation.views.api.create_certs_task')
    def test_no_email(self, mock_create_certs_task):
        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)

        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['email'], [u'このフィールドは必須です。'])

        mock_create_certs_task.assert_not_called()

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.create_certs_task')
    def test_error(self, mock_create_certs_task, mock_utils_log):
        mock_create_certs_task.delay.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        })
        self._assert_exception(response, mock_utils_log)
        self._assert_audit_log(mock_utils_log)


@override_settings(GA_OPERATION_VALID_DOMAINS_LIST=['example.com'])
class CertsCreateCertsMeetingTest(CertsApiTestBase, ApiTestMixin):

    @property
    def url(self):
        return 'create_certs_meeting'

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.create_certs_task')
    def test_success(self, mock_create_certs_task, mock_log):
        _url = reverse(self.url)
        data = {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
            'student_ids': ','.join(['user1', 'user2'])
        }
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        mock_create_certs_task.delay.assert_called_once_with(
            course_id='course-v1:org+course+run',
            email='test@example.com',
            student_ids=['user1', 'user2'],
            prefix='verified-'
        )
        self._assert_success_message(
            content, u'修了証の作成（対面あり）を開始しました。\n処理が完了したらtest@example.comのアドレスに処理の完了通知が来ます。'
        )
        self._assert_audit_log(mock_log)

    @patch('ga_operation.views.api.create_certs_task')
    def test_no_email(self, mock_create_certs_task):
        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'student_ids': ','.join(['user1', 'user2'])
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)

        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['email'], [u'このフィールドは必須です。'])

        mock_create_certs_task.assert_not_called()

    @patch('ga_operation.views.api.create_certs_task')
    def test_no_student_ids(self, mock_create_certs_task):
        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)

        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['student_ids'], [u'このフィールドは必須です。'])

        mock_create_certs_task.assert_not_called()

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('ga_operation.views.api.create_certs_task')
    def test_error(self, mock_create_certs_task, mock_utils_log):
        mock_create_certs_task.delay.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
            'student_ids': ','.join(['user1', 'user2'])
        })
        self._assert_exception(response, mock_utils_log)
        self._assert_audit_log(mock_utils_log)


@ddt.ddt
@override_settings(GA_OPERATION_MONGO={
    "comment": {
        "collection": "contents",
        "db": "cs_comments_service",
        "host": ["localhost"],
        "password": "password",
        "port": 27017,
        "user": "cs_comments_service"
    }
})
class CertsDiscussionDataDownloadTest(CertsApiTestBase):

    @property
    def url(self):
        return 'discussion_data_download'

    @patch('ga_operation.views.api.log')
    def test_success(self, mock_log):

        _url = reverse(self.url)
        data = {
            'course_id': 'course-v1:org+course+run',
        }
        response = self.client.get(_url, data)
        self.assertEqual(response.status_code, 403)

    @patch('ga_operation.views.api.log')
    def test_no_course_id(self, mock_log):
        _url = reverse(self.url)
        response = self.client.get(_url)

        self.assertEqual(response.status_code, 403)

    @patch('ga_operation.views.api.log')
    @patch('ga_operation.views.api.CommentStore')
    def test_error(self, mock_CommentStore, mock_log):
        mock_CommentStore().get_documents.side_effect = self.exception

        _url = reverse(self.url)
        data = {
            'course_id': 'course-v1:org+course+run',
        }

        response = self.client.get(_url, data)

        self.assertEqual(response.status_code, 403)

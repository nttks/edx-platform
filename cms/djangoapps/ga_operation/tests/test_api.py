# -*- coding: utf-8 -*-
import ddt
import json
from mock import MagicMock, patch

from django.core.urlresolvers import reverse as django_reverse
from django.test.utils import override_settings
from django.utils.crypto import get_random_string

from biz.djangoapps.ga_contract.tests.factories import ContractFactory, ContractDetailFactory
from biz.djangoapps.ga_organization.tests.factories import OrganizationFactory
from contentstore.tests.utils import CourseTestCase
from ga_operation.views.api import RESPONSE_FIELD_ID
from opaque_keys.edx.keys import CourseKey
from student.tests.factories import CourseEnrollmentFactory, UserFactory

GA_OPERATION_POST_ENDPOINTS = [
    'delete_course',
    'delete_library',
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
    is_endpoint_declared = endpoint in GA_OPERATION_POST_ENDPOINTS
    if is_operation_endpoint and is_endpoint_declared is False:
        # Verify that all endpoints are declared so we can ensure they are
        # properly validated elsewhere.
        raise ValueError("The endpoint {} must be declared in ENDPOINTS before use.".format(endpoint))
    return django_reverse('ga_operation_api:' + endpoint, args=args, kwargs=kwargs)


@ddt.ddt
class EndpointMethodTest(CourseTestCase):
    def setUp(self):
        super(EndpointMethodTest, self).setUp()

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


@ddt.ddt
class EndpointPermissionTest(CourseTestCase):
    def setUp(self):
        super(EndpointPermissionTest, self).setUp()

    @ddt.data(*GA_OPERATION_POST_ENDPOINTS)
    def test_post_endpoints_reject(self, endpoint):
        """
        Tests that POST endpoints are rejected with 403 when accessed by non global staff.
        """
        url = reverse(endpoint)
        client, _ = self.create_non_staff_authed_user_client()
        response = client.post(url)

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


class ApiTestBase(CourseTestCase):
    def setUp(self):
        super(ApiTestBase, self).setUp()
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


@ddt.ddt
@override_settings(GA_OPERATION_VALID_DOMAINS_LIST=['example.com'])
class DeleteCourseTest(ApiTestBase, ApiTestMixin):
    @property
    def url(self):
        return 'delete_course'

    @staticmethod
    def _create_contract_detail(course_id):
        def _create_contract():
            org = OrganizationFactory.create(
                org_name='docomo gacco',
                org_code='gacco',
                creator_org_id=1,  # It means the first of Organization
                created_by=UserFactory.create(),
            )
            return ContractFactory.create(
                contract_name=get_random_string(8),
                contract_type='PF',
                invitation_code=get_random_string(8),
                contractor_organization=org,
                owner_organization=org,
                created_by=UserFactory.create(),
            )

        return [ContractDetailFactory.create(
            contract=_create_contract(), course_id=course_id
        ) for _ in range(3)]

    @staticmethod
    def _create_enrolled_users(course_id):
        course_key = CourseKey.from_string(course_id)
        enrollments = [CourseEnrollmentFactory.create(
            user=UserFactory.create(), course_id=course_key
        ) for _ in range(3)]
        return [e.user for e in enrollments]

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('cms.djangoapps.ga_operation.views.api.delete_course_task')
    def test_success(self, mock_delete_course_task, mock_log):
        _url = reverse(self.url)
        data = {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        }
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        mock_delete_course_task.delay.assert_called_once_with(
            course_id='course-v1:org+course+run',
            email='test@example.com',
        )
        self._assert_success_message(
            content, u'講座削除処理を開始しました。\n処理が終了次第、test@example.comのアドレスに完了通知が届きます。'
        )
        self._assert_audit_log(mock_log)

    @patch('cms.djangoapps.ga_operation.views.api.delete_course_task')
    def test_no_email(self, mock_delete_course_task):
        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)

        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['email'], [u'This field is required.'])

        mock_delete_course_task.assert_not_called()

    @patch('cms.djangoapps.ga_operation.views.api.delete_course_task')
    def test_already_registered_to_the_contract(self, mock_delete_course_task):
        data = {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        }
        details = self._create_contract_detail(data['course_id'])

        _url = reverse(self.url)
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)
        self.assertEqual(
            content[RESPONSE_FIELD_ID],
            u"・以下の法人契約がこの講座を登録しているため、削除できません。\n"
            + u"\n".join([u"- " + d.contract.contract_name for d in details])
            + u"\n\n"
        )
        mock_delete_course_task.assert_not_called()

    @patch('cms.djangoapps.ga_operation.views.api.delete_course_task')
    def test_already_enrolled_by_user(self, mock_delete_course_task):
        data = {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        }
        users = self._create_enrolled_users(data['course_id'])

        _url = reverse(self.url)
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)
        self.assertEqual(
            content[RESPONSE_FIELD_ID],
            u"・以下のユーザーがこの講座を受講登録しているため、削除できません。\n"
            + u",".join([u.username for u in users])
        )
        mock_delete_course_task.assert_not_called()

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('cms.djangoapps.ga_operation.views.api.delete_course_task')
    def test_error(self, mock_delete_course_task, mock_log):
        mock_delete_course_task.delay.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        })
        self._assert_exception(response, mock_log)
        self._assert_audit_log(mock_log)


@ddt.ddt
@override_settings(GA_OPERATION_VALID_DOMAINS_LIST=['example.com'])
class DeleteLibraryTest(ApiTestBase, ApiTestMixin):
    @property
    def url(self):
        return 'delete_library'

    @staticmethod
    def _create_contract_detail(course_id):
        def _create_contract():
            org = OrganizationFactory.create(
                org_name='docomo gacco',
                org_code='gacco',
                creator_org_id=1,  # It means the first of Organization
                created_by=UserFactory.create(),
            )
            return ContractFactory.create(
                contract_name=get_random_string(8),
                contract_type='PF',
                invitation_code=get_random_string(8),
                contractor_organization=org,
                owner_organization=org,
                created_by=UserFactory.create(),
            )

        return [ContractDetailFactory.create(
            contract=_create_contract(), course_id=course_id
        ) for _ in range(3)]

    @staticmethod
    def _create_enrolled_users(course_id):
        course_key = CourseKey.from_string(course_id)
        enrollments = [CourseEnrollmentFactory.create(
            user=UserFactory.create(), course_id=course_key
        ) for _ in range(3)]
        return [e.user for e in enrollments]

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('cms.djangoapps.ga_operation.views.api.delete_library_task')
    def test_success(self, mock_delete_library_task, mock_log):
        _url = reverse(self.url)
        data = {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        }
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        mock_delete_library_task.delay.assert_called_once_with(
            library_id='course-v1:org+course+run',
            email='test@example.com',
        )
        self._assert_success_message(
            content, u'ライブラリ削除処理を開始しました。\n処理が終了次第、test@example.comのアドレスに完了通知が届きます。'
        )
        self._assert_audit_log(mock_log)

    @patch('cms.djangoapps.ga_operation.views.api.delete_library_task')
    def test_no_email(self, mock_delete_library_task):
        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)

        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['email'], [u'This field is required.'])

        mock_delete_library_task.assert_not_called()

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('cms.djangoapps.ga_operation.views.api.delete_library_task')
    def test_error(self, mock_delete_library_task, mock_log):
        mock_delete_library_task.delay.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'course_id': 'course-v1:org+course+run',
            'email': 'test@example.com',
        })
        self._assert_exception(response, mock_log)
        self._assert_audit_log(mock_log)

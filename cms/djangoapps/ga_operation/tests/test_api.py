# -*- coding: utf-8 -*-
import ddt
import json
from mock import MagicMock, patch

from django.core.urlresolvers import reverse as django_reverse
from django.test.utils import override_settings
from django.utils.crypto import get_random_string

from biz.djangoapps.ga_contract.tests.factories import ContractFactory, ContractDetailFactory
from biz.djangoapps.ga_organization.tests.factories import OrganizationFactory
from contentstore.tests.utils import CourseTestCase, parse_json
from contentstore.utils import reverse_course_url
from ga_operation.views.api import RESPONSE_FIELD_ID
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import LibraryLocator
from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration
from student.tests.factories import CourseEnrollmentFactory, UserFactory
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.factories import ItemFactory

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


class ApiDeleteCourseTestMixin(object):
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


class ApiDeleteLibraryTestMixin(object):
    def test_no_library_id(self):
        _url = reverse(self.url)
        response = self.client.post(_url)

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)
        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['library_id'], [u'このフィールドは必須です。'])

    def test_invalid_library_id(self):
        _url = reverse(self.url)
        response = self.client.post(_url, {'library_id': 'invalid-course-id'})

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)
        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['library_id'], [u'ライブラリIDの書式が不正です。'])

    def _setting_library_option(self, course):
        CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='library-for-settings',
            course_key=course.id,
            changed_by_id=self.user.id
        ).save()

    def _create_library(self, course, org='org', library='lib', display_name='Test Library'):
        """
        Helper method used to create a library. Uses the REST API.
        """
        lib_url = reverse_course_url('course_library_handler', course.id)

        response = self.client.ajax_post(lib_url, {
            'org': org,
            'library': library,
            'display_name': display_name,
        })
        self.assertEqual(response.status_code, 200)
        lib_info = parse_json(response)
        lib_key = CourseKey.from_string(lib_info['library_key'])
        self.assertIsInstance(lib_key, LibraryLocator)

        libraries = getattr(course, 'target_library', [])
        libraries.append(unicode(lib_key))
        setattr(course, 'target_library', libraries)
        modulestore().update_item(course, self.user.id)

        return lib_key

    def _add_library_content_block(self, course, library_key, is_nonselect_library, other_settings=None):
        if is_nonselect_library:
            return ItemFactory.create(
                category='library_content',
                parent_location=course.location,
                user_id=self.user.id,
                publish_item=False,
                **(other_settings or {})
            )
        else:
            return ItemFactory.create(
                category='library_content',
                parent_location=course.location,
                user_id=self.user.id,
                publish_item=False,
                source_library_id=unicode(library_key),
                **(other_settings or {})
            )


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
@override_settings(GA_OPERATION_COURSE_ID_PATTERN=r'(course-v1:[^/+]+(/|\+)[^/+]+(/|\+)[^/+]+)$')
class DeleteCourseTest(ApiTestBase, ApiDeleteCourseTestMixin):
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
        self.assertEqual(content['email'], [u'このフィールドは必須です。'])

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
@override_settings(GA_OPERATION_LIBRARY_KEY_PATTERN=r'(library-v1:[^/+]+\+[^/+]+)$')
class DeleteLibraryTest(ApiTestBase, ApiDeleteLibraryTestMixin):
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
            'library_id': 'library-v1:org+course',
            'email': 'test@example.com',
        }
        response = self.client.post(_url, data)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)

        mock_delete_library_task.delay.assert_called_once_with(
            library_id='library-v1:org+course',
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
            'library_id': 'library-v1:org+course',
        })

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.content)

        self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
        self.assertEqual(content['email'], [u'このフィールドは必須です。'])

        mock_delete_library_task.assert_not_called()

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('cms.djangoapps.ga_operation.views.api.delete_library_task')
    def test_error(self, mock_delete_library_task, mock_log):
        mock_delete_library_task.delay.side_effect = self.exception

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'library_id': 'library-v1:org+course',
            'email': 'test@example.com',
        })
        self._assert_exception(response, mock_log)
        self._assert_audit_log(mock_log)

    @patch('cms.djangoapps.ga_operation.views.api.delete_library_task')
    def test_use_library(self, mock_delete_library_task):

        self._setting_library_option(self.course)
        lib_key = self._create_library(self.course)

        self.lc_block = self._add_library_content_block(self.course, lib_key, False)
        modulestore().update_item(self.lc_block, self.user.id)

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'library_id': lib_key,
            'email': 'test@example.com',
        })

        self.assertEqual(response.status_code, 400)

        content = json.loads(response.content)
        self.assertEqual(
            content[RESPONSE_FIELD_ID],
            u"・以下の講座で利用されているため、削除できません。\n{}".format(self.course.id)
        )
        mock_delete_library_task.assert_not_called()

    @patch('openedx.core.djangoapps.ga_operation.utils.log')
    @patch('cms.djangoapps.ga_operation.views.api.delete_library_task')
    def test_not_use_library(self, mock_delete_library_task, mock_log):

        self._setting_library_option(self.course)
        lib_key = self._create_library(self.course)

        self.lc_block = self._add_library_content_block(self.course, lib_key, True)
        modulestore().update_item(self.lc_block, self.user.id)
        library_id = 'library-v1:' + lib_key.org + '+' + lib_key.library

        _url = reverse(self.url)
        response = self.client.post(_url, {
            'library_id': library_id,
            'email': 'test@example.com',
        })

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        mock_delete_library_task.delay.assert_called_once_with(
            library_id=library_id,
            email='test@example.com',
        )
        self._assert_success_message(
            content, u'ライブラリ削除処理を開始しました。\n処理が終了次第、test@example.comのアドレスに完了通知が届きます。'
        )
        self._assert_audit_log(mock_log)

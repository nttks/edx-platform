# -*- coding: utf-8 -*-
import ddt
import json
import unittest
from datetime import date
from mock import patch

from django.core.urlresolvers import reverse as django_reverse
from django.test.utils import override_settings

from courseware.tests.factories import GlobalStaffFactory
from courseware.tests.helpers import LoginEnrollmentTestCase
from ga_operation.tests.test_api import ApiTestBase
from ga_operation.views.api import RESPONSE_FIELD_ID
from student.roles import GaAnalyzerRole
from student.tests.factories import UserFactory

GA_OPERATION_FOR_ANALYZER_POST_ENDPOINTS = [
    'all_users_info',
    'create_certs_status',
    'disabled_account_info',
    'enrollment_status',
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
            that must be declared in the GA_OPERATION_FOR_ANALYZER_POST_ENDPOINTS
            sets, or false otherwise.

    Returns:
        The return of Django's reverse function

    """
    is_endpoint_declared = endpoint in GA_OPERATION_FOR_ANALYZER_POST_ENDPOINTS
    if is_operation_endpoint and is_endpoint_declared is False:
        # Verify that all endpoints are declared so we can ensure they are
        # properly validated elsewhere.
        raise ValueError("The endpoint {} must be declared in ENDPOINTS before use.".format(endpoint))
    return django_reverse('ga_operation_api:' + endpoint, args=args, kwargs=kwargs)


@ddt.ddt
class GaOperationForAnalyzerEndpointMethodTest(LoginEnrollmentTestCase):

    def setUp(self):
        super(GaOperationForAnalyzerEndpointMethodTest, self).setUp()
        global_user = GlobalStaffFactory()
        GaAnalyzerRole().add_users(global_user)
        self.client.login(username=global_user.username, password='test')

    @ddt.data(*GA_OPERATION_FOR_ANALYZER_POST_ENDPOINTS)
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
class GaOperationForAnalyzerEndpointPermissionTest(LoginEnrollmentTestCase):

    def setUp(self):
        super(GaOperationForAnalyzerEndpointPermissionTest, self).setUp()
        self.setup_user()

    @ddt.data(*GA_OPERATION_FOR_ANALYZER_POST_ENDPOINTS)
    def test_post_endpoints_reject(self, endpoint):
        """
        Tests that POST endpoints are rejected with 403
        when accessed by non global staff and non ga analyzer.
        """
        url = reverse(endpoint)
        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    @ddt.data(*GA_OPERATION_FOR_ANALYZER_POST_ENDPOINTS)
    def test_post_endpoints_reject_non_ga_analyzer(self, endpoint):
        """
        Tests that POST endpoints are rejected with 403
        when accessed by global staff and non ga analyzer.
        """
        self.user = GlobalStaffFactory()
        self.client.login(username=self.user.username, password='test')
        url = reverse(endpoint)
        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)

    @ddt.data(*GA_OPERATION_FOR_ANALYZER_POST_ENDPOINTS)
    def test_post_endpoints_reject_non_global_staff(self, endpoint):
        """
        Tests that POST endpoints are rejected with 403
        when accessed by global non global staff and ga analyzer.
        """
        GaAnalyzerRole().add_users(self.user)
        url = reverse(endpoint)
        response = self.client.post(url)

        self.assertEqual(response.status_code, 403)


@ddt.ddt
@override_settings(GA_OPERATION_VALID_DOMAINS_LIST=['example.com'])
class ApiByEmailAndPeriodDateTest(ApiTestBase):

    def setUp(self):
        super(ApiByEmailAndPeriodDateTest, self).setUp()
        GaAnalyzerRole().add_users(self.user)
        self._url = 'all_users_info'
        self._task = None

    def _assert_audit_log(self, logger):
        logger.info.assert_called_with('path:{}, user.id:{} End.'.format(reverse(self.url), self.user.id))

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, url):
        self._url = url
        self._task = self.choose_task(url)

    @property
    def task(self):
        return self._task

    @property
    def service_in_date(self):
        return '2014-01-09'

    def choose_task(self, key):
        return {
            'all_users_info': 'ga_operation.views.api.all_users_info_task',
            'create_certs_status': 'ga_operation.views.api.create_certs_status_task',
            'enrollment_status': 'ga_operation.views.api.enrollment_status_task',
            'disabled_account_info': 'ga_operation.views.api.disabled_account_info_task'
        }[key]

    @patch('ga_operation.views.api.log')
    @ddt.data(
        ('all_users_info', '2014-01-09', '2017-03-31'),
        ('all_users_info', None, '2017-03-31'),
        ('all_users_info', '2014-01-09', None),
        ('all_users_info', None, None),
        ('create_certs_status', '2014-01-09', '2017-03-31'),
        ('create_certs_status', None, '2017-03-31'),
        ('create_certs_status', '2014-01-09', None),
        ('create_certs_status', None, None),
        ('enrollment_status', '2014-01-09', '2017-03-31'),
        ('enrollment_status', None, '2017-03-31'),
        ('enrollment_status', '2014-01-09', None),
        ('enrollment_status', None, None),
        ('disabled_account_info', '2014-01-09', '2017-03-31'),
        ('disabled_account_info', None, '2017-03-31'),
        ('disabled_account_info', '2014-01-09', None),
        ('disabled_account_info', None, None),
    )
    @ddt.unpack
    def test_success(self, url, start_date, end_date, mock_log):
        self.url = url
        with patch(self.task) as mock_task:
            _url = reverse(self.url)
            data = {
                'email': 'test@example.com',
            }

            if start_date:
                data['start_date'] = start_date.replace('-', '')

            if end_date:
                data['end_date'] = end_date.replace('-', '')

            response = self.client.post(_url, data)
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.content)

            sd = start_date if start_date else self.service_in_date
            ed = end_date if end_date else date.today().strftime('%Y-%m-%d')
            mock_task.delay.assert_called_with(
                sd,
                ed,
                'test@example.com',
            )
            self._assert_success_message(
                content, u'処理を開始しました。\n処理が終了次第、test@example.comのアドレスに完了通知が届きます。'
            )
            self._assert_audit_log(mock_log)

    @patch('ga_operation.views.api.log')
    @ddt.data(
        ('all_users_info', '2014-01-09', '2017-03-31'),
        ('create_certs_status', '2014-01-09', '2017-03-31'),
        ('enrollment_status', '2014-01-09', '2017-03-31'),
        ('disabled_account_info', '2014-01-09', '2017-03-31'),
    )
    @ddt.unpack
    def test_success_global_admin(self, url, start_date, end_date, mock_log):
        admin = 'global_admin'
        passwd = 'pass'
        self.user = UserFactory(username=admin, password=passwd, is_staff=True, is_superuser=True)
        self.client.login(username=admin, password=passwd)
        self.url = url
        with patch(self.task) as mock_task:
            _url = reverse(self.url)
            data = {
                'email': 'test@example.com',
            }

            if start_date:
                data['start_date'] = start_date.replace('-', '')

            if end_date:
                data['end_date'] = end_date.replace('-', '')

            response = self.client.post(_url, data)
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.content)

            sd = start_date if start_date else self.service_in_date
            ed = end_date if end_date else date.today().strftime('%Y-%m-%d')
            mock_task.delay.assert_called_with(
                sd,
                ed,
                'test@example.com',
            )
            self._assert_success_message(
                content, u'処理を開始しました。\n処理が終了次第、test@example.comのアドレスに完了通知が届きます。'
            )
            self._assert_audit_log(mock_log)

    @ddt.data('all_users_info', 'create_certs_status', 'enrollment_status', 'disabled_account_info')
    def test_start_date_before_service_in(self, url):
        self.url = url
        with patch(self.task) as mock_task:
            _url = reverse(self.url)
            data = {
                'start_date': '20140108',
                'end_date': '20141231',
                'email': 'test@example.com',
            }

            response = self.client.post(_url, data)
            self.assertEqual(response.status_code, 400)
            content = json.loads(response.content)

            self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
            self.assertEqual(content['start_date'], [u'集計開始日は20140109以降の日付を入力してください。'])
            mock_task.delay.assert_not_called()

    @ddt.data('all_users_info', 'create_certs_status', 'enrollment_status', 'disabled_account_info')
    def test_end_date_after_today(self, url):
        self.url = url
        with patch(self.task) as mock_task:
            _url = reverse(self.url)
            tomorrow = date.fromordinal(date.today().toordinal() + 1).strftime('%Y%m%d')
            data = {
                'start_date': self.service_in_date.replace('-', ''),
                'end_date': tomorrow,
                'email': 'test@example.com',
            }

            response = self.client.post(_url, data)
            self.assertEqual(response.status_code, 400)
            content = json.loads(response.content)

            self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
            self.assertEqual(content['end_date'], [u'集計終了日は本日以前の日付を入力してください。'])
            mock_task.delay.assert_not_called()

    @ddt.data('all_users_info', 'create_certs_status', 'enrollment_status', 'disabled_account_info')
    def test_end_date_before_start_date(self, url):
        self.url = url
        with patch(self.task) as mock_task:
            _url = reverse(self.url)
            data = {
                'start_date': '20170331',
                'end_date': '20170101',
                'email': 'test@example.com',
            }

            response = self.client.post(_url, data)
            self.assertEqual(response.status_code, 400)
            content = json.loads(response.content)

            self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
            self.assertEqual(content['end_date'], [u'終了日は開始日以降の日付を入力してください。'])
            mock_task.delay.assert_not_called()

    @ddt.data('all_users_info', 'create_certs_status', 'enrollment_status', 'disabled_account_info')
    def test_no_email(self, url):
        self.url = url
        with patch(self.task) as mock_task:
            _url = reverse(self.url)
            response = self.client.post(_url, {
                'start_date': '20160401',
                'end_date': '20170331',
            })

            self.assertEqual(response.status_code, 400)
            content = json.loads(response.content)

            self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
            self.assertEqual(content['email'], [u'このフィールドは必須です。'])
            mock_task.assert_not_called()

    @unittest.skip("There is no need for testing.")
    @ddt.data('all_users_info', 'create_certs_status', 'enrollment_status', 'disabled_account_info')
    def test_invalid_domain_email(self, url):
        self.url = url
        with patch(self.task) as mock_task:
            _url = reverse(self.url)
            response = self.client.post(_url, {
                'start_date': '20160401',
                'end_date': '20170331',
                'email': 'test@example.jp'
            })

            self.assertEqual(response.status_code, 400)
            content = json.loads(response.content)

            self.assertEqual(content[RESPONSE_FIELD_ID], u'入力したフォームの内容が不正です。')
            self.assertEqual(content['email'], [u'このドメインのEメールは使用できません。'])
            mock_task.assert_not_called()

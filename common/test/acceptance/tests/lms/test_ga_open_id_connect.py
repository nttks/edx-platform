"""
End-to-end tests for the OpenID Connect flow
"""
import base64
import json
import jwt
import requests
import urlparse
import unittest

from bok_choy.web_app_test import WebAppTest
from lms.envs.bok_choy import OAUTH_OIDC_ISSUER, EDXMKTG_LOGGED_IN_COOKIE_NAME
from ...fixtures.course import CourseFixture
from ...fixtures.ga_course_team import CourseTeamFixture
from ...pages.common.logout import LogoutPage
from ...pages.lms import BASE_URL
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.ga_authorize import (
    AuthorizePage, AuthorizeConfirmPage,
)
from ...pages.lms.ga_dashboard import DashboardPage
from ...pages.lms.login_and_register import CombinedLoginAndRegisterPage
from ..ga_helpers import GaccoTestMixin
from ..helpers import UniqueCourseTest


class AuthorizeTest(UniqueCourseTest, GaccoTestMixin):
    """
    Test the OpenID Connect process
    """

    def setUp(self):
        """
        Initialize pages.
        """
        super(AuthorizeTest, self).setUp()

        # client info is registerd by db_fixture
        self.client_name = 'oidc_test_app'
        self.client_id = 'test_client_id'
        self.client_secret = 'test_client_secret'

        # create course
        self.course = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        ).install()

        # create user
        username = 'test_oidc_user' + self.unique_id[0:6]
        self.user = {
            'username': username,
            'email': username + '@example.com'
        }
        self._create_user(self.user, False)

        CourseTeamFixture(self.course._course_key, self.user['email'], True).install()

        self.authorize_confirm_page = AuthorizeConfirmPage(self.browser)

        # Set window size
        self.setup_window_size_for_pc()

    def _access_authorize_page(self, response_type, client_id, redirect_uri, scope, state, nonce, next_page=None):
        if next_page is None:
            next_page = self.authorize_confirm_page

        AuthorizePage(self.browser, response_type, client_id, redirect_uri, scope, state, nonce).visit()
        if self.browser.get_cookie(EDXMKTG_LOGGED_IN_COOKIE_NAME) is None:
            CombinedLoginAndRegisterPage(self.browser, start_page='login').login(self.user['email'], 'edx')
            next_page.wait_for_page()

    def _create_user(self, user, staff):
        AutoAuthPage(
            self.browser,
            username=user['username'],
            email=user['email'],
            password='edx',
            staff=staff
        ).visit()
        LogoutPage(self.browser).visit()

    def _assert_access_token(self, scope, token_response):
        """
        Check Access Token Response
        """
        self.assertLess(token_response['expires_in'], 3600)
        self.assertItemsEqual(scope.split(' '), token_response['scope'].split(' '))
        access_token = token_response['access_token']
        token_type = token_response['token_type']
        id_token = jwt.decode(token_response['id_token'], self.client_secret, audience=self.client_id)
        refresh_token = token_response['refresh_token']
        return (access_token, token_type, id_token, refresh_token)

    def _assert_id_token(self, id_token):
        """
        Check ID Token
        """
        self.assertTrue('sub' in id_token)
        self.assertTrue('exp' in id_token)
        self.assertTrue('iat' in id_token)
        self.assertEqual(OAUTH_OIDC_ISSUER, id_token['iss'])
        self.assertEqual(self.client_id, id_token['aud'])

    def _assert_user_info(self, id_token, user_info):
        """
        Check User Info
        """
        self.assertEqual(id_token['sub'], user_info['sub'])
        self.assertEqual(self.user['username'], user_info['name'])
        self.assertEqual(self.user['username'], user_info['preferred_username'])
        self.assertEqual('en', user_info['locale'])
        self.assertEqual(self.user['email'], user_info['email'])
        self.assertFalse(user_info['administrator'])

    @unittest.skip("Until fix authority course_staff and course_instructor or revert honke.")
    def test_authorize_flow(self):
        scope = 'openid profile email course_staff course_instructor permissions'
        redirect_uri = 'http://localhost:8003/dashboard'
        state = 'dummy_state'
        nonce = 'dummy_nonce'

        # Access to authorize page
        self._access_authorize_page('code', self.client_id, redirect_uri, scope, state, nonce)

        self.assertTrue(self.authorize_confirm_page.get_title().startswith(self.client_name))
        self.assertItemsEqual(scope.split(' '), self.authorize_confirm_page.get_scopes())

        # Execute approve
        self.authorize_confirm_page.click_approve()
        DashboardPage(self.browser).wait_for_page()

        result_url = urlparse.urlparse(self.browser.current_url)
        # Check state is keeping
        self.assertEqual(state, urlparse.parse_qs(result_url.query)['state'][0])
        code = urlparse.parse_qs(result_url.query)['code'][0]

        # Get Access Token (client_secret_post authentication)
        token_response = requests.post(
            '{base}/oauth2/access_token/'.format(base=BASE_URL),
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'authorization_code',
                'code': code,
                'nonce': nonce,
            }
        ).json()

        access_token, token_type, id_token, refresh_token = self._assert_access_token(scope, token_response)
        self._assert_id_token(id_token)

        # Get UserInfo
        user_info_response = requests.get(
            '{base}/oauth2/user_info/'.format(base=BASE_URL),
            headers={
                'Authorization': '{token_type} {token}'.format(token_type=token_type, token=access_token)
            }
        )
        user_info = json.loads(user_info_response.content)
        self._assert_user_info(id_token, user_info)

        # Get Access Token used by Refersh Token (client_secret_basic authentication)
        basic_token = base64.b64encode(self.client_id + ':' + self.client_secret)
        token_response_by_refresh = requests.post(
            '{base}/oauth2/access_token/'.format(base=BASE_URL),
            headers={
                'Authorization': 'Basic {}'.format(basic_token)
            },
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
            },
        ).json()
        access_token, token_type, id_token, refresh_token = self._assert_access_token(scope, token_response_by_refresh)
        self._assert_id_token(id_token)

        # Get UserInfo
        user_info_response = requests.get(
            '{base}/oauth2/user_info/'.format(base=BASE_URL),
            headers={
                'Authorization': '{token_type} {token}'.format(token_type=token_type, token=access_token)
            }
        )
        user_info = json.loads(user_info_response.content)
        self._assert_user_info(id_token, user_info)

    def test_authorize_cancel(self):
        scope = 'openid profile email course_staff course_instructor permissions'
        redirect_uri = 'http://localhost:8003/dashboard'
        state = 'dummy_state'
        nonce = 'dummy_nonce'

        # Access to authorize page
        self._access_authorize_page('code', self.client_id, redirect_uri, scope, state, nonce)

        self.assertTrue(self.authorize_confirm_page.get_title().startswith(self.client_name))
        self.assertItemsEqual(scope.split(' '), self.authorize_confirm_page.get_scopes())

        # Execute cancel
        self.authorize_confirm_page.click_cancel()
        DashboardPage(self.browser).wait_for_page()

        result_url = urlparse.urlparse(self.browser.current_url)
        result_params = urlparse.parse_qs(result_url.query)
        # Check error code
        self.assertEqual('access_denied', result_params['error'][0])
        self.assertFalse('code' in result_params)

    @unittest.skip("Until fix authority course_staff and course_instructor or revert honke.")
    def test_authorize_bypass(self):
        # override credential
        self.client_id = 'test_trusted_client_id'
        self.client_secret = 'test_trusted_client_secret'
        scope = 'openid profile email course_staff course_instructor permissions'
        redirect_uri = 'http://localhost:8003/dashboard'
        state = 'dummy_state'
        nonce = 'dummy_nonce'

        # Access to authorize page
        # Bypass the AuthorizePage
        self._access_authorize_page('code', self.client_id, redirect_uri, scope, state, nonce, next_page=DashboardPage(self.browser))

        result_url = urlparse.urlparse(self.browser.current_url)
        # Check state is keeping
        self.assertEqual(state, urlparse.parse_qs(result_url.query)['state'][0])
        code = urlparse.parse_qs(result_url.query)['code'][0]

        # Get Access Token (client_secret_post authentication)
        token_response = requests.post(
            '{base}/oauth2/access_token/'.format(base=BASE_URL),
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'authorization_code',
                'code': code,
                'nonce': nonce,
            }
        ).json()

        access_token, token_type, id_token, refresh_token = self._assert_access_token(scope, token_response)
        self._assert_id_token(id_token)

        # Get UserInfo
        user_info_response = requests.get(
            '{base}/oauth2/user_info/'.format(base=BASE_URL),
            headers={
                'Authorization': '{token_type} {token}'.format(token_type=token_type, token=access_token)
            }
        )
        user_info = json.loads(user_info_response.content)
        self._assert_user_info(id_token, user_info)

    def test_authorize_error(self):
        scope = 'openid profile email course_staff course_instructor permissions'
        redirect_uri = 'http://localhost:8003/dashboard'
        state = 'dummy_state'
        nonce = 'dummy_nonce'

        def _assert_error(error_code, error_description=None):
            self.assertEqual('Error Code: {}'.format(error_code), self.authorize_confirm_page.get_error_code())
            if error_description:
                self.assertEqual(error_description, self.authorize_confirm_page.get_error_description())

        # No response_type
        self._access_authorize_page(None, self.client_id, redirect_uri, scope, state, nonce)
        _assert_error('invalid_request', "No 'response_type' supplied.")

        # Invalid response_type
        self._access_authorize_page('codeX', self.client_id, redirect_uri, scope, state, nonce)
        _assert_error('unsupported_response_type')

        # No client_id
        self._access_authorize_page('code', None, redirect_uri, scope, state, nonce)
        _assert_error('unauthorized_client')

        # Invalid client_id
        self._access_authorize_page('code', 'invalid_client_id', redirect_uri, scope, state, nonce)
        _assert_error('unauthorized_client')

        # Invalid redirect_uri
        self._access_authorize_page('code', self.client_id, 'http://localhost/invalid', scope, state, nonce)
        _assert_error('invalid_request', "The requested redirect didn't match the client settings.")

        # Invalid scope
        self._access_authorize_page('code', self.client_id, redirect_uri, 'openid profileX email', state, nonce)
        _assert_error('invalid_request', "'profileX' is not a valid scope.")

    def test_access_token_error(self):
        def _assert_error(response, error_code, error_description=None, status=400):
            self.assertEqual(status, response.status_code)
            response_json = response.json()
            self.assertEqual(error_code, response_json['error'])
            if error_description:
                self.assertEqual(error_description, response_json['error_description'])

        # Try to GET request
        _assert_error(
            requests.get(
                '{base}/oauth2/access_token/'.format(base=BASE_URL),
            ),
            error_code='invalid_request',
            error_description='Only POST requests allowed.'
        )

        # No grant_type
        _assert_error(
            requests.post(
                '{base}/oauth2/access_token/'.format(base=BASE_URL),
                data={
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                }
            ),
            error_code='invalid_request',
            error_description="No 'grant_type' included in the request."
        )

        # Unsupported grant_type
        _assert_error(
            requests.post(
                '{base}/oauth2/access_token/'.format(base=BASE_URL),
                data={
                    'grant_type': 'password',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                }
            ),
            error_code='unsupported_grant_type',
        )

        # not authenticate
        _assert_error(
            requests.post(
                '{base}/oauth2/access_token/'.format(base=BASE_URL),
                data={
                    'grant_type': 'authorization_code',
                    'code': 'testcode'
                }
            ),
            error_code='invalid_client',
        )

        # No code
        _assert_error(
            requests.post(
                '{base}/oauth2/access_token/'.format(base=BASE_URL),
                data={
                    'grant_type': 'authorization_code',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                }
            ),
            error_code='invalid_request',
        )

        # Invalid code
        _assert_error(
            requests.post(
                '{base}/oauth2/access_token/'.format(base=BASE_URL),
                data={
                    'grant_type': 'authorization_code',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'code': 'invalid_code',
                }
            ),
            error_code='invalid_grant',
        )

        # No refresh_token
        _assert_error(
            requests.post(
                '{base}/oauth2/access_token/'.format(base=BASE_URL),
                data={
                    'grant_type': 'refresh_token',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                }
            ),
            error_code='invalid_request',
        )

        # Invalid refresh_token
        _assert_error(
            requests.post(
                '{base}/oauth2/access_token/'.format(base=BASE_URL),
                data={
                    'grant_type': 'refresh_token',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'refresh_token': 'invalid_refresh_token',
                }
            ),
            error_code='invalid_grant',
        )

    def test_user_info_error(self):
        def _assert_error(response, error_code, error_description=None, status=401):
            self.assertEqual(status, response.status_code)
            response_json = response.json()
            self.assertEqual(error_code, response_json['error'])
            if error_description:
                self.assertEqual(error_description, response_json['error_description'])

        # Invalid header
        _assert_error(
            requests.get(
                '{base}/oauth2/user_info/'.format(base=BASE_URL),
            ),
            error_code='access_denied'
        )

        # Invalid access_token
        _assert_error(
            requests.get(
                '{base}/oauth2/user_info/'.format(base=BASE_URL),
                headers={
                    'Authorization': 'Bearer invalid_token'
                }
            ),
            error_code='invalid_token'
        )

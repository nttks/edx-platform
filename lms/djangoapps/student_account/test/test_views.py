# -*- coding: utf-8 -*-
""" Tests for student account views. """

import re
from unittest import skipUnless
from urllib import urlencode
import json

import mock
import ddt
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core import mail
from django.contrib import messages
from django.contrib.messages.middleware import MessageMiddleware
from django.test import TestCase
from django.test.utils import override_settings
from django.http import HttpRequest

from course_modes.models import CourseMode
from openedx.core.djangoapps.ga_optional.models import UserOptionalConfiguration, USERPOFILE_OPTION_KEY
from openedx.core.djangoapps.user_api.accounts.api import activate_account, create_account
from openedx.core.djangoapps.user_api.accounts import EMAIL_MAX_LENGTH
from openedx.core.lib.js_utils import escape_json_dumps
from student.tests.factories import UserFactory
from student_account.views import account_settings_context
from third_party_auth.tests.testutil import simulate_running_pipeline, ThirdPartyAuthTestMixin
from util.testing import UrlResetMixin
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_sso_config.models import SsoConfig
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_sso_config.tests.factories import SsoConfigFactory
from biz.djangoapps.util.tests.testcase import BizViewTestBase


@ddt.ddt
class StudentAccountUpdateTest(UrlResetMixin, TestCase):
    """ Tests for the student account views that update the user's account information. """

    USERNAME = u"heisenberg"
    ALTERNATE_USERNAME = u"walt"
    OLD_PASSWORD = u"ḅḷüëṡḳÿ"
    NEW_PASSWORD = u"🄱🄸🄶🄱🄻🅄🄴"
    OLD_EMAIL = u"walter@graymattertech.com"
    NEW_EMAIL = u"walt@savewalterwhite.com"
    
    LOCK_USERNAME = u'lockuser'
    LOCK_PASSWORD = u'Abc1234#$%'
    LOCK_EMAIL = u'locked@test.com'
    
    UNLOCK_USERNAME = u'unlockuser'
    UNLOCK_PASSWORD = u'Abc1234#$%'
    UNLOCK_EMAIL = u'unlocked@test.com'

    INVALID_ATTEMPTS = 100

    INVALID_EMAILS = [
        None,
        u"",
        u"a",
        "no_domain",
        "no+domain",
        "@",
        "@domain.com",
        "test@no_extension",

        # Long email -- subtract the length of the @domain
        # except for one character (so we exceed the max length limit)
        u"{user}@example.com".format(
            user=(u'e' * (EMAIL_MAX_LENGTH - 11))
        )
    ]

    INVALID_KEY = u"123abc"

    def setUp(self):
        super(StudentAccountUpdateTest, self).setUp("student_account.urls")

        # Create/activate a new account
        activation_key = create_account(self.USERNAME, self.OLD_PASSWORD, self.OLD_EMAIL)
        activate_account(activation_key)

        # Login
        result = self.client.login(username=self.USERNAME, password=self.OLD_PASSWORD)
        self.assertTrue(result)
        
        # Create initial data
        self.gacco_organization = Organization(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,  # It means the first of Organization
            created_by=UserFactory.create(),
        )
        self.gacco_organization.save()
        self.user = UserFactory.create()

    @skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in LMS')
    def test_password_change(self):
        # Request a password change while logged in, simulating
        # use of the password reset link from the account page
        response = self._change_password()
        self.assertEqual(response.status_code, 200)

        # Check that an email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Retrieve the activation link from the email body
        email_body = mail.outbox[0].body
        result = re.search('(?P<url>https?://[^\s]+)', email_body)
        self.assertIsNot(result, None)
        activation_link = result.group('url')

        # Visit the activation link
        response = self.client.get(activation_link)
        self.assertEqual(response.status_code, 200)

        # Submit a new password and follow the redirect to the success page
        response = self.client.post(
            activation_link,
            # These keys are from the form on the current password reset confirmation page.
            {'new_password1': self.NEW_PASSWORD, 'new_password2': self.NEW_PASSWORD},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your password has been set.")

        # Log the user out to clear session data
        self.client.logout()

        # Verify that the new password can be used to log in
        result = self.client.login(username=self.USERNAME, password=self.NEW_PASSWORD)
        self.assertTrue(result)

        # Try reusing the activation link to change the password again
        response = self.client.post(
            activation_link,
            {'new_password1': self.OLD_PASSWORD, 'new_password2': self.OLD_PASSWORD},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The password reset link was invalid, possibly because the link has already been used.")

        self.client.logout()

        # Verify that the old password cannot be used to log in
        result = self.client.login(username=self.USERNAME, password=self.OLD_PASSWORD)
        self.assertFalse(result)

        # Verify that the new password continues to be valid
        result = self.client.login(username=self.USERNAME, password=self.NEW_PASSWORD)
        self.assertTrue(result)

    @ddt.data(True, False)
    def test_password_change_logged_out(self, send_email):
        # Log the user out
        self.client.logout()

        # Request a password change while logged out, simulating
        # use of the password reset link from the login page
        if send_email:
            response = self._change_password(email=self.OLD_EMAIL)
            self.assertEqual(response.status_code, 200)
        else:
            # Don't send an email in the POST data, simulating
            # its (potentially accidental) omission in the POST
            # data sent from the login page
            response = self._change_password()
            self.assertEqual(response.status_code, 400)

    def test_password_change_inactive_user(self):
        # Log out the user created during test setup
        self.client.logout()

        # Create a second user, but do not activate it
        create_account(self.ALTERNATE_USERNAME, self.OLD_PASSWORD, self.NEW_EMAIL)

        # Send the view the email address tied to the inactive user
        response = self._change_password(email=self.NEW_EMAIL)

        # Expect that the activation email is still sent,
        # since the user may have lost the original activation email.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_password_change_no_user(self):
        # Log out the user created during test setup
        self.client.logout()

        # Send the view an email address not tied to any user
        response = self._change_password(email=self.NEW_EMAIL)
        self.assertEqual(response.status_code, 400)

    def test_password_change_rate_limited(self):
        # Log out the user created during test setup, to prevent the view from
        # selecting the logged-in user's email address over the email provided
        # in the POST data
        self.client.logout()

        # Make many consecutive bad requests in an attempt to trigger the rate limiter
        for attempt in xrange(self.INVALID_ATTEMPTS):
            self._change_password(email=self.NEW_EMAIL)

        response = self._change_password(email=self.NEW_EMAIL)
        self.assertEqual(response.status_code, 403)

    @ddt.data(
        ('post', 'password_change_request', []),
    )
    @ddt.unpack
    def test_require_http_method(self, correct_method, url_name, args):
        wrong_methods = {'get', 'put', 'post', 'head', 'options', 'delete'} - {correct_method}
        url = reverse(url_name, args=args)

        for method in wrong_methods:
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 405)
            
    def test_password_change_block(self):
        """ try check password change lock. SsoConfig table register records."""
        lock_user = UserFactory.create(email=self.LOCK_EMAIL)
        MemberFactory.create(
            org=self.gacco_organization,
            group=None,
            user=lock_user,
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            is_active=True,
            is_delete=False,
        )
        SsoConfigFactory.create(idp_slug='abcde', created_by=self.user, modified_by=self.user,
                                org=self.gacco_organization)
        # Record Check
        self.assertEqual(1, len(Member.objects.filter(org=self.gacco_organization, is_active=True)))
        self.assertEqual(1, len(SsoConfig.objects.filter(org=self.gacco_organization)))
        self.client.logout()
        # Locked Password URL form create and assert
        response = self._change_password(email=self.LOCK_EMAIL)
        self.assertEqual(response.status_code, 400)
        # Unlocked Password URL form create and assert
        create_account(self.UNLOCK_USERNAME, self.UNLOCK_PASSWORD, self.UNLOCK_EMAIL)
        response = self._change_password(email=self.UNLOCK_EMAIL)
        self.assertEqual(response.status_code, 200)

    def _change_password(self, email=None):
        """Request to change the user's password. """
        data = {}

        if email:
            data['email'] = email

        return self.client.post(path=reverse('password_change_request'), data=data)


@ddt.ddt
class StudentAccountLoginAndRegistrationTest(ThirdPartyAuthTestMixin, UrlResetMixin, ModuleStoreTestCase):
    """ Tests for the student account views that update the user's account information. """

    USERNAME = "bob"
    EMAIL = "bob@example.com"
    PASSWORD = "password"

    @mock.patch.dict(settings.FEATURES, {'EMBARGO': True})
    def setUp(self):
        super(StudentAccountLoginAndRegistrationTest, self).setUp('embargo')
        # For these tests, two third party auth providers are enabled by default:
        self.configure_google_provider(enabled=True)
        self.configure_facebook_provider(enabled=True)
        # SAML Test append test data
        self.configure_azure_ad_provider(enabled=False)
        self.gacco_organization = Organization(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,
            created_by=UserFactory.create(),
        )
        self.gacco_organization.save()
        self.user = UserFactory.create()

    @ddt.data(
        ("signin_user", "login"),
        ("register_user", "register"),
    )
    @ddt.unpack
    def test_login_and_registration_form(self, url_name, initial_mode):
        response = self.client.get(reverse(url_name))
        expected_data = '"initial_mode": "{mode}"'.format(mode=initial_mode)
        self.assertContains(response, expected_data)

    @ddt.data("signin_user", "register_user")
    def test_login_and_registration_form_already_authenticated(self, url_name):
        # Create/activate a new account and log in
        activation_key = create_account(self.USERNAME, self.PASSWORD, self.EMAIL)
        activate_account(activation_key)
        result = self.client.login(username=self.USERNAME, password=self.PASSWORD)
        self.assertTrue(result)

        # Verify that we're redirected to the dashboard
        response = self.client.get(reverse(url_name))
        self.assertRedirects(response, reverse("dashboard"))

    @ddt.data(
        (False, "signin_user"),
        (False, "register_user"),
        (True, "signin_user"),
        (True, "register_user"),
    )
    @ddt.unpack
    def test_login_and_registration_form_signin_preserves_params(self, is_edx_domain, url_name):
        params = [
            ('course_id', 'edX/DemoX/Demo_Course'),
            ('enrollment_action', 'enroll'),
        ]

        # The response should have a "Sign In" button with the URL
        # that preserves the querystring params
        with mock.patch.dict(settings.FEATURES, {'IS_EDX_DOMAIN': is_edx_domain}):
            response = self.client.get(reverse(url_name), params)

        expected_url = '/login?{}'.format(self._finish_auth_url_param(params + [('next', '/dashboard')]))
        self.assertContains(response, expected_url)

        # Add additional parameters:
        params = [
            ('course_id', 'edX/DemoX/Demo_Course'),
            ('enrollment_action', 'enroll'),
            ('course_mode', CourseMode.DEFAULT_MODE_SLUG),
            ('email_opt_in', 'true'),
            ('next', '/custom/final/destination')
        ]

        # Verify that this parameter is also preserved
        with mock.patch.dict(settings.FEATURES, {'IS_EDX_DOMAIN': is_edx_domain}):
            response = self.client.get(reverse(url_name), params)

        expected_url = '/login?{}'.format(self._finish_auth_url_param(params))
        self.assertContains(response, expected_url)

    @mock.patch.dict(settings.FEATURES, {"ENABLE_THIRD_PARTY_AUTH": False})
    @ddt.data("signin_user", "register_user")
    def test_third_party_auth_disabled(self, url_name):
        response = self.client.get(reverse(url_name))
        self._assert_third_party_auth_data(response, None, None, [])

    @ddt.data(
        ("signin_user", None, None),
        ("register_user", None, None),
        ("signin_user", "google-oauth2", "Google"),
        ("register_user", "google-oauth2", "Google"),
        ("signin_user", "facebook", "Facebook"),
        ("register_user", "facebook", "Facebook"),
    )
    @ddt.unpack
    def test_third_party_auth(self, url_name, current_backend, current_provider):
        params = [
            ('course_id', 'course-v1:Org+Course+Run'),
            ('enrollment_action', 'enroll'),
            ('course_mode', CourseMode.DEFAULT_MODE_SLUG),
            ('email_opt_in', 'true'),
            ('next', '/custom/final/destination'),
        ]

        # Simulate a running pipeline
        if current_backend is not None:
            pipeline_target = "student_account.views.third_party_auth.pipeline"
            with simulate_running_pipeline(pipeline_target, current_backend):
                response = self.client.get(reverse(url_name), params)

        # Do NOT simulate a running pipeline
        else:
            response = self.client.get(reverse(url_name), params)

        # This relies on the THIRD_PARTY_AUTH configuration in the test settings
        expected_providers = [
            {
                "id": "oa2-facebook",
                "name": "Facebook",
                "iconClass": "fa-facebook",
                "loginUrl": self._third_party_login_url("facebook", "login", params),
                "registerUrl": self._third_party_login_url("facebook", "register", params)
            },
            {
                "id": "oa2-google-oauth2",
                "name": "Google",
                "iconClass": "fa-google-plus",
                "loginUrl": self._third_party_login_url("google-oauth2", "login", params),
                "registerUrl": self._third_party_login_url("google-oauth2", "register", params)
            }
        ]
        self._assert_third_party_auth_data(response, current_backend, current_provider, expected_providers)

    def test_hinted_login(self):
        params = [("next", "/courses/something/?tpa_hint=oa2-google-oauth2")]
        response = self.client.get(reverse('signin_user'), params)
        self.assertContains(response, '"third_party_auth_hint": "oa2-google-oauth2"')

    @override_settings(SITE_NAME=settings.MICROSITE_TEST_HOSTNAME)
    def test_microsite_uses_old_login_page(self):
        # Retrieve the login page from a microsite domain
        # and verify that we're served the old page.
        resp = self.client.get(
            reverse("signin_user"),
            HTTP_HOST=settings.MICROSITE_TEST_HOSTNAME
        )
        self.assertContains(resp, "Log into your Test Microsite Account")
        self.assertContains(resp, "login-form")

    def test_microsite_uses_old_register_page(self):
        # Retrieve the register page from a microsite domain
        # and verify that we're served the old page.
        resp = self.client.get(
            reverse("register_user"),
            HTTP_HOST=settings.MICROSITE_TEST_HOSTNAME
        )
        self.assertContains(resp, "Register for Test Microsite")
        self.assertContains(resp, "register-form")

    def test_login_registration_xframe_protected(self):
        resp = self.client.get(
            reverse("register_user"),
            {},
            HTTP_REFERER="http://localhost/iframe"
        )

        self.assertEqual(resp['X-Frame-Options'], 'DENY')

        self.configure_lti_provider(name='Test', lti_hostname='localhost', lti_consumer_key='test_key', enabled=True)

        resp = self.client.get(
            reverse("register_user"),
            HTTP_REFERER="http://localhost/iframe"
        )

        self.assertEqual(resp['X-Frame-Options'], 'ALLOW')

    def _assert_third_party_auth_data(self, response, current_backend, current_provider, providers):
        """Verify that third party auth info is rendered correctly in a DOM data attribute. """
        finish_auth_url = None
        if current_backend:
            finish_auth_url = reverse("social:complete", kwargs={"backend": current_backend}) + "?"

        auth_info = {
            "currentProvider": current_provider,
            "providers": providers,
            "secondaryProviders": [],
            "finishAuthUrl": finish_auth_url,
            "errorMessage": None,
        }
        auth_info = escape_json_dumps(auth_info)

        expected_data = '"third_party_auth": {auth_info}'.format(
            auth_info=auth_info
        )

        self.assertContains(response, expected_data)

    def _third_party_login_url(self, backend_name, auth_entry, login_params):
        """Construct the login URL to start third party authentication. """
        return u"{url}?auth_entry={auth_entry}&{param_str}".format(
            url=reverse("social:begin", kwargs={"backend": backend_name}),
            auth_entry=auth_entry,
            param_str=self._finish_auth_url_param(login_params),
        )

    def _finish_auth_url_param(self, params):
        """
        Make the next=... URL parameter that indicates where the user should go next.

        >>> _finish_auth_url_param([('next', '/dashboard')])
        '/account/finish_auth?next=%2Fdashboard'
        """
        return urlencode({
            'next': '/account/finish_auth?{}'.format(urlencode(params))
        })

    @ddt.data(
        ("signin_user", None),
        ("register_user", None),
        ("signin_user", "saml-abc"),
        ("register_user", "saml-abc"),
        ("signin_user", "saml-cde"),
        ("register_user", "saml-cde"),
    )
    @ddt.unpack
    def test_is_hide_third_party_auth(self, url_name, current_backend):
        self.configure_azure_ad_provider(enabled=True)
        self.configure_azure_ad_2_provider(enabled=True)
        SsoConfigFactory.create(idp_slug='abc', created_by=self.user, modified_by=self.user,
                                org=self.gacco_organization)
        params = [
            ('course_id', 'course-v1:Org+Course+Run'),
            ('enrollment_action', 'enroll'),
            ('course_mode', CourseMode.DEFAULT_MODE_SLUG),
            ('email_opt_in', 'true'),
            ('next', '/custom/final/destination'),
        ]
        # Simulate a running pipeline
        if current_backend is not None:
            pipeline_target = "student_account.views.third_party_auth.pipeline"
            with simulate_running_pipeline(pipeline_target, current_backend):
                response = self.client.get(reverse(url_name), params)

        # Do NOT simulate a running pipeline
        else:
            response = self.client.get(reverse(url_name), params)
        res_facebook = response.content.find('oa2-facebook')
        res_google = response.content.find('oa2-google')
        res_saml_abc = response.content.find('saml-abc')
        res_saml_cde = response.content.find('saml-cde')
        # True
        self.assertNotEqual(-1, res_facebook)
        self.assertNotEqual(-1, res_google)
        self.assertNotEqual(-1, res_saml_cde)
        # False
        self.assertEqual(-1, res_saml_abc)


class AccountSettingsViewTest(ThirdPartyAuthTestMixin, BizViewTestBase):
    """ Tests for the account settings view. """

    USERNAME = 'student'
    PASSWORD = 'password'
    FIELDS = [
        'country',
        'gender',
        'language',
        'level_of_education',
        'password',
        'invitation_code',
        'year_of_birth',
        'preferred_language',
    ]

    @mock.patch("django.conf.settings.MESSAGE_STORAGE", 'django.contrib.messages.storage.cookie.CookieStorage')
    def setUp(self):
        super(AccountSettingsViewTest, self).setUp()
        self.user = UserFactory.create(username=self.USERNAME, password=self.PASSWORD)
        self.client.login(username=self.USERNAME, password=self.PASSWORD)

        self.request = HttpRequest()
        self.request.user = self.user

        # For these tests, two third party auth providers are enabled by default:
        self.configure_google_provider(enabled=True)
        self.configure_facebook_provider(enabled=True)
        self.configure_azure_ad_provider(enabled=True)

        # Python-social saves auth failure notifcations in Django messages.
        # See pipeline.get_duplicate_provider() for details.
        self.request.COOKIES = {}
        MessageMiddleware().process_request(self.request)
        messages.error(self.request, 'Facebook is already in use.', extra_tags='Auth facebook')

    def test_context(self):

        user_optional_configuration = UserOptionalConfiguration(
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key=USERPOFILE_OPTION_KEY,
            changed_by=self.request.user,
            user=self.request.user
        )
        user_optional_configuration.save()

        context = account_settings_context(self.request)

        user_accounts_api_url = reverse("accounts_api", kwargs={'username': self.user.username})
        self.assertEqual(context['user_accounts_api_url'], user_accounts_api_url)

        user_preferences_api_url = reverse('preferences_api', kwargs={'username': self.user.username})
        self.assertEqual(context['user_preferences_api_url'], user_preferences_api_url)

        for attribute in self.FIELDS:
            self.assertIn(attribute, context['fields'])

        self.assertEqual(
            context['user_accounts_api_url'], reverse("accounts_api", kwargs={'username': self.user.username})
        )
        self.assertEqual(
            context['user_preferences_api_url'], reverse('preferences_api', kwargs={'username': self.user.username})
        )

        self.assertEqual(context['duplicate_provider'], 'Facebook')
        self.assertEqual(context['auth']['providers'][0]['name'], 'Facebook')
        self.assertEqual(context['auth']['providers'][1]['name'], 'Google')
        self.assertEqual(context['email_hidden_available'], True)

    def test_excluding_saml(self):

        # Register NG words in the sso_config
        main_org = self._create_organization(org_name='org_name', org_code='org_code')
        SsoConfigFactory.create(idp_slug='abc', org=main_org, created_by=self.user, modified_by=self.user)

        user_optional_configuration = UserOptionalConfiguration(
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key=USERPOFILE_OPTION_KEY,
            changed_by=self.request.user,
            user=self.request.user
        )
        user_optional_configuration.save()

        context = account_settings_context(self.request)

        user_accounts_api_url = reverse("accounts_api", kwargs={'username': self.user.username})
        self.assertEqual(context['user_accounts_api_url'], user_accounts_api_url)

        user_preferences_api_url = reverse('preferences_api', kwargs={'username': self.user.username})
        self.assertEqual(context['user_preferences_api_url'], user_preferences_api_url)

        for attribute in self.FIELDS:
            self.assertIn(attribute, context['fields'])

        self.assertEqual(
            context['user_accounts_api_url'], reverse("accounts_api", kwargs={'username': self.user.username})
        )
        self.assertEqual(
            context['user_preferences_api_url'], reverse('preferences_api', kwargs={'username': self.user.username})
        )

        self.assertEqual(context['duplicate_provider'], 'Facebook')
        self.assertEqual(context['auth']['providers'][0]['name'], 'Facebook')
        self.assertEqual(context['auth']['providers'][1]['name'], 'Google')

        context_len = len(context['auth']['providers'])

        self.assertEqual(2, context_len)
        self.assertEqual(context['email_hidden_available'], True)

    def test_view(self):

        view_path = reverse('account_settings')
        response = self.client.get(path=view_path)

        for attribute in self.FIELDS:
            self.assertIn(attribute, response.content)


@override_settings(SITE_NAME=settings.MICROSITE_LOGISTRATION_HOSTNAME)
class MicrositeLogistrationTests(TestCase):
    """
    Test to validate that microsites can display the logistration page
    """

    def test_login_page(self):
        """
        Make sure that we get the expected logistration page on our specialized
        microsite
        """

        resp = self.client.get(
            reverse('signin_user'),
            HTTP_HOST=settings.MICROSITE_LOGISTRATION_HOSTNAME
        )
        self.assertEqual(resp.status_code, 200)

        self.assertIn('<div id="login-and-registration-container"', resp.content)

    def test_registration_page(self):
        """
        Make sure that we get the expected logistration page on our specialized
        microsite
        """

        resp = self.client.get(
            reverse('register_user'),
            HTTP_HOST=settings.MICROSITE_LOGISTRATION_HOSTNAME
        )
        self.assertEqual(resp.status_code, 200)

        self.assertIn('<div id="login-and-registration-container"', resp.content)

    @override_settings(SITE_NAME=settings.MICROSITE_TEST_HOSTNAME)
    def test_no_override(self):
        """
        Make sure we get the old style login/registration if we don't override
        """

        resp = self.client.get(
            reverse('signin_user'),
            HTTP_HOST=settings.MICROSITE_TEST_HOSTNAME
        )
        self.assertEqual(resp.status_code, 200)

        self.assertNotIn('<div id="login-and-registration-container"', resp.content)

        resp = self.client.get(
            reverse('register_user'),
            HTTP_HOST=settings.MICROSITE_TEST_HOSTNAME
        )
        self.assertEqual(resp.status_code, 200)

        self.assertNotIn('<div id="login-and-registration-container"', resp.content)

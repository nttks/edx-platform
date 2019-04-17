# -*- coding: utf-8 -*-
import ddt
import json
from django.core.urlresolvers import reverse
from django.test import TestCase
from student.tests.factories import UserFactory
from biz.djangoapps.gx_username_rule.tests.factories import OrgUsernameRuleFactory
from biz.djangoapps.ga_organization.tests.factories import OrganizationFactory
from biz.djangoapps.gx_sso_config.tests.factories import SsoConfigFactory
from social.apps.django_app.default.models import UserSocialAuth


@ddt.ddt
class GaStudentAccountViewTest(TestCase):

    def setUp(self):
        super(GaStudentAccountViewTest, self).setUp()
        self.gacco_org = OrganizationFactory.create(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,
            created_by=UserFactory.create(),
        )

    @property
    def _url_check_redirect_saml_login(self):
        return reverse('ga_student_account:check_redirect_saml_login')

    @property
    def _url_get_org_username_rules(self):
        return reverse('ga_student_account:get_org_username_rules')

    """
    Test for get_org_username_rules
    """
    @ddt.data(0, 1, 5)
    def test_get_org_username_rules(self, prefix_count):
        # arrange
        for i in range(prefix_count):
            OrgUsernameRuleFactory.create(prefix='PRE{}-'.format(str(i)), org=self.gacco_org)
        # act
        response = self.client.post(self._url_get_org_username_rules)
        # assert
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        data_list = json.loads(data['list'])
        self.assertEqual(prefix_count, len(data_list))

    """
    Test for check_redirect_saml_login
    """
    def _assert_response_not_redirect(self, response):
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(False, data['exist_saml_master'])
        self.assertEqual('', data['redirect_url'])

    def test_check_redirect_saml_login(self):
        # arrange
        OrgUsernameRuleFactory.create(prefix='PRE-', org=self.gacco_org)
        SsoConfigFactory.create(idp_slug='TEST', org=self.gacco_org)
        user = UserFactory.create(email='sample@sample.com', username='PRE-username1')
        UserSocialAuth.objects.create(user=user, provider='tpa-saml', uid="TEST:xxxxx")
        # act
        response = self.client.post(self._url_check_redirect_saml_login, {
            'email': user.email,
            'next': '/dashboard'
        })
        # assert
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(True, data['exist_saml_master'])
        self.assertEqual('/auth/login/tpa-saml/?auth_entry=login&next=/dashboard&idp=TEST', data['redirect_url'])

    def test_check_redirect_saml_login_when_not_found_user(self):
        # arrange
        OrgUsernameRuleFactory.create(prefix='PRE-', org=self.gacco_org)
        user = UserFactory.create(email='sample@sample.com', username='PRE-username1')
        # act
        response = self.client.post(self._url_check_redirect_saml_login, {
            'email': 'xxxxx@xxxx.com',
            'next': '/dashboard'
        })
        # assert
        self._assert_response_not_redirect(response)

    def test_check_redirect_saml_login_when_no_match_username_rule(self):
        # arrange
        OrgUsernameRuleFactory.create(prefix='PRE-', org=self.gacco_org)
        SsoConfigFactory.create(idp_slug='TEST', org=self.gacco_org)
        user = UserFactory.create(email='sample@sample.com', username='NG-PRE-username1')
        UserSocialAuth.objects.create(user=user, provider='tpa-saml', uid="TEST:xxxxx")
        # act
        response = self.client.post(self._url_check_redirect_saml_login, {
            'email': user.email,
            'next': '/dashboard'
        })
        # assert
        self._assert_response_not_redirect(response)

    def test_check_redirect_saml_login_when_no_user_social_auth(self):
        # arrange
        OrgUsernameRuleFactory.create(prefix='PRE-', org=self.gacco_org)
        SsoConfigFactory.create(idp_slug='TEST', org=self.gacco_org)
        user = UserFactory.create(email='sample@sample.com', username='PRE-username1')
        # act
        response = self.client.post(self._url_check_redirect_saml_login, {
            'email': user.email,
            'next': '/dashboard'
        })
        # assert
        self._assert_response_not_redirect(response)

    def test_check_redirect_saml_login_when_no_sso_config(self):
        # arrange
        OrgUsernameRuleFactory.create(prefix='PRE-', org=self.gacco_org)
        user = UserFactory.create(email='sample@sample.com', username='PRE-username1')
        UserSocialAuth.objects.create(user=user, provider='tpa-saml', uid="TEST:xxxxx")
        # act
        response = self.client.post(self._url_check_redirect_saml_login, {
            'email': user.email,
            'next': '/dashboard'
        })
        # assert
        self._assert_response_not_redirect(response)

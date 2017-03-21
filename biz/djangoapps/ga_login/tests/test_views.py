import ddt
import json
from mock import patch

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from django.utils.crypto import get_random_string

from biz.djangoapps.ga_contract.models import ContractAuth
from biz.djangoapps.ga_invitation.models import (
    INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE
)
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.ga_login.models import BizUser
from biz.djangoapps.ga_login.tests.factories import BizUserFactory


class LoginViewsTestBase(BizContractTestBase):

    def _url_index(self, url_code):
        return reverse('biz:login:index', kwargs={'url_code': url_code})

    def _url_submit(self):
        return reverse('biz:login:submit')

    @property
    def url_code(self):
        return ContractAuth.objects.get(contract=self.contract_auth).url_code

    @property
    def url_code_disabled(self):
        return ContractAuth.objects.get(contract=self.contract_auth_disabled).url_code

    @property
    def url_code_student_cannot_register(self):
        return ContractAuth.objects.get(contract=self.contract_auth_student_cannot_register).url_code

    def _assert_call(self, mock_patch, call_withes=None):
        call_withes = call_withes or []

        self.assertEqual(len(call_withes), mock_patch.call_count)
        for call_with in call_withes:
            mock_patch.assert_any_call(call_with)

    def setup_user(self, login_code=None, do_activate=True, do_login=True):
        self.username = get_random_string(16)
        self.password = get_random_string(8)
        self.email = self.username + '@test.com'
        self.user = self.create_account(
            self.username,
            self.email,
            self.password,
        )
        self.login_code = login_code
        if login_code:
            BizUserFactory.create(user=self.user, login_code=login_code)
        if do_activate:
            self.activate_user(self.email)
        if do_login:
            self.login(self.email, self.password)

        return self.user


class LoginViewsIndexTest(LoginViewsTestBase):

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_no_contract(self, warning_log):
        self.assert_request_status_code(404, self._url_index('hogehoge'))

        self._assert_call(warning_log, [
            "Not found contract with url_code:hogehoge"
        ])

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_disabled_contract(self, warning_log):
        self.assert_request_status_code(404, self._url_index(self.url_code_disabled))

        self._assert_call(warning_log, [
            "Disabled contract:{} with url_code:{}".format(self.contract_auth_disabled.id, self.url_code_disabled),
        ])

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_success(self, warning_log):
        self.assert_request_status_code(200, self._url_index(self.url_code))

        self._assert_call(warning_log)

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_logined_no_login_code(self, warning_log):
        self.setup_user()
        self.assert_request_status_code(404, self._url_index(self.url_code))

        self._assert_call(warning_log)

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_logined_without_contract_register(self, warning_log):
        self.setup_user('test-login-code')
        self.assert_request_status_code(404, self._url_index(self.url_code))

        self._assert_call(warning_log, [
            "Unknown login_code:{} with contract:{}".format(self.login_code, self.contract_auth.id)
        ])

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_logined_with_contract_register_input(self, warning_log):
        self.setup_user('test-login-code')
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(302, self._url_index(self.url_code))
        self.assertTrue(response.url.endswith(reverse('biz:invitation:confirm', kwargs={'invitation_code': self.contract_auth.invitation_code})))

        self._assert_call(warning_log)

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_logined_with_contract_register_register(self, warning_log):
        self.setup_user('test-login-code')
        self.create_contract_register(self.user, self.contract_auth, REGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(302, self._url_index(self.url_code))
        self.assertTrue(response.url.endswith(reverse('dashboard')))

        self._assert_call(warning_log)

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_logined_with_contract_register_unregister(self, warning_log):
        self.setup_user('test-login-code')
        self.create_contract_register(self.user, self.contract_auth, UNREGISTER_INVITATION_CODE)
        self.assert_request_status_code(404, self._url_index(self.url_code))

        self._assert_call(warning_log, [
            "Unregister status user:{} with contract:{}".format(self.user.id, self.contract_auth.id)
        ])

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_logined_with_contract_register_type_director_input(self, warning_log):
        self.setup_user('test-login-code')
        self.create_contract_register(self.user, self.contract_auth_student_cannot_register, INPUT_INVITATION_CODE)
        self.assert_request_status_code(404, self._url_index(self.url_code_student_cannot_register))

        self._assert_call(warning_log, [
            "Student can not be registered, status is input, user:{} contract:{}".format(self.user.id, self.contract_auth_student_cannot_register.id)
        ])

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_logined_with_contract_register_type_director_register(self, warning_log):
        self.setup_user('test-login-code')
        self.create_contract_register(self.user, self.contract_auth_student_cannot_register, REGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(302, self._url_index(self.url_code_student_cannot_register))
        self.assertTrue(response.url.endswith(reverse('dashboard')))

        self._assert_call(warning_log)

    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_logined_with_contract_register_type_director_unregister(self, warning_log):
        self.setup_user('test-login-code')
        self.create_contract_register(self.user, self.contract_auth_student_cannot_register, UNREGISTER_INVITATION_CODE)
        self.assert_request_status_code(404, self._url_index(self.url_code_student_cannot_register))

        self._assert_call(warning_log, [
            "Unregister status user:{} with contract:{}".format(self.user.id, self.contract_auth_student_cannot_register.id)
        ])


FEATURES_SQUELCH_PII_IN_LOGS_ENABLED = settings.FEATURES.copy()
FEATURES_SQUELCH_PII_IN_LOGS_ENABLED['SQUELCH_PII_IN_LOGS'] = True
FEATURES_SQUELCH_PII_IN_LOGS_DISABLED = settings.FEATURES.copy()
FEATURES_SQUELCH_PII_IN_LOGS_DISABLED['SQUELCH_PII_IN_LOGS'] = False


@ddt.ddt
class LoginViewsSubmitTest(LoginViewsTestBase):

    def setUp(self):
        super(LoginViewsSubmitTest, self).setUp()

        # Make mock to setup_user with LMS_SEGMENT_KEY.
        dummy_patcher = patch('student.views.analytics')
        dummy_patcher.start()
        self.addCleanup(dummy_patcher.stop)

        analytics_patcher = patch('biz.djangoapps.ga_login.views.analytics')
        self.mock_tracker = analytics_patcher.start()
        self.addCleanup(analytics_patcher.stop)

    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    @ddt.data(
        ({'url_code': 'hoge', 'login_code': 'hoge'}, None),
        ({'url_code': 'hoge', 'password': 'hoge'}, None),
        ({'login_code': 'hoge', 'password': 'hoge'}, None),
        ({'url_code': 'hoge', 'login_code': 'hoge', 'password': 'hoge'}, ["Not found contract with url_code:hoge"]),
    )
    @ddt.unpack
    def test_no_param_no_contract(self, data, warning_call_with, warning_log, audit_warning_log, critical_log, audit_critical_log):
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data=data)
        self.assertEqual(response.content, u"There was an error receiving your login information. Please email us.")

        self._assert_call(warning_log, warning_call_with)
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_ENABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_not_found_login_code_squelch_on(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user(do_login=False)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': 'hoge',
            'password': 'hoge',
        })
        self.assertEqual(response.content, u"Login code or password is incorrect.")

        self._assert_call(warning_log, [
            "Unknown login_code:{} with contract:{}".format('hoge', self.contract_auth.id),
            "Login failed contract:{0} - Unknown user".format(self.contract_auth.id),
        ])
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_DISABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_not_found_login_code_squelch_off(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user(do_login=False)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': 'hoge',
            'password': 'hoge',
        })
        self.assertEqual(response.content, u"Login code or password is incorrect.")

        self._assert_call(warning_log, [
            "Unknown login_code:{} with contract:{}".format('hoge', self.contract_auth.id),
            "Login failed contract:{0} - Unknown user {1}".format(self.contract_auth.id, 'hoge'),
        ])
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_ENABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_not_found_contract_register_squelch_on(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': self.login_code,
            'password': 'hoge',
        })
        self.assertEqual(response.content, u"Login code or password is incorrect.")

        self._assert_call(warning_log, [
            "Unknown login_code:{} with contract:{}".format(self.login_code, self.contract_auth.id),
            "Login failed contract:{0} - Unknown user".format(self.contract_auth.id),
        ])
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_DISABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_not_found_contract_register_squelch_off(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': self.login_code,
            'password': 'hoge',
        })
        self.assertEqual(response.content, u"Login code or password is incorrect.")

        self._assert_call(warning_log, [
            "Unknown login_code:{} with contract:{}".format(self.login_code, self.contract_auth.id),
            "Login failed contract:{0} - Unknown user {1}".format(self.contract_auth.id, self.login_code),
        ])
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_ENABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_found_contract_register_unregister_squelch_on(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth, UNREGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': self.login_code,
            'password': 'hoge',
        })
        self.assertEqual(response.content, u"Login code or password is incorrect.")

        self._assert_call(warning_log, [
            "Unregister status user:{} with contract:{}".format(self.user.id, self.contract_auth.id),
            "Login failed contract:{0} - Unknown user".format(self.contract_auth.id),
        ])
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_DISABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_found_contract_register_unregister_squelch_off(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth, UNREGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': self.login_code,
            'password': 'hoge',
        })
        self.assertEqual(response.content, u"Login code or password is incorrect.")

        self._assert_call(warning_log, [
            "Unregister status user:{} with contract:{}".format(self.user.id, self.contract_auth.id),
            "Login failed contract:{0} - Unknown user {1}".format(self.contract_auth.id, self.login_code),
        ])
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_ENABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_found_contract_register_type_director_input_squelch_on(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth_student_cannot_register, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code_student_cannot_register,
            'login_code': self.login_code,
            'password': self.password,
        })
        self.assertEqual(response.content, u"The invitation code has not been registered yet. Please ask your director to register invitation code.")

        self._assert_call(warning_log, [
            "Student can not be registered, status is input, contract:{0}, user.id:{1}".format(self.contract_auth_student_cannot_register.id, self.user.id),
        ])
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_DISABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_found_contract_register_type_director_input_squelch_off(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth_student_cannot_register, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code_student_cannot_register,
            'login_code': self.login_code,
            'password': self.password,
        })
        self.assertEqual(response.content, u"The invitation code has not been registered yet. Please ask your director to register invitation code.")

        self._assert_call(warning_log, [
            "Student can not be registered, status is input, contract:{0}, user {1}".format(self.contract_auth_student_cannot_register.id, self.login_code),
        ])
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    @patch('biz.djangoapps.ga_login.views.log.debug')
    def test_found_contract_register_type_director_register(self, debug_log, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth_student_cannot_register, REGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(204, self._url_submit(), 'POST', data={
            'url_code': self.url_code_student_cannot_register,
            'login_code': self.login_code,
            'password': self.password,
        })
        self.assertEqual(response.content, u"")

        self.assertEqual(0, self.mock_tracker.identify.call_count)
        self.assertEqual(0, self.mock_tracker.track.call_count)

        self._assert_call(debug_log)
        self._assert_call(warning_log)
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_ENABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_found_contract_register_type_director_unregister_squelch_on(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth_student_cannot_register, UNREGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code_student_cannot_register,
            'login_code': self.login_code,
            'password': 'hoge',
        })
        self.assertEqual(response.content, u"Login code or password is incorrect.")

        self._assert_call(warning_log, [
            "Unregister status user:{} with contract:{}".format(self.user.id, self.contract_auth_student_cannot_register.id),
            "Login failed contract:{0} - Unknown user".format(self.contract_auth_student_cannot_register.id),
        ])
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_DISABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_found_contract_register_type_director_unregister_squelch_off(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth_student_cannot_register, UNREGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code_student_cannot_register,
            'login_code': self.login_code,
            'password': 'hoge',
        })
        self.assertEqual(response.content, u"Login code or password is incorrect.")

        self._assert_call(warning_log, [
            "Unregister status user:{} with contract:{}".format(self.user.id, self.contract_auth_student_cannot_register.id),
            "Login failed contract:{0} - Unknown user {1}".format(self.contract_auth_student_cannot_register.id, self.login_code),
        ])
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_ENABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_not_authenticate_squelch_on(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': self.login_code,
            'password': 'hoge',
        })
        self.assertEqual(response.content, u"Login code or password is incorrect.")

        self._assert_call(warning_log)
        self._assert_call(audit_warning_log, [
            "Login failed contract:{0} - password for user.id:{1} is invalid".format(self.contract_auth.id, self.user.id),
        ])
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_DISABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_not_authenticate_squelch_off(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(403, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': self.login_code,
            'password': 'hoge',
        })
        self.assertEqual(response.content, u"Login code or password is incorrect.")

        self._assert_call(warning_log)
        self._assert_call(audit_warning_log, [
            "Login failed contract:{0} - password for {1} is invalid".format(self.contract_auth.id, self.login_code),
        ])
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(LMS_SEGMENT_KEY=None)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    @patch('biz.djangoapps.ga_login.views.log.debug')
    def test_success(self, debug_log, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(204, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': self.login_code,
            'password': self.password,
        })
        self.assertEqual(response.content, u"")

        self.assertEqual(0, self.mock_tracker.identify.call_count)
        self.assertEqual(0, self.mock_tracker.track.call_count)

        self._assert_call(debug_log)
        self._assert_call(warning_log)
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(LMS_SEGMENT_KEY='hoge')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    @patch('biz.djangoapps.ga_login.views.log.debug')
    def test_success_analytics_track(self, debug_log, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(204, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': self.login_code,
            'password': self.password,
        })
        self.assertEqual(response.content, u"")

        self.assertEqual(1, self.mock_tracker.identify.call_count)
        self.assertEqual(1, self.mock_tracker.track.call_count)

        self._assert_call(debug_log)
        self._assert_call(warning_log)
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    @patch('biz.djangoapps.ga_login.views.log.debug')
    def test_success_remember(self, debug_log, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(204, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': self.login_code,
            'password': self.password,
            'remember': 'true',
        })
        self.assertEqual(response.content, u"")

        self._assert_call(debug_log, [
            "Setting user session to never expire"
        ])
        self._assert_call(warning_log)
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    @patch('biz.djangoapps.ga_login.views.log.debug')
    def test_fail(self, debug_log, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)
        with self.assertRaises(Exception), patch('biz.djangoapps.ga_login.views.login', side_effect=Exception):
            response = self.assert_request_status_code(500, self._url_submit(), 'POST', data={
                'url_code': self.url_code,
                'login_code': self.login_code,
                'password': self.password,
                'remember': 'true',
            })

        self._assert_call(debug_log)
        self._assert_call(warning_log)
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log, [
            "Login failed - Could not create session. Is memcached running?"
        ])
        self._assert_call(audit_critical_log, [
            "Login failed - Could not create session. Is memcached running?"
        ])

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_ENABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_no_activate_squelch_on(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False, do_activate=False)
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)
        with patch('biz.djangoapps.ga_login.views.reactivation_email_for_user') as patch_reactivation_email_for_user:
            response = self.assert_request_status_code(400, self._url_submit(), 'POST', data={
                'url_code': self.url_code,
                'login_code': self.login_code,
                'password': self.password,
            })
            patch_reactivation_email_for_user.assert_called_once_with(self.user)

        self.assertEqual(
            response.content,
            u"This account has not been activated. We have sent another activation message. Please check your email for the activation instructions."
        )

        self._assert_call(warning_log)
        self._assert_call(audit_warning_log, [
            "Login failed contract:{0} - Account not active for user.id:{1}, resending activation".format(self.contract_auth.id, self.user.id)
        ])
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @override_settings(FEATURES=FEATURES_SQUELCH_PII_IN_LOGS_DISABLED)
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    def test_no_activate_squelch_off(self, warning_log, audit_warning_log, critical_log, audit_critical_log):
        self.setup_user('Test-Login-Code', do_login=False, do_activate=False)
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)
        with patch('biz.djangoapps.ga_login.views.reactivation_email_for_user') as patch_reactivation_email_for_user:
            response = self.assert_request_status_code(400, self._url_submit(), 'POST', data={
                'url_code': self.url_code,
                'login_code': self.login_code,
                'password': self.password,
            })
            patch_reactivation_email_for_user.assert_called_once_with(self.user)

        self.assertEqual(
            response.content,
            u"This account has not been activated. We have sent another activation message. Please check your email for the activation instructions."
        )

        self._assert_call(warning_log)
        self._assert_call(audit_warning_log, [
            "Login failed contract:{0} - Account not active for user {1}, resending activation".format(self.contract_auth.id, self.login_code)
        ])
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

    @patch('biz.djangoapps.ga_login.views.LoginFailures.clear_lockout_counter')
    @patch('biz.djangoapps.ga_login.views.LoginFailures.increment_lockout_counter')
    @ddt.data(
        ([True,True], [True], None, 403, True, False, 0, 0), # lock
        ([True,True], [False], None, 204, False, False, 0, 1), # ok
        ([True,True], [True], 'hoge', 403, True, False, 0, 0), # lock
        ([True,True], [False], 'hoge', 403, False, True, 1, 0), # no auth
        ([False,False], [True], None, 204, False, False, 0, 0), # ok
        ([False,False], [False], None, 204, False, False, 0, 0), # ok
        ([False,False], [True], 'hoge', 403, False, True, 0, 0), # no auth
        ([False,False], [False], 'hoge', 403, False, True, 0, 0), # no auth
    )
    @ddt.unpack
    def test_login_failures(self, is_feature_enabled, is_user_locked_out, password, status_code, lock_user, not_authenticate_user,
                            increment_lockout_counter_call_count, clear_lockout_counter_call_count,
                            increment_lockout_counter, clear_lockout_counter):
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)
        with patch(
            'biz.djangoapps.ga_login.views.LoginFailures.is_feature_enabled', side_effect=is_feature_enabled
        ), patch(
            'biz.djangoapps.ga_login.views.LoginFailures.is_user_locked_out', side_effect=is_user_locked_out
        ):
            response = self.assert_request_status_code(status_code, self._url_submit(), 'POST', data={
                'url_code': self.url_code,
                'login_code': self.login_code,
                'password': password or self.password,
            })

        if lock_user:
            self.assertEqual(
                response.content,
                u"This account has been temporarily locked due to excessive login failures. Try again later."
            )
        elif not_authenticate_user:
            self.assertEqual(response.content, u"Login code or password is incorrect.")
        else:
            self.assertEqual(response.content, u"")

        self.assertEqual(increment_lockout_counter_call_count, increment_lockout_counter.call_count)
        self.assertEqual(clear_lockout_counter_call_count, clear_lockout_counter.call_count)

    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.critical')
    @patch('biz.djangoapps.ga_login.views.log.critical')
    @patch('biz.djangoapps.ga_login.views.AUDIT_LOG.warning')
    @patch('biz.djangoapps.ga_login.views.log.warning')
    @patch('biz.djangoapps.ga_login.views.log.debug')
    def test_success_same_login_code(self, debug_log, warning_log, audit_warning_log, critical_log, audit_critical_log):
        # first user, do not use test
        self.setup_user('Test-Login-Code', do_login=False)
        self.create_contract_register(self.user, self.contract_auth_disabled, INPUT_INVITATION_CODE)

        # second user, to use test
        self.setup_user(self.login_code, do_login=False)
        self.create_contract_register(self.user, self.contract_auth, INPUT_INVITATION_CODE)

        # assert users have same login-code
        self.assertEquals(2, BizUser.objects.filter(login_code=self.login_code).count())

        response = self.assert_request_status_code(204, self._url_submit(), 'POST', data={
            'url_code': self.url_code,
            'login_code': self.login_code,
            'password': self.password,
        })
        self.assertEqual(response.content, u"")

        self.assertEqual(0, self.mock_tracker.identify.call_count)
        self.assertEqual(0, self.mock_tracker.track.call_count)

        self._assert_call(debug_log)
        self._assert_call(warning_log)
        self._assert_call(audit_warning_log)
        self._assert_call(critical_log)
        self._assert_call(audit_critical_log)

"""
Test for contract_operation util
"""
from mock import patch

from django.test.utils import override_settings

from biz.djangoapps.util.tests.testcase import BizViewTestBase
from biz.djangoapps.ga_contract_operation.utils import send_mail


class SendMailTest(BizViewTestBase):

    @override_settings(DEFAULT_FROM_EMAIL='test@example.com')
    @patch('biz.djangoapps.ga_contract_operation.utils.django_send_mail')
    def test_no_replace(self, django_send_mail):
        self.setup_user()

        send_mail(self.user, 'Mail Subject {email_address} {username}', 'Mail Body {emailaddress} {user_name}')

        django_send_mail.assert_called_with(
            'Mail Subject {email_address} {username}',
            'Mail Body {emailaddress} {user_name}',
            'test@example.com',
            [self.user.email],
        )

    @override_settings(DEFAULT_FROM_EMAIL='test@example.com')
    @patch('biz.djangoapps.ga_contract_operation.utils.django_send_mail')
    def test_with_replace(self, django_send_mail):
        self.setup_user()

        send_mail(self.user, 'Mail Subject {email_address} {username}', 'Mail Body {emailaddress} {user_name}', {
            'user_name': self.user.username,
            'email_address': self.user.email,
        })

        django_send_mail.assert_called_with(
            'Mail Subject %s {username}' % self.user.email,
            'Mail Body {emailaddress} %s' % self.user.username,
            'test@example.com',
            [self.user.email],
        )

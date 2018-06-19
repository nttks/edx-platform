"""
Test for mail util
"""
from mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from courseware.tests.factories import UserFactory
from openedx.core.lib.ga_mail_utils import send_mail


class SendMailTest(TestCase):

    @override_settings(DEFAULT_FROM_EMAIL='test@example.com')
    @patch('openedx.core.lib.ga_mail_utils.django_send_mail')
    def test_no_replace(self, django_send_mail):
        self.user = UserFactory.create()

        send_mail(self.user, 'Mail Subject {email_address} {username}', 'Mail Body {emailaddress} {user_name}')

        django_send_mail.assert_called_with(
            'Mail Subject {email_address} {username}',
            'Mail Body {emailaddress} {user_name}',
            'test@example.com',
            [self.user.email],
        )

    @override_settings(DEFAULT_FROM_EMAIL='test@example.com')
    @patch('openedx.core.lib.ga_mail_utils.django_send_mail')
    def test_with_replace(self, django_send_mail):
        self.user = UserFactory.create()

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

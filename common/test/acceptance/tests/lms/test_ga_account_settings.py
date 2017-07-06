# -*- coding: utf-8 -*-
"""
End-to-end tests for the Account Settings page.
"""
from .test_account_settings import AccountSettingsTestMixin
from ..ga_helpers import GaccoTestMixin, SUPER_USER_INFO
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.ga_django_admin import DjangoAdminPage


class GaAccountSettingsPageTest(AccountSettingsTestMixin, GaccoTestMixin):
    """
    Tests that verify behaviour of the Account Settings page.
    """

    def setUp(self):
        """
        Initialize account and pages.
        """
        super(GaAccountSettingsPageTest, self).setUp()

    def _get_basic_account_information_sections(self, hidden_email=False):
        fields = [
            'Username',
            'Full Name',
            'Email Address',
            'Password',
            'Language',
        ]
        if hidden_email:
            fields.pop(2)
        return {
            'title': 'Basic Account Information (required)',
            'fields': fields
        }

    def _get_additional_information_sections(self):
        return {
            'title': 'Additional Information (optional)',
            'fields': [
                'Education Completed',
                'Gender',
                'Year of Birth',
            ]
        }

    def _get_other_procedures_sections(self):
        return {
            'title': 'Other procedures',
            'fields': [
                'Invitation Code',
                'Resign',
            ]
        }

    def _get_connected_accounts_sections(self):
        return {
            'title': 'Connected Accounts',
            'fields': [
                'Dummy',
                'Facebook',
                'Google',
            ]
        }

    def _login_get_userid(self, user_info):
        auto_auth_page = AutoAuthPage(self.browser, username=user_info['username'], email=user_info['email']).visit()
        return auto_auth_page.get_user_id()

    def test_none_hidden_emailsetting_account_settings_page(self):
        """
        Scenario: Since it is not set by Django admin, confirm that the e-mail selection is displayed on the page.
        """
        self.username, self.user_id = self.log_in_as_unique_user()
        self.visit_account_settings_page()

        expected_sections_structure = [
            self._get_basic_account_information_sections(),
            self._get_additional_information_sections(),
            self._get_other_procedures_sections(),
            self._get_connected_accounts_sections()
        ]
        self.assertEqual(self.account_settings_page.sections_structure(), expected_sections_structure)

    def test_disable_hidden_emailsetting_account_settings_page(self):
        """
        Scenario: Since it is set by Django admin, confirm that the e-mail selection is not displayed on the page.
        """
        target_user = self.register_user()
        target_id = self._login_get_userid(target_user)

        self.switch_to_user(SUPER_USER_INFO)

        # set Django admin disable hidden e-mail settings
        DjangoAdminPage(self.browser).visit().click_add('ga_optional', 'useroptionalconfiguration').input({
            'enabled': False,
            'key': 'hide-email-settings',
            'user': target_id,
        }).save()

        self.switch_to_user(target_user)
        self.visit_account_settings_page()
        expected_sections_structure = [
            self._get_basic_account_information_sections(),
            self._get_additional_information_sections(),
            self._get_other_procedures_sections(),
            self._get_connected_accounts_sections()
        ]
        self.assertEqual(self.account_settings_page.sections_structure(), expected_sections_structure)

    def test_enable_hidden_emailsetting_account_settings_page(self):
        """
        Scenario: Since it is set by Django admin, confirm that the e-mail selection is not displayed on the page.
        """
        target_user = self.register_user()
        target_id = self._login_get_userid(target_user)

        self.switch_to_user(SUPER_USER_INFO)

        # set Django admin enable hidden e-mail settings
        DjangoAdminPage(self.browser).visit().click_add('ga_optional', 'useroptionalconfiguration').input({
            'enabled': True,
            'key': 'hide-email-settings',
            'user': target_id,
        }).save()

        self.switch_to_user(target_user)
        self.visit_account_settings_page()
        expected_sections_structure = [
            self._get_basic_account_information_sections(hidden_email=True),
            self._get_additional_information_sections(),
            self._get_other_procedures_sections(),
            self._get_connected_accounts_sections()
        ]
        self.assertEqual(self.account_settings_page.sections_structure(), expected_sections_structure)

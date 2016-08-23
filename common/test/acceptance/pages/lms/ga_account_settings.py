"""
Base class for account settings page.
"""
from bok_choy.promise import EmptyPromise

from .account_settings import AccountSettingsPage as EdXAccountSettingsPage


class AccountSettingsPage(EdXAccountSettingsPage):
    """
    Tests for Account Settings Page.
    """

    @property
    def receive_email_text(self):
        query = self.q(css='#u-field-link-receive_email+span')
        return query.text[0] if query.present else None

    @property
    def is_optin_receive_email(self):
        return self.receive_email_text == u'Stop delivery'

    @property
    def is_optout_receive_email(self):
        return self.receive_email_text == u'Resume delivery'
    
    @property
    def visible_receive_email(self):
        return self.q(css='div.u-field-receive_email').visible

    def click_receive_email(self):
        self.click_on_link_in_link_field('receive_email')
        self.wait_for_ajax()
        return self.wait_for_loading_receive_email()

    def wait_for_loading_receive_email(self):
        self.wait_for_receive_email()
        EmptyPromise(
            lambda: self.is_optin_receive_email or self.is_optout_receive_email,
            "Loading receive_email is in progress."
        ).fulfill()
        return self

    def wait_for_receive_email(self):
        EmptyPromise(
            lambda: self.q(css='div.u-field-receive_email').present,
            "receive_email is present."
        ).fulfill()
        return self

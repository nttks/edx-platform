"""
Pages for biz invitation
"""
from . import BASE_URL
from .ga_navigation import BizNavPage
from .ga_w2ui import W2uiMixin


class BizInvitationPage(BizNavPage, W2uiMixin):
    """
    Invitation page
    """

    @property
    def url(self):
        return '{base}/biz/invitation/'.format(base=BASE_URL)

    def is_browser_on_page(self):
        """
        Check if browser is showing correct page.
        """
        return 'Invitation Code' in self.browser.title

    def input_invitation_code(self, value):
        """
        Input invitation code
        """
        self.q(css='input[name=invitation_code]').fill(value)
        return self

    def click_register_button(self):
        """
        Click the register button
        """
        self.q(css='#form-invitation-code input[type=submit]').click()
        return self

    @property
    def messages(self):
        """Return a list of errors displayed. """
        return self.q(css="#message-invitation-code").text


class BizInvitationConfirmPage(BizNavPage, W2uiMixin):
    """
    Invitation confirm page
    """

    def is_browser_on_page(self):
        """
        Check if browser is showing correct page.
        """
        return 'Confirm Invitation Code' in self.browser.title

    def input_additional_info(self, value, index):
        """
        Input additional info
        """
        self.q(css='.additional-input').nth(index).fill(value)
        return self

    def click_register_button(self):
        """
        Click the register button
        """
        self.q(css='#form-invitation-code input[type=submit]').click()
        return self

    @property
    def additional_messages(self):
        """Return a list of errors displayed to the view. """
        return self.q(css=".additional .error-message").text

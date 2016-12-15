"""
Pages for biz invitation
"""
from bok_choy.page_object import PageObject

from . import BASE_URL


class BizInvitationPage(PageObject):
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


class BizInvitationConfirmPage(PageObject):
    """
    Invitation confirm page
    """

    def __init__(self, browser, invitation_code):
        super(BizInvitationConfirmPage, self).__init__(browser)
        self.invitation_code = invitation_code

    @property
    def url(self):
        return '{base}/biz/invitation/{invitation_code}'.format(
            base=BASE_URL,
            invitation_code=self.invitation_code
        )

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

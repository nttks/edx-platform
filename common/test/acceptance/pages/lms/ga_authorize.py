"""
Pages for authorize
"""
import urllib

from bok_choy.page_object import PageObject
from . import BASE_URL

from .ga_login import LoginPage as _LoginPage


class AuthorizePage(PageObject):
    """
    Authorize page
    """
    def __init__(self, browser, response_type=None, client_id=None, redirect_uri=None, scope=None, state=None, nonce=None):
        super(AuthorizePage, self).__init__(browser)
        self.response_type = response_type
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.state = state
        self.nonce = nonce

    @property
    def url(self):
        query_dict = dict()
        if self.response_type:
            query_dict['response_type'] = self.response_type
        if self.client_id:
            query_dict['client_id'] = self.client_id
        if self.redirect_uri:
            query_dict['redirect_uri'] = self.redirect_uri
        if self.scope:
            query_dict['scope'] = self.scope
        if self.state:
            query_dict['state'] = self.state
        if self.nonce:
            query_dict['nonce'] = self.nonce
        return '{base}/oauth2/authorize/?{query_string}'.format(
            base=BASE_URL,
            query_string=urllib.urlencode(query_dict)
        )

    def is_browser_on_page(self):
        # This page has no view. Just redirect to LoginPage or AuthorizeConfirmPage
        if self.browser.get_cookie('edxloggedin'):
            return AuthorizeConfirmPage(self.browser).is_browser_on_page()
        else:
            return LoginPage(self.browser).is_browser_on_page()


class AuthorizeConfirmPage(PageObject):
    """
    Authorize confirm page
    """

    @property
    def url(self):
        return '{base}/oauth2/authorize/confirm'.format(base=BASE_URL)

    def is_browser_on_page(self):
        return self.q(css='.authorize-title').present

    def get_title(self):
        return self.q(css='.authorize-title').text[0]

    def get_scopes(self):
        return [
            href.split('#')[1].split('-')[2]
            for href in self.q(css='ul.authorize-scope li a.authorize-info').attrs('href')
        ]

    def get_error_code(self):
        return self.q(css='.authorize-error-message p')[0].text

    def get_error_description(self):
        return self.q(css='.authorize-error-message p')[1].text

    def click_approve(self):
        """
        Click the Approve button
        """
        self.q(css='button.action-authorize').click()

    def click_cancel(self):
        """
        Click the Cancel button
        """
        self.q(css='button.action-cancel').click()


class LoginPage(_LoginPage):
    """
    Login page for OIDC
    """

    def submit(self):
        """
        Submit registration info to create an account.
        """
        self.q(css='button#submit').first.click()

        # The next page is the authorize confirm page; make sure it loads
        authroize = AuthorizeConfirmPage(self.browser)
        authroize.wait_for_page()
        return authroize

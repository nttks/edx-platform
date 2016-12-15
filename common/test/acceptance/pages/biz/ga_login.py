"""
Login page of biz.
"""
from bok_choy.page_object import PageObject

from . import BASE_URL


class BizLoginPage(PageObject):

    def __init__(self, browser, url_code, not_found=False):
        super(BizLoginPage, self).__init__(browser)
        self.url_code = url_code
        self.not_found = not_found

    @property
    def url(self):
        return '{base}/biz/login/{url_code}'.format(
            base=BASE_URL,
            url_code=self.url_code
        )

    def is_browser_on_page(self):
        if self.not_found:
            return self.q(css='#summary>h1').present and u'Page not found' in self.q(css='#summary>h1').first.text[0]
        else:
            return self.q(css='#login-anchor').present and self.q(css='.login-button').visible

    @property
    def error_messages(self):
        return self.q(css='.submission-error li').text

    def input(self, login_code='', password=''):
        self.wait_for_element_visibility('#login-login_code', 'Email field is shown')
        self.q(css='#login-login_code').fill(login_code)
        self.q(css='#login-password').fill(password)
        return self

    def click_login(self):
        self.q(css='.login-button').click()
        self.wait_for_ajax()
        return self

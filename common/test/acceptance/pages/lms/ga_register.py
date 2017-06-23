"""Registration pages"""

from bok_choy.page_object import PageObject
from . import BASE_URL


class ActivationPage(PageObject):
    """
    Account activate page.
    """

    def __init__(self, browser, activation_key):
        super(ActivationPage, self).__init__(browser)
        self.activation_key = activation_key

    @property
    def url(self):
        return "{base}/activate/{activation_key}".format(base=BASE_URL, activation_key=self.activation_key)

    def is_browser_on_page(self):
        return self.q(css='section.activation').present

    @property
    def complete_message(self):
        return self.q(css='section.message p').text[0]

    def click_login_button(self):
        self.q(css=".cta-login").click()


class RegisterPage(PageObject):
    """
    register page.
    """

    url = BASE_URL + "/register"

    def is_browser_on_page(self):
        return self.q(css=".login-register").present

    def click_top_page(self):
        self.q(css='a.top-page').first.click()


class LoginPage(PageObject):
    """
    Login page for the LMS.
    """

    url = BASE_URL + "/login"

    def is_browser_on_page(self):
        return self.q(css='.login-register').present

    def click_top_page(self):
        self.q(css='a.top-page').first.click()

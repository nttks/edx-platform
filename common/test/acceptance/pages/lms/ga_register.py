"""Registration pages"""

from bok_choy.page_object import PageObject
from . import BASE_URL
from .ga_dashboard import DashboardPage
from .login_and_register import RegisterPage as EdXRegisterPage

class RegisterPage(EdXRegisterPage):
    """
    Account registration page.
    """

    def __init__(self, browser):
        super(RegisterPage, self).__init__(browser, None)

    @property
    def url(self):
        return "{base}/register".format(base=BASE_URL)

    def is_browser_on_page(self):
        return any([
            'educational' in title.lower()
            for title in self.q(css='span.title-sub').text
        ])

    def submit(self):
        """
        Submit registration info to create an account.
        """
        self.q(css='button#submit').first.click()

        # The next page is the dashboard; make sure it loads
        dashboard = DashboardPage(self.browser)
        dashboard.wait_for_page()
        return dashboard


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

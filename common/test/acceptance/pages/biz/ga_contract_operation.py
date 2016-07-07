"""
Contract operation pages of biz.
"""
from . import BASE_URL
from .ga_navigation import BizNavPage
from .ga_w2ui import W2uiMixin


class BizStudentsPage(BizNavPage, W2uiMixin):
    url = "{base}/biz/contract_operation/students".format(base=BASE_URL)

    def is_browser_on_page(self):
        return self.pagetitle == u'Students List'


class BizRegisterStudentsPage(BizNavPage, W2uiMixin):
    """
    Register students page
    """

    @property
    def url(self):
        return '{base}/biz/contract_operation/register_students'.format(base=BASE_URL)

    def is_browser_on_page(self):
        """
        Check if browser is showing the page.
        """
        return 'Register Students' in self.browser.title

    def input_students(self, value):
        """
        Input students info

        Arguments:
            value : target students
        """
        self.q(css='textarea#list-students').fill(value)
        return self

    def click_register_button(self):
        """
        Click the register button
        """
        self.q(css='#register-btn').click()
        self.wait_for_ajax()

    @property
    def messages(self):
        """Return a list of errors displayed to the list view. """
        return self.q(css="div.main ul.messages li").text

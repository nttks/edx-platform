"""
Pages for biz contract
"""
from . import BASE_URL
from .ga_navigation import BizNavPage
from .ga_w2ui import W2uiMixin


class BizContractPage(BizNavPage, W2uiMixin):
    """
    Contract list page
    """

    def __init__(self, browser):
        """
        Initialize the page.

        Arguments:
            browser (Browser): The browser instance.
        """
        super(BizContractPage, self).__init__(browser)

    @property
    def url(self):
        return '{base}/biz/contract/'.format(base=BASE_URL)

    def is_browser_on_page(self):
        """
        Check if browser is showing correct page.
        """
        return 'Contract List' in self.browser.title

    def click_register_button(self, wait_for_page=False):
        """
        Click the register button
        """
        self.q(css='#register-btn').click()
        if wait_for_page:
            return BizContractDetailPage(self.browser).wait_for_page()
        return self

    @property
    def messages(self):
        """Return a list of errors displayed to the list view. """
        return self.q(css="ul.messages").text


class BizContractDetailPage(BizNavPage, W2uiMixin):
    """
    Contract detail page
    """
    url = None

    def __init__(self, browser, href=None):
        """
        Initialize the page.

        Arguments:
            browser (Browser): The browser instance.
            href : The page url.
        """
        super(BizContractDetailPage, self).__init__(browser)

    def is_browser_on_page(self):
        return 'Contract Detail' in self.browser.title

    def input(self, contract_name='', contract_type='', register_type='', invitation_code='', start_date='', end_date='',
              contractor_organization=''):
        """
        Input contract info
        """
        self.q(css='input#id_contract_name').fill(contract_name)
        self.q(css='select#id_contract_type>option[value="{}"]'.format(contract_type)).first.click()
        self.q(css='select#id_register_type>option[value="{}"]'.format(register_type)).first.click()
        self.q(css='input#id_start_date').fill(start_date)
        self.q(css='input#id_end_date').fill(end_date)
        self.q(css='input#id_invitation_code').fill(invitation_code)
        self.q(css='select#id_contractor_organization>option[value="{}"]'.format(contractor_organization)).first.click()
        return self

    def select_contractor_organization(self, name):
        self.q(css='select#id_contractor_organization>option').filter(lambda el: el.text.strip() == name).first.click()
        return self

    def add_detail_info(self, value, index):
        """
        Click add contract details link and input value for it
        """
        self.q(css='a#add-detail').click()
        self.input_detail_info(value, index)
        return self

    def input_detail_info(self, value, index):
        """
        Input contract detail info
        """
        self.q(css='select[name=detail_course]>option[value="{}"]'.format(value)).nth(index).first.click()
        return self

    def add_additional_info(self, value, index):
        """
        Click add additional info link and input value for it
        """
        self.q(css='a#add-additional').click()
        self.input_additional_info(value, index)
        return self

    def input_additional_info(self, value, index):
        """
        Input additional info
        """
        self.q(css='input[name=additional_info_display_name]').nth(index).fill(value)
        return self

    def click_register_button(self):
        """
        Click the register button
        """
        self.q(css='input#register-btn').click()
        return self

    def click_delete_button(self):
        """
        Click the delete button
        """
        self.q(css='#delete-btn').first.click()
        return self.wait_for_popup_enable()

    @property
    def contract_field_errors(self):
        """Return a error list of contract fields displayed to the contract info. """
        return [el.text for el in self.q(css='div#main-info .err-msg').results]

    @property
    def main_info_error(self):
        """Return a error displayed to the contract info. """
        return self.q(css='div#main-info .errorlist li').text[0]

    @property
    def detail_info_error(self):
        """Return a error displayed to the contract detail info. """
        return self.q(css='div#detail-container .errorlist li').text[0]

    @property
    def additional_info_error(self):
        """Return a error displayed to the contract additional_info. """
        return self.q(css='div#additional-container .errorlist li').text[0]

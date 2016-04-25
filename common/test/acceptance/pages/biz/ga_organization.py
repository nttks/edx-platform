"""
Organization page of biz.
"""

from bok_choy.page_object import PageObject

from . import BASE_URL
from .ga_navigation import BizNavPage
from .ga_w2ui import W2uiMixin


class BizOrganizationPage(BizNavPage, W2uiMixin):

    url = "{base}/biz/organization/".format(base=BASE_URL)

    def is_browser_on_page(self):
        return self.pagetitle == u'Organization List'

    def click_add(self):
        self.q(css='input#register-btn').first.click()
        return BizOrganizationShowRegisterPage(self.browser).wait_for_page()


class BizOrganizationShowRegisterPage(BizNavPage):

    url = "{base}/biz/organization/show_register".format(base=BASE_URL)

    def is_browser_on_page(self):
        return self.pagetitle == u'Organization Detail'

    @property
    def input_error_messages(self):
        return [t.strip() for t in self.q(css='input[type="text"]~span.err-msg').text]

    def input(self, org_name, org_code):
        self.q(css='input#id_org_name').fill(org_name)
        self.q(css='input#id_org_code').fill(org_code)
        return self

    def click_register(self, success=True):
        self.q(css='input#register-btn').first.click()
        if success:
            return BizOrganizationPage(self.browser).wait_for_page()
        else:
            return BizOrganizationRegisterPage(self.browser).wait_for_page()


class BizOrganizationRegisterPage(BizOrganizationShowRegisterPage):

    url = "{base}/biz/organization/register".format(base=BASE_URL)


class BizOrganizationDetailPage(BizOrganizationShowRegisterPage, W2uiMixin):

    def __init__(self, browser, href):
        super(BizOrganizationDetailPage, self).__init__(browser)
        self.organization_id = href.split('/')[-1]

    @property
    def url(self):
        return "{base}/biz/organization/detail/{organization_id}".format(base=BASE_URL, organization_id=self.organization_id)

    def click_register(self, success=True):
        self.q(css='input#register-btn').first.click()
        if success:
            return BizOrganizationPage(self.browser).wait_for_page()
        else:
            return BizOrganizationEditPage(self.browser, self.organization_id).wait_for_page()

    def click_delete(self):
        self.q(css='input#delete-btn').first.click()
        return self.wait_for_popup_enable()


class BizOrganizationEditPage(BizOrganizationDetailPage):

    def __init__(self, browser, organization_id):
        super(BizOrganizationEditPage, self).__init__(browser)
        self.organization_id = organization_id

    @property
    def url(self):
        return "{base}/biz/organization/edit/{organization_id}".format(base=BASE_URL, organization_id=self.organization_id)

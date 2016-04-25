"""
Navigation page of biz.
"""

from bok_choy.page_object import PageObject, unguarded

from . import BASE_URL


class BizNavPage(PageObject):

    url = "{base}/biz/".format(base=BASE_URL)

    def is_browser_on_page(self):
        return self.q(css='div.change-role>a.change-role-button').present

    @property
    @unguarded
    def pagetitle(self):
        pagetitle = self.q(css='div.main>div.biz-wrap>h1')
        return pagetitle.first.text[0] if pagetitle.present else None

    @property
    def messages(self):
        return [t.strip() for t in self.q(css='div.main>div.biz-wrap>ul.messages>li').text]

    def click_organization(self):
        # Import in func for cross reference
        from .ga_organization import BizOrganizationPage

        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/organization/"]').first.click()
        return BizOrganizationPage(self.browser).wait_for_page()

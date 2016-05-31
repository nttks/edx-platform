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

    def wait_for_message(self, message):
        self.wait_for(lambda: message in self.messages, 'Found message({}) on page'.format(message))
        return self

    def click_organization(self):
        # Import in func for cross reference
        from .ga_organization import BizOrganizationPage

        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/organization/"]').first.click()
        return BizOrganizationPage(self.browser).wait_for_page()

    def click_contract(self):
        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/contract/"]').first.click()
        from .ga_contract import BizContractPage
        return BizContractPage(self.browser).wait_for_page()

    def click_manager(self):
        # Import in func for cross reference
        from .ga_manager import BizManagerPage

        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/manager/"]').first.click()
        manager_page = BizManagerPage(self.browser).wait_for_page()
        manager_page.wait_for_ajax()
        return manager_page.wait_for_lock_absence()

    def click_survey(self):
        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/course_operation/survey"]').first.click()
        from common.test.acceptance.pages.biz.ga_survey import BizSurveyPage
        return BizSurveyPage(self.browser).wait_for_page()

    def change_role(self, org_id, contract_name, course_id):
        # Show role selection modal
        self.q(css='.change-role-button').first.click()
        self.wait_for_element_visibility('#role-selection-modal', 'visit biz change role dialog')
        # Choice options
        self.q(css='select#org-id>option[value="{}"]'.format(org_id)).first.click()
        for option in self.q(css='select#contract-id option').results:
            if contract_name == option.text:
                option.click()
        self.q(css='select#course-id>option[value="{}"]'.format(course_id)).first.click()
        self.q(css='button#save-selection').first.click()
        return self.wait_for_page()

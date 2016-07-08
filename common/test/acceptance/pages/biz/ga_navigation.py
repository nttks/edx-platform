"""
Navigation page of biz.
"""

from bok_choy.page_object import PageObject, unguarded

from . import BASE_URL


NO_SELECTED = '--'

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

    @property
    def modal_message(self):
        return self.q(css='section#role-selection-modal .error-message').text[0]

    def change_manage_target(self, org_name=None, contract_name=None, course_name=None, cancel=False, close=True):
        # view modal
        self.q(css='div.change-role>a.change-role-button').first.click()
        self.wait_for_element_visibility('section#role-selection-modal', 'Role selection modal is visible')

        # select org
        if org_name:
            if org_name not in self._org_names:
                raise ValueError('Not found org:{} not in {}'.format(org_name, self._org_names))
            self.q(css='#role-selection-modal #org-id>option').filter(lambda el: el.text.strip() == org_name).first.click()

            if contract_name and NO_SELECTED != org_name:
                # wait contract enabled
                self.wait_for(
                    lambda: bool(self.q(css='#role-selection-modal #contract-id').filter(lambda el: el.is_enabled()).results),
                    'Selectbox of contract is enabled.'
                )

        # select contract
        if contract_name:
            if contract_name not in self._contract_names:
                raise ValueError('Not found contract:{} not in {}'.format(contract_name, self._contract_names))
            self.q(css='#role-selection-modal #contract-id>option').filter(lambda el: el.text.strip() == contract_name).first.click()

            if course_name and NO_SELECTED != contract_name:
                # wait course enabled
                self.wait_for(
                    lambda: bool(self.q(css='#role-selection-modal #course-id').filter(lambda el: el.is_enabled()).results),
                    'Selectbox of course is enabled.'
                )

        # select course
        if course_name:
            if not any(course_name in c for c in self._course_names):
                raise ValueError('Not found course:{} not in {}'.format(course_name, self._course_names))
            self.q(css='#role-selection-modal #course-id>option').filter(lambda el: course_name in el.text.strip()).first.click()

        if cancel:
            self.q(css='.w2ui-msg-buttons>.biz-modal-close').first.click()
        else:
            self.q(css='.w2ui-msg-buttons>#save-selection').first.click()

        if close:
            self.wait_for_element_invisibility('section#role-selection-modal', 'Role selection modal is invisible')
        return self

    @property
    def _org_names(self):
        return self.q(css='#role-selection-modal #org-id>option').text

    @property
    def _contract_names(self):
        return self.q(css='#role-selection-modal #contract-id>option').text

    @property
    def _course_names(self):
        return self.q(css='#role-selection-modal #course-id>option').text

    @property
    def is_not_selected(self):
        message = self.q(css='div.course-selection>div.current-role>div.message>p').text
        return message and message[0] == u'Course not specified'

    @property
    def contract_name(self):
        return self.q(css='div.course-selection>div.current-role>div:nth-of-type(1)>div').text[0].strip()

    @property
    def course_name(self):
        return self.q(css='div.course-selection>div.current-role>div:nth-of-type(2)>div').text[0].strip()

    @property
    def left_menu_items(self):
        menu_item = self.q(css='nav.side-menu>ul.menu>li>a')
        return {t: h for t, h in zip(menu_item.text, menu_item.attrs('href'))}

    def click_organization(self):
        # Import in func for cross reference
        from .ga_organization import BizOrganizationPage

        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/organization/"]').first.click()
        return BizOrganizationPage(self.browser).wait_for_page()

    def click_contract(self):
        # Import in func for cross reference
        from .ga_contract import BizContractPage

        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/contract/"]').first.click()
        return BizContractPage(self.browser).wait_for_page()

    def click_manager(self):
        # Import in func for cross reference
        from .ga_manager import BizManagerPage

        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/manager/"]').first.click()
        manager_page = BizManagerPage(self.browser).wait_for_page()
        manager_page.wait_for_ajax()
        return manager_page.wait_for_lock_absence()

    def click_survey(self):
        # Import in func for cross reference
        from .ga_survey import BizSurveyPage

        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/course_operation/survey"]').first.click()
        return BizSurveyPage(self.browser).wait_for_page()

    def click_register_students(self):
        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/contract_operation/register_students"]').first.click()
        from common.test.acceptance.pages.biz.ga_contract_operation import BizRegisterStudentsPage
        return BizRegisterStudentsPage(self.browser).wait_for_page()

    def click_score(self):
        # Import in func for cross reference
        from .ga_achievement import BizAchievementPage

        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/achievement/"]').first.click()
        return BizAchievementPage(self.browser).wait_for_page()

    def click_register_management(self):
        # Import in func for cross reference
        from .ga_contract_operation import BizStudentsPage

        self.q(css='nav.side-menu>ul.menu>li>a[href="/biz/contract_operation/students"]').first.click()
        return BizStudentsPage(self.browser).wait_for_page()

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

    def wait_for_contract_not_specified(self):
        self.wait_for(
            lambda: self.pagetitle == u'Contract Not Specified',
            'ContractNotSpecifiedPage is visible.'
        )
        return self

    def wait_for_course_not_specified(self):
        self.wait_for(
            lambda: self.pagetitle == u'Course Not Specified',
            'CourseNotSpecifiedPage is visible.'
        )
        return self

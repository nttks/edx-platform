# -*- coding: utf-8 -*-
"""
Manager page of biz.
"""

from . import BASE_URL
from .ga_navigation import BizNavPage
from .ga_w2ui import W2uiMixin


class BizManagerPage(BizNavPage, W2uiMixin):

    url = "{base}/biz/manager/".format(base=BASE_URL)

    def is_browser_on_page(self):
        return self.pagetitle == u'Manager Setting'

    @property
    def organizations(self):
        organizations = {}
        for el in self.q(css='select#organization>option').results:
            organizations[el.get_attribute('value')] = el.text.strip()
        return organizations

    @property
    def permissions(self):
        permissions = {}
        for el in self.q(css='select#permission>option').results:
            permissions[el.get_attribute('value')] = el.text.strip()
        return permissions

    @property
    def names(self):
        return [el.text.strip() for el in self.q(css='td#name').filter(lambda el: el.is_displayed())]

    @property
    def emails(self):
        return [el.text.strip() for el in self.q(css='td#email').filter(lambda el: el.is_displayed())]

    def select(self, organization_name, permission):
        # select organization
        self.q(css='select#organization>option').filter(lambda el: organization_name == el.text.strip()).first.click()
        self.wait_for_ajax()
        self.wait_for_lock_absence()
        # select permission
        self.q(css='select#permission>option[value="{}"]'.format(permission)).first.click()
        self.wait_for_ajax()
        return self.wait_for_lock_absence()

    def input_user(self, name_or_email=''):
        self.q(css='input#add-user').fill(name_or_email)
        return self

    def click_grant(self):
        self.q(css='input#edit-btn').first.click()
        self.wait_for_ajax()
        return self.wait_for_lock_absence()

    def click_revoke(self, name_or_email):
        try:
            index = self.names.index(name_or_email)
        except ValueError:
            index = self.emails.index(name_or_email)

        self.q(css='tr#member-detail>td>a').nth(index).click()
        self.wait_for_ajax()
        return self.wait_for_lock_absence()

    def refresh_page(self):
        self.browser.refresh()
        self.wait_for_page()
        self.wait_for_ajax()
        return self.wait_for_lock_absence()

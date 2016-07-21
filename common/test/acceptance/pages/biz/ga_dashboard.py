"""
Student dashboard page of biz.
"""

from ..lms.ga_dashboard import DashboardPage as GaDashboardPage
from . import BASE_URL
from .ga_navigation import BizNavPage


class DashboardPage(GaDashboardPage):
    """
    Student dashboard, where the student can view
    courses she/he has registered for.
    """
    def is_browser_on_page(self):
        return super(DashboardPage, self).is_browser_on_page() and self.q(css='ul.dropdown-menu>li>a[href="/biz/"]').present

    def click_biz(self):
        self.q(css='button.dropdown').first.click()
        self.wait_for_element_visibility('ul.dropdown-menu', 'Drop down menu is visible')
        self.q(css='ul.dropdown-menu>li>a[href="/biz/"]').first.click()
        return BizNavPage(self.browser).wait_for_page()

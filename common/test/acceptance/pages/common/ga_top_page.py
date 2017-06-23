"""
TOP Page.
"""
from bok_choy.page_object import PageObject
from . import BASE_URL


class TopPage(PageObject):
    """
    top page
    """

    url = BASE_URL

    def is_browser_on_page(self):
        return self.q(css='.wrap-top-page').present

    def click_top_page(self):
        self.q(css='a.top-page').first.click()

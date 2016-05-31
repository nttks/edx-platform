"""
Pages for biz invitation
"""
from bok_choy.page_object import PageObject


class BizSurveyPage(PageObject):
    """
    Survey page
    """

    url = None

    def is_browser_on_page(self):
        """
        Check if browser is showing correct page.
        """
        return 'Survey Download' in self.browser.title

    def click_download_button(self):
        """
        Click the download button
        """
        self.q(css='input#download-btn').first.click()
        return self.wait_for_page()

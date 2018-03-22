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

    def check_encoding_utf8(self, checked):
        checkbox = self.q(css='input#encoding-utf8')
        if checkbox.selected != checked:
            checkbox.click()
            self.wait_for(lambda: checked == checkbox.selected, 'Checkbox is not clicked')
        return self

    def is_encoding_utf8_selected(self):
        return self.q(css='input#encoding-utf8').selected

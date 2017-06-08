"""Login and Registration pages (2)"""

from bok_choy.page_object import unguarded
from .login_and_register import CombinedLoginAndRegisterPage as EdXCombinedLoginAndRegisterPage


class CombinedLoginAndRegisterPage(EdXCombinedLoginAndRegisterPage):
    """
    Interact with combined login and registration page.
    """

    def __init__(self, browser, start_page="register", course_id=None):
        """
        Initialize the page.
        """
        super(CombinedLoginAndRegisterPage, self).__init__(browser, start_page, course_id)

    @unguarded
    def register_complete_message(self):
        """Get the message displayed to the user on the login form"""
        if self.q(css=".activate-account-notice h4").visible:
            return self.q(css=".activate-account-notice h4").text[0]

"""Login page for the LMS"""

from .login import LoginPage as EdXLoginPage


class LoginPage(EdXLoginPage):
    """
    Login page for the LMS.
    """

    def is_browser_on_page(self):
        return any([
            'welcome' in title.lower()
            for title in self.q(css='span.title-super').text
        ])

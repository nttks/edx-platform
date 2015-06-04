"""Login page for the LMS"""

from .ga_dashboard import DashboardPage
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

    def submit(self):
        """
        Submit registration info to create an account.
        """
        self.q(css='button#submit').first.click()

        # The next page is the dashboard; make sure it loads
        dashboard = DashboardPage(self.browser)
        dashboard.wait_for_page()
        return dashboard

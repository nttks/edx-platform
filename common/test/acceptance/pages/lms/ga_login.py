"""Login page for the LMS"""

from bok_choy.promise import Promise

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

    def login(self, email, password, next_page=True):
        """
        Attempt to log in using `email` and `password`.
        """
        self.provide_info(email, password)
        return self.submit(next_page)

    def submit(self, next_page=True):
        """
        Submit registration info to create an account.
        """
        self.q(css='button#submit').first.click()

        if next_page:
            # The next page is the dashboard; make sure it loads
            dashboard = DashboardPage(self.browser)
            dashboard.wait_for_page()
            return dashboard
        else:
            return None

    @property
    def errors(self):
        """Return a list of errors displayed to the user. """
        return self.q(css=".submission-error .message-copy").text

    def wait_for_errors(self):
        """Wait for errors to be visible, then return them. """
        def _check_func():
            """Return success status and any errors that occurred."""
            errors = self.errors
            return (bool(errors), errors)
        return Promise(_check_func, "Errors are visible").fulfill()

"""
Pages for password reset
"""
import re

from bok_choy.page_object import PageObject
from bok_choy.promise import Promise
from lms.envs.bok_choy import PLATFORM_NAME
from . import BASE_URL


class PasswordResetConfirmPage(PageObject):
    """
    Password reset confirm page
    """

    def __init__(self, browser, uidb36, token):
        super(PasswordResetConfirmPage, self).__init__(browser)
        self.uidb36 = uidb36
        self.token = token

    @property
    def url(self):
        return '{base}/password_reset_confirm/{uidb36}-{token}/'.format(
            base=BASE_URL,
            uidb36=self.uidb36,
            token=self.token
        )

    def is_browser_on_page(self):
        title = self.browser.title
        matches = re.match(u"^Reset Your {platform_name} Password$".format(platform_name=PLATFORM_NAME), title)
        return matches is not None

    def fill_password(self, password1, password2):
        """
        Fill in the new passwords
        """
        self.q(css='input#new_password1').fill(password1)
        self.q(css='input#new_password2').fill(password2)

    def submit(self):
        """
        Click the submit button
        """
        self.q(css='button#submit').click()

    @property
    def errors(self):
        """Return a list of errors displayed to the user. """
        return self.q(css=".submission-error li").text

    def wait_for_errors(self):
        """Wait for errors to be visible, then return them. """
        def _check_func():
            """Return success status and any errors that occurred."""
            errors = self.errors
            return (bool(errors), errors)
        return Promise(_check_func, "Errors are visible").fulfill()


class PasswordResetCompletePage(PageObject):
    """
    Password reset complete page
    """

    url = None

    def is_browser_on_page(self):
        title = self.browser.title
        matches = re.match(u"^Your Password Reset is Complete$", title)
        return matches is not None

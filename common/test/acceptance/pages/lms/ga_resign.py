"""
Pages for resign
"""
import re

from bok_choy.page_object import PageObject
from bok_choy.promise import Promise
from lms.envs.bok_choy import PLATFORM_NAME
from . import BASE_URL


class ResignConfirmPage(PageObject):
    """
    Resign confirm page
    """

    def __init__(self, browser, uidb36, token):
        super(ResignConfirmPage, self).__init__(browser)
        self.uidb36 = uidb36
        self.token = token

    @property
    def url(self):
        return '{base}/resign_confirm/{uidb36}-{token}/'.format(
            base=BASE_URL,
            uidb36=self.uidb36,
            token=self.token
        )

    def is_browser_on_page(self):
        title = self.browser.title
        matches = re.match(u"^Resignation from {platform_name}$".format(platform_name=PLATFORM_NAME), title)
        return matches is not None

    def fill_resign_reason(self, text):
        """
        Fill in the resign reason
        """
        self.q(css='textarea#id_resign_reason').fill(text)

    def submit(self):
        """
        Click the submit button
        """
        self.q(css='button#submit').click()

    def cancel(self):
        """
        Click the cancel button
        """
        self.q(css='a.action-cancel').click()

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


class ResignCompletePage(PageObject):
    """
    Resign complete page
    """

    url = None

    def is_browser_on_page(self):
        title = self.browser.title
        matches = re.match(u"^Resignation from {platform_name} is Complete$".format(platform_name=PLATFORM_NAME), title)
        return matches is not None


class DisabledAccountPage(PageObject):
    """
    Disabled account page
    """

    url = None

    def is_browser_on_page(self):
        title = self.browser.title
        matches = re.match(u"^Disabled Account | {platform_name}$".format(platform_name=PLATFORM_NAME), title)
        return matches is not None

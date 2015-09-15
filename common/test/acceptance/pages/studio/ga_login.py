"""
Login page for Studio.
"""

from .login import LoginPage as EdXLoginPage


class LoginPage(EdXLoginPage):
    """
    Login page for Studio.
    """

    def __init__(self, browser):
        """
        Initialize the page.
        """
        super(LoginPage, self).__init__(browser)

    def has_maintenance_message(self):
        """
        (bool) is the "Message for maintenance"?
        """
        return self.q(css='li.maintenance-item').is_present()

    def get_maintenance_message_title(self):
        """
        (str) element of message title
        """
        return self.q(css='li.maintenance-item > h3').text

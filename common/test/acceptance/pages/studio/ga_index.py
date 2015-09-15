"""
Studio Home page
"""

from .index import DashboardPage as EdXDashboardPage


class DashboardPage(EdXDashboardPage):
    """
    Studio Home page
    """

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

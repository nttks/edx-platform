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

    @property
    def course_creation_error(self):
        """
        Returns course creation error element.
        """
        return self.q(css='.wrapper-create-course .wrap-error.is-shown #course_creation_error.message')

    @property
    def course_creation_error_message(self):
        """
        Returns text of course creation error message.
        """
        self.wait_for_element_presence(
            ".wrapper-create-course .wrap-error.is-shown #course_creation_error.message", "Course creation error message is present"
        )
        return self.course_creation_error.results[0].find_element_by_css_selector('p').text

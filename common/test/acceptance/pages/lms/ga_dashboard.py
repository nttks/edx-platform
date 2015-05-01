"""
Student dashboard page.
"""

from selenium.common.exceptions import NoSuchElementException

from .dashboard import DashboardPage as EdXDashboardPage

class DashboardPage(EdXDashboardPage):
    """
    Student dashboard, where the student can view
    courses she/he has registered for.
    """
    def __init__(self, browser):
        """
        Initialize the page.
        """
        super(DashboardPage, self).__init__(browser)

    @property
    def activation_message(self):
        """
        Return the message about activation.
        """
        return self.q(css='section.dashboard-banner .activation-message').text

    def click_resign(self):
        """
        Click resign on dashboard
        """
        self.q(css="#resign_button").first.click()

    def click_reset_password(self):
        """
        Click reset password on dashboard
        """
        self.q(css="#pwd_reset_button").first.click()

    def is_exists_notification(self):
        """
        Return whether notification is displayed.
        """
        return len(self.q(css='section.dashboard-notifications section')) > 0

    def is_enable_unenroll(self, course_name):
        """Return whether unenroll link is displayed

        Arguments:
            course_name (str): The name of the course whose student could be cancelled.

        Returns:
            Boolean, whether students undoable.

        Raises:
            Exception, if no course with the provided name is found on the dashboard.
        """
        # Filter elements by course name, only returning the relevant course item
        course_listing = self.q(css=".course").filter(lambda el: course_name in el.text).results

        if course_listing:
            # There should only be one course listing corresponding to the provided course name.
            el = course_listing[0]
            try:
                el.find_element_by_css_selector(".unenroll")
                return True
            except NoSuchElementException:
                return False
        else:
            raise Exception("No course named {} was found on the dashboard".format(course_name))

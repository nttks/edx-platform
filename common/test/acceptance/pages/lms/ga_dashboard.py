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

    def _get_element_in_course(self, course_name, selector):
        """
        Return the element in the course.
        """
        # Filter elements by course name, only returning the relevant course item
        course_listing = self.q(css=".course").filter(lambda el: course_name in el.text).results

        if course_listing:
            # There should only be one course listing corresponding to the provided course name.
            el = course_listing[0]
            return el.find_element_by_css_selector(selector)
        else:
            raise Exception("No course named {} was found on the dashboard".format(course_name))

    @property
    def activation_message(self):
        """
        Return the message about activation.
        """
        return self.q(css='section.dashboard-banner .activation-message').text

    def change_email_settings(self, course_name):
        """
        Change email settings on dashboard
        """
        self._get_element_in_course(course_name, ".action-more").click()
        self._get_element_in_course(course_name, ".action-email-settings").click()
        self.q(css="#receive_emails").first.click()
        # there are multiple elements of id 'submit'
        self.q(css="#email_settings_form #submit").first.click()

    def is_exists_notification(self):
        """
        Return whether notification is displayed.
        """
        return len(self.q(css='section.dashboard-notifications section')) > 0

    def is_enable_unenroll(self, course_name):
        """
        Return whether unenroll link is displayed
        """
        try:
            self._get_element_in_course(course_name, ".unenroll")
            return True
        except NoSuchElementException:
            return False

    @property
    def hidden_course_text(self):
        text_items = self.q(css='section #block-course-msg').text
        if len(text_items) > 0:
            return text_items[0]
        else:
            return ""

    def is_hidden_course_link_active(self, course_id):
        link_css = self._link_css(course_id)
        return True if link_css is not None else False

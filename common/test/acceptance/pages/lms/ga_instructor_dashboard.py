"""
Instructor (2) dashboard page.
"""

from bok_choy.page_object import PageObject
from .instructor_dashboard import InstructorDashboardPage as EdXInstructorDashboardPage


class InstructorDashboardPage(EdXInstructorDashboardPage):
    """
    Instructor dashboard, where course staff can manage a course.
    """

    def select_send_email(self):
        """
        Selects the email tab and returns the EmailSection
        """
        self.q(css='a[data-section=send_email]').first.click()
        send_email_section = SendEmailPage(self.browser)
        send_email_section.wait_for_page()
        return send_email_section


class SendEmailPage(PageObject):
    """
    Email section of the Instructor dashboard.
    """
    url = None

    def is_browser_on_page(self):
        return self.q(css='a[data-section=send_email].active-section').present

    def is_visible_optout_container(self):
        """
        Return whether optout container is rendered.
        """
        return self.q(css='.optout-container').visible

    def select_send_to(self, send_to):
        self.q(css="#id_to option").filter(lambda el: el.get_attribute('value') == send_to).first.click()

    def set_title(self, title):
        self.q(css="input#id_subject").fill(title)

    def set_message(self, message):
        self.browser.execute_script("tinyMCE.activeEditor.setContent('{}')".format(message))

    def check_include_optout(self):
        self.q(css="#section-send-email input[name='include-optout']").click()

    def send(self):
        self.q(css="input[name='send']").click()

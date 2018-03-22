"""
Instructor (2) dashboard page.
"""

from bok_choy.page_object import PageObject
from .instructor_dashboard import InstructorDashboardPage as EdXInstructorDashboardPage, \
    MembershipPage as EdXMembershipPage


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

    def select_survey(self):
        """
        Selects the survey tab and returns the SurveySection
        """
        self.q(css='a[data-section=survey]').first.click()
        survey_section = SurveyPageSection(self.browser)
        survey_section.wait_for_page()
        return survey_section


class SurveyPageSection(PageObject):
    """
    Survey section of the Instructor dashboard.
    """
    url = None

    def is_browser_on_page(self):
        return self.q(css='a[data-section=survey].active-section').present

    def click_download_button(self):
        """
        Click the download csv button
        """
        self.q(css="input[name='list-survey']").click()
        self.wait_for_ajax()
        return self

    def check_encoding_utf8(self, checked):
        checkbox = self.q(css='input#encoding-utf8')
        if checkbox.selected != checked:
            checkbox.click()
            self.wait_for(lambda: checked == checkbox.selected, 'Checkbox is not clicked')
        return self

    def is_encoding_utf8_selected(self):
        return self.q(css='input#encoding-utf8').selected


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

    def is_visible_advanced_course(self):
        return self.q(css="select[name='advanced_course']").visible

    def select_advanced_course(self, advanced_course_name):
        self.q(css="select[name='advanced_course'] option").filter(lambda el: el.text == advanced_course_name).first.click()

class MembershipPageMemberListSection(EdXMembershipPage):
    """
    Member list management section of the Membership tab of the Instructor dashboard.
    """
    url = None

    def select_role(self, role_name):
        for option in self.q(css='#member-lists-selector option').results:
            if role_name == option.text:
                option.click()

    def add_role(self, role_name, member):
        self.select_role(role_name)
        self.q(css='div[data-rolename="{}"] input.add-field'.format(role_name)).fill(member)
        self.q(css='div[data-rolename="{}"] input.add'.format(role_name)).click()
        self.wait_for_ajax()

    def add_role_by_display_name(self, role_name, member):
        self.select_role(role_name)
        self.q(css='div[data-display-name="{}"] input.add-field'.format(role_name)).fill(member)
        self.q(css='div[data-display-name="{}"] input.add'.format(role_name)).click()
        self.wait_for_ajax()

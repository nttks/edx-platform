"""
Contract operation pages of biz.
"""
import re

from selenium.webdriver.support.ui import Select

from . import BASE_URL
from .ga_navigation import BizNavPage
from .ga_w2ui import W2uiMixin, W2uiGrid, KEY_GRID_INDEX


class BizTaskHistoryMixin(object):

    def __init__(self, *args, **kwargs):
        super(BizTaskHistoryMixin, self).__init__()
        self.task_history_grid = W2uiGrid(self, '#task-history-grid.w2ui-grid')

    def click_show_history(self):
        self.q(css='#task-history-btn').click()
        self.wait_for_ajax()
        self.wait_for_element_visibility('#task-history-grid.w2ui-grid', 'Task history grid visible')
        return self

    def click_task_reload_button(self):
        self.q(css='button#task-reload-btn').click()
        self.wait_for_ajax()
        return self

    @property
    def task_history_grid_row(self):
        return self.get_task_history_grid_row(0)

    def get_task_history_grid_row(self, index):
        return self.task_history_grid.get_row({
            KEY_GRID_INDEX: index
        })

    @property
    def task_messages(self):
        return self.get_task_messages(0)

    def get_task_messages(self, index):
        with self.task_history_grid.click_expand(index=index) as expanded_grid:
            return expanded_grid.grid_rows

    def wait_for_task_complete(self):
        def _wait_for():
            self.click_task_reload_button()
            return self.task_history_grid_row['State'] == 'Complete'
        self.wait_for(_wait_for, 'Latest task state is not Complete')


class BizStudentsPage(BizNavPage, BizTaskHistoryMixin, W2uiMixin):
    """
    Students page for unregister and mask
    """

    url = "{base}/biz/contract_operation/students".format(base=BASE_URL)

    def __init__(self, browser):
        super(BizStudentsPage, self).__init__(browser)
        self.student_grid = W2uiGrid(self, '#grid.w2ui-grid')

    def is_browser_on_page(self):
        return self.pagetitle == u'Users List'

    def click_unregister_button(self):
        """
        Click the unregister button
        """
        self.q(css='#unregister-btn').click()
        self.wait_for_ajax()
        return self

    def click_personalinfo_mask_button(self):
        """
        Click the personalinfo mask button
        """
        self.q(css='#personalinfo-mask-btn').click()
        self.wait_for_ajax()
        return self

    @property
    def messages(self):
        """Return a list of errors displayed to the list view. """
        return self.q(css="div.main ul.messages li").text


class BizRegisterStudentsPage(BizNavPage, BizTaskHistoryMixin, W2uiMixin):
    """
    Register students page
    """

    @property
    def url(self):
        return '{base}/biz/contract_operation/register_students'.format(base=BASE_URL)

    def is_browser_on_page(self):
        """
        Check if browser is showing the page.
        """
        return 'Enrolling New Learners' in self.browser.title

    def input_students(self, value):
        """
        Input students info

        Arguments:
            value : target students
        """
        self.q(css='.w2ui-page.page-0 textarea#list-students').fill(value)
        return self

    def input_one_user_info(self, user_info):
        """
        Input student info

        Arguments:
            user_info : target student info
        """
        self.q(css='input#employee_last_name').fill(user_info['last_name'] if 'last_name' in user_info else user_info['username'])
        self.q(css='input#employee_email').fill(user_info['email'])
        self.q(css='input#user_name').fill(user_info['username'])
        self.wait_for_ajax()
        return self

    def input_one_user_info_auth(self, user_info):
        """
        Input student info with contract auth

        Arguments:
            user_info : target student info
        """
        self.q(css='input#employee_last_name').fill(user_info['last_name'] if 'last_name' in user_info else user_info['username'])
        self.q(css='input#employee_email').fill(user_info['email'])
        self.q(css='input#user_name').fill(user_info['username'])
        self.q(css='input#login_code').fill(user_info['login_code'] if 'login_code' in user_info else user_info['username'])
        self.q(css='input#password').fill(user_info['password'])
        self.wait_for_ajax()
        return self

    def click_register_status(self):
        """
        Click the register status checkbox
        """
        self.q(css='.w2ui-page.page-0 #register-status').click()
        return self

    def click_one_register_status(self):
        """
        Click the register status checkbox in One Registration Page
        """
        self.q(css='input#register-status-new.gc_optional_chk.js_register_status_popup').click()
        return self

    def click_register_button(self):
        """
        Click the register button
        """
        self.q(css='.w2ui-page.page-0 #register-btn').click()
        self.wait_for_ajax()
        return self

    def click_one_register_button(self):
        """
        Click the register button in One Registration Page
        """
        self.q(css='button#register-btn-new.btn.btn-grn').click()
        self.wait_for_ajax()
        return self

    @property
    def messages(self):
        """Return a list of errors displayed to the list view. """
        return self.q(css="div.main ul.messages li.info").text

    @property
    def error_messages(self):
        """
        Return error messages
        """
        return self.q(css="div#error_area.gc_error_area ul.messages li.error").text

    def click_tab_file_register_student(self):
        self.q(css='li#tab01').click()
        self.wait_for_ajax()
        return self

    def click_tab_one_register_student(self):
        self.q(css='li#tab02').click()
        self.wait_for_ajax()
        return self

    def click_tab_search_registration(self):
        self.q(css='li#tab03').click()
        self.wait_for_ajax()
        return self

    def click_tab_additional_info(self):
        self.q(css='li#tab04').click()
        self.wait_for_ajax()
        return self

    def click_tab_update_additional_info(self):
        self.q(css='li#tab05').click()
        self.wait_for_ajax()
        return self

    def click_additional_info_register_button(self):
        self.q(css='button.biz-btn.register-btn.add-additional-info-btn').click()
        self.wait_for_ajax()
        return self

    def click_additional_info_delete_button(self, index=0):
        self.q(css='button.biz-btn.remove-btn.small-btn').click()
        self.wait_for_ajax()
        return self

    def click_additional_info_update_button(self):
        self.q(css='input#update-btn.biz-btn.register-btn.update-btn').click()
        self.wait_for_ajax()
        return self

    def edit_additional_info_value(self, value, index=0):
        self.q(css='.w2ui-field [name="display_name"]').nth(index).fill(value)
        # focus out.
        self.q(css='.w2ui-field [name="register_display_name"]').click()
        self.wait_for_ajax()
        return self

    def input_additional_info_register(self, value):
        self.q(css='.w2ui-field [name="register_display_name"]').fill(value)
        return self

    def input_additional_info_list(self, value):
        self.q(css='textarea#additional-info-list.additional-info-list').fill(value)
        return self

    def get_display_name_values(self, index=0):
        return self.q(css='[name="display_name"]').nth(index).attrs('value')

    def get_additional_infos(self):
        return self.q(css='.operation.setting-list').text


class BizMailPage(BizNavPage, W2uiMixin):
    """
    Mail page
    """

    @property
    def url(self):
        return '{base}/biz/contract_operation/mail'.format(base=BASE_URL)

    def is_browser_on_page(self):
        return self.pagetitle == u'Welcome E-Mail Management'

    @property
    def parameter_keys(self):
        r = re.compile(u'^\{(\w+)\}')
        return [m.group(1) for m in [r.search(el.text) for el in self.q(css='.w2ui-page .operation').results if el.is_displayed()] if m]

    @property
    def subject(self):
        for el in self.q(css='.w2ui-page input[name="mail_subject"]').results:
            if el.is_displayed():
                return el.get_attribute('value')
        return None

    @property
    def body(self):
        for el in self.q(css='.w2ui-page textarea[name="mail_body"]').results:
            if el.is_displayed():
                return el.text
        return None

    def click_tab_for_new_user(self):
        self.click_tab('For New User')
        return self

    def click_tab_for_existing_user(self):
        self.click_tab('For Existing User')
        return self

    def click_tab_for_new_user_login_code(self):
        self.click_tab('For New User with Login Code')
        return self

    def click_tab_for_existing_user_login_code(self):
        self.click_tab('For Existing User with Login Code')
        return self

    def input(self, subject, body):
        for el in self.q(css='.w2ui-page input[name="mail_subject"]').results:
            if el.is_displayed():
                el.clear()
                el.send_keys(subject)
        for el in self.q(css='.w2ui-page textarea[name="mail_body"]').results:
            if el.is_displayed():
                el.clear()
                el.send_keys(body)
        return self

    def click_save_template(self):
        for el in self.q(css='.w2ui-page .register-btn').results:
            if el.is_displayed():
                el.click()
        self.wait_for_ajax()
        return self

    def click_send_test_mail(self):
        for el in self.q(css='.w2ui-page .test-send-btn').results:
            if el.is_displayed():
                el.click()
        self.wait_for_ajax()
        return self


class BizReminderMailPage(BizNavPage, W2uiMixin):
    """
    Reminder mail page
    """

    @property
    def url(self):
        return '{base}/biz/contract_operation/reminder_mail'.format(base=BASE_URL)

    def is_browser_on_page(self):
        return self.pagetitle == u'Reminder Mail Setting'

    @property
    def parameter_keys(self):
        r = re.compile(u'^\{(\w+)\}')
        return [m.group(1) for m in [r.search(el.text) for el in self.q(css='.w2ui-page .operation').results if el.is_displayed()] if m]

    @property
    def reminder_email_days(self):
        for el in self.q(css='.w2ui-page select[name="reminder_email_days"]').results:
            if el.is_displayed():
                return Select(el).first_selected_option.text
        return None

    @property
    def subject(self):
        for el in self.q(css='.w2ui-page input[name="mail_subject"]').results:
            if el.is_displayed():
                return el.get_attribute('value')
        return None

    @property
    def body(self):
        for el in self.q(css='.w2ui-page textarea[name="mail_body"]').results:
            if el.is_displayed():
                return el.text
        return None

    @property
    def body2(self):
        for el in self.q(css='.w2ui-page textarea[name="mail_body2"]').results:
            if el.is_displayed():
                return el.text
        return None

    def click_tab_for_submission_reminder_mail(self):
        self.click_tab('Submission Reminder Mail')
        return self

    def input(self, reminder_email_days, subject, body, body2):
        for el in self.q(css='.w2ui-page select[name="reminder_email_days"]').results:
            if el.is_displayed():
                Select(el).select_by_value(reminder_email_days)
        for el in self.q(css='.w2ui-page input[name="mail_subject"]').results:
            if el.is_displayed():
                el.clear()
                el.send_keys(subject)
        for el in self.q(css='.w2ui-page textarea[name="mail_body"]').results:
            if el.is_displayed():
                el.clear()
                el.send_keys(body)
        for el in self.q(css='.w2ui-page textarea[name="mail_body2"]').results:
            if el.is_displayed():
                el.clear()
                el.send_keys(body2)
        return self

    def click_save_template(self):
        for el in self.q(css='.w2ui-buttons .save-btn').results:
            if el.is_displayed():
                el.click()
        self.wait_for_ajax()
        return self

    def click_send_test_mail(self):
        for el in self.q(css='.w2ui-buttons .send-btn').results:
            if el.is_displayed():
                el.click()
        self.wait_for_ajax()
        return self


class BizBulkStudentsPage(BizNavPage, BizTaskHistoryMixin, W2uiMixin):
    """
    Bulk operation page
    """

    @property
    def url(self):
        return '{base}/biz/contract_operation/bulk_students'.format(base=BASE_URL)

    def is_browser_on_page(self):
        """
        Check if browser is showing the page.
        """
        return 'Unregister, Mask' in self.browser.title

    def input_students(self, value):
        """
        Input students info

        Arguments:
            value : target students
        """
        self.q(css='textarea#list-students').fill(value)
        return self

    def click_bulk_unregister_button(self):
        """
        Click the bulk-unregister button
        """
        self.q(css='#bulk-unregister-btn').click()
        self.wait_for_ajax()
        return self

    def click_bulk_personalinfo_mask_button(self):
        """
        Click the bulk-personalinfo-mask button
        """
        self.q(css='#bulk-personalinfo-mask-btn').click()
        self.wait_for_ajax()
        return self

    @property
    def messages(self):
        """Return a list of errors displayed to the list view. """
        return self.q(css="div.main ul.messages li").text

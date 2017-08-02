# -*- coding: utf-8 -*-
"""
ga_operation page.
"""
from bok_choy.javascript import wait_for_js
from bok_choy.page_object import PageObject
from . import BASE_URL


class GaOperationPage(PageObject):

    url = BASE_URL + '/ga_operation'

    @wait_for_js
    def is_browser_on_page(self):
        return self.q(css='a[href="#upload_certs_template"]').present

    # get link text
    def get_upload_certs_template_text(self):
        return self.q(css='a[href="#upload_certs_template"]').text

    def get_create_certs_text(self):
        return self.q(css='a[href="#create_certs"]').text

    def get_create_certs_meeting_text(self):
        return self.q(css='a[href="#create_certs_meeting"]').text

    def get_publish_certs_text(self):
        return self.q(css='a[href="#publish_certs"]').text

    # get content text
    def get_confirm_certs_template_error_course_id_text(self):
        return self.q(css='#course_id').text

    def get_cert_pdf_tmpl_error_text(self):
        return self.q(css='li#cert_pdf_tmpl_error').text

    def get_create_certs_error_course_id_text(self):
        return self.q(css='#course_id').text

    def get_create_certs_error_email_text(self):
        return self.q(css='#email').text

    def get_create_certs_meeting_error_course_id_text(self):
        return self.q(css='#course_id').text

    def get_create_certs_meeting_error_student_ids_text(self):
        return self.q(css='#student_ids').text

    def get_create_certs_meeting_error_email_text(self):
        return self.q(css='#email').text

    def get_publish_certs_error_course_id_text(self):
        return self.q(css='#course_id').text

    # click link
    def click_upload_certs_template_link(self):
        return self.q(css='a[href="#upload_certs_template"]').first.click()

    def click_create_certs_link(self):
        return self.q(css='a[href="#create_certs"]').first.click()

    def click_create_certs_meeting_link(self):
        return self.q(css='a[href="#create_certs_meeting"]').first.click()

    def click_publish_certs_link(self):
        return self.q(css='a[href="#publish_certs"]').first.click()

    # click button
    def click_template_check_button(self):
        return self.q(css='#confirm_certs_template').first.click()

    def click_template_upload_button(self):
        return self.q(css='#upload_certs_template').first.click()

    def click_create_certs_button(self):
        return self.q(css='#create_certs').first.click()

    def click_create_certs_meeting_button(self):
        return self.q(css='#create_certs_meeting').first.click()

    def click_publish_certs_button(self):
        return self.q(css='#publish_certs').first.click()

    # set textbox
    def set_create_certs_textbox(self):
        self.q(css='input[name="course_id"]').fill('')
        self.q(css='input[name="email"]').fill('')
        return self

    def set_create_certs_meeting_textbox(self):
        self.q(css='input[name="course_id"]').fill('')
        self.q(css='input[name="email"]').fill('')
        return self

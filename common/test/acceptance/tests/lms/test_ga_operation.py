# -*- coding: utf-8 -*-
"""
Tests the ga_operation page
"""
import bok_choy.browser

from ..helpers import UniqueCourseTest
from ..ga_helpers import GaccoTestMixin, SUPER_USER_INFO

from ...pages.lms.ga_operation import GaOperationPage


class GaOperationTest(UniqueCourseTest, GaccoTestMixin):

    def setUp(self):
        super(GaOperationTest, self).setUp()

        self.switch_to_user(SUPER_USER_INFO)

        self.ga_operation_page = GaOperationPage(self.browser)
        self.ga_operation_page.visit()

    def test_show_ga_operation_page(self):
        self.assertEqual([u'テンプレートアップロード'], self.ga_operation_page.get_upload_certs_template_text())
        self.assertEqual([u'修了証発行(通常)'], self.ga_operation_page.get_create_certs_text())
        self.assertEqual([u'修了証発行(対面学習)'], self.ga_operation_page.get_create_certs_meeting_text())
        self.assertEqual([u'修了証公開'], self.ga_operation_page.get_publish_certs_text())

    def test_click_check_templete_with_not_input(self):
        self.ga_operation_page.click_upload_certs_template_link()

        self.ga_operation_page.click_template_check_button()
        self.ga_operation_page.wait_for_ajax()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_check_templete')

        self.assertEqual([u'このフィールドは必須です。'],
                         self.ga_operation_page.get_confirm_certs_template_error_course_id_text())

    def test_click_upload_templete_with_not_input(self):
        self.ga_operation_page.click_upload_certs_template_link()

        self.ga_operation_page.click_template_upload_button()
        self.ga_operation_page.wait_for_ajax()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_upload_templete')

        self.assertEqual([u'通常テンプレートと対面学習テンプレートのどちらか一方または両方を選択してください。'],
                         self.ga_operation_page.get_cert_pdf_tmpl_error_text())

    def test_click_create_certs_with_not_input(self):
        self.ga_operation_page.click_create_certs_link()

        self.ga_operation_page.set_create_certs_textbox()
        self.ga_operation_page.click_create_certs_button()
        self.ga_operation_page.wait_for_ajax()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_create_certs')

        self.assertEqual([u'このフィールドは必須です。'],
                         self.ga_operation_page.get_create_certs_error_course_id_text())
        self.assertEqual([u'このフィールドは必須です。'],
                         self.ga_operation_page.get_create_certs_error_email_text())

    def test_click_create_certs_meeting_with_not_input(self):
        self.ga_operation_page.click_create_certs_meeting_link()

        self.ga_operation_page.set_create_certs_meeting_textbox()
        self.ga_operation_page.click_create_certs_meeting_button()
        self.ga_operation_page.wait_for_ajax()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_create_certs_meeting')

        self.assertEqual([u'このフィールドは必須です。'],
                         self.ga_operation_page.get_create_certs_meeting_error_course_id_text())
        self.assertEqual([u'このフィールドは必須です。'],
                         self.ga_operation_page.get_create_certs_meeting_error_student_ids_text())
        self.assertEqual([u'このフィールドは必須です。'],
                         self.ga_operation_page.get_create_certs_meeting_error_email_text())

    def test_click_publish_certs_with_not_input(self):
        self.ga_operation_page.click_publish_certs_link()

        self.ga_operation_page.click_publish_certs_button()
        self.ga_operation_page.wait_for_ajax()
        bok_choy.browser.save_screenshot(self.browser, 'test_click_publish_certs')

        self.assertEqual([u'このフィールドは必須です。'],
                         self.ga_operation_page.get_publish_certs_error_course_id_text())

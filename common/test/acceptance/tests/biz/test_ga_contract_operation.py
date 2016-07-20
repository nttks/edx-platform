# -*- coding: utf-8 -*-
"""
End-to-end tests for survey of biz feature
"""
from unittest import skip

from bok_choy.web_app_test import WebAppTest

from common.test.acceptance.pages.biz.ga_contract import BizContractPage
from common.test.acceptance.pages.biz.ga_navigation import BizNavPage
from common.test.acceptance.pages.common.logout import LogoutPage
from common.test.acceptance.pages.lms.account_settings import AccountSettingsPage
from common.test.acceptance.pages.lms.login_and_register import CombinedLoginAndRegisterPage
from common.test.acceptance.tests.biz import PLATFORMER_USER_INFO, \
    GaccoBizTestMixin, A_DIRECTOR_USER_INFO, A_COMPANY, PLAT_COMPANY_CODE
from lms.envs.bok_choy import EMAIL_FILE_PATH


@skip("TODO: implements with task history")
class BizContractOperationTest(WebAppTest, GaccoBizTestMixin):
    """
    Tests that the contract operation functionality of biz works
    """

    def setUp(self):
        super(BizContractOperationTest, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # Install course
        self.course_key, _ = self.install_course(PLAT_COMPANY_CODE)

        # Register a contract for A company
        self.switch_to_user(PLATFORMER_USER_INFO)
        self.organization = A_COMPANY
        self.contract = self.create_contract(BizContractPage(self.browser).visit(), 'PF', '2016/01/01',
                                             '2100/01/01', contractor_organization=self.organization,
                                             detail_info=[self.course_key], additional_info=[u'部署'])

    def test_as_director(self):
        """
        Tests that
        """
        existing_users = []
        for i in range(10):
            existing_users.append(self.register_user())

        new_users = []
        for i in range(10):
            username = 'test_' + self.unique_id[0:8]
            new_users.append({'username': username, 'password': 'Password123', 'email': username + '@example.com'})

        # Case 6, registered users and new users
        biz_register_students_page = self._visit_biz_register_students_page(A_DIRECTOR_USER_INFO)
        students = u'{},{},{}\r\n'.format(existing_users[0]['email'], existing_users[0]['username'],
                                          self.unique_id[0:8]) + \
                   u'{},{},{}\r\n'.format(existing_users[1]['email'], existing_users[1]['username'],
                                          self.unique_id[0:8]) + \
                   u'{},{},{}\r\n'.format(new_users[0]['email'], new_users[0]['username'], self.unique_id[0:8]) + \
                   u'{},{},{}'.format(new_users[1]['email'], new_users[1]['username'], self.unique_id[0:8])
        biz_register_students_page.input_students(students).click_register_button()
        self.assertEqual(['All accounts were created successfully.'], biz_register_students_page.messages)
        self._verify_sent_email(existing_users[0], True, self._get_message_from_messages(existing_users[0]['email']))
        self._verify_sent_email(existing_users[1], True, self._get_message_from_messages(existing_users[1]['email']))
        self._verify_sent_email(new_users[0], False, self._get_message_from_messages(new_users[0]['email']))
        self._verify_sent_email(new_users[1], False, self._get_message_from_messages(new_users[1]['email']))

        # Case 7, new user
        students = u'{},{},{}'.format(new_users[2]['email'], new_users[2]['username'], '')
        biz_register_students_page.input_students(students).click_register_button()
        self.assertEqual([u'Your legal name must be a minimum of two characters long'],
                         biz_register_students_page.messages)

        # Case 8, inactive user
        inactive_username = 'acom_student1'
        inactive_user = {
            'username': inactive_username,
            'password': 'edx',
            'email': inactive_username + '@example.com',
        }
        students = u'{},{},{}'.format(inactive_user['email'], inactive_username, self.unique_id[0:8])
        biz_register_students_page.input_students(students).click_register_button()
        self.assertEqual(['All accounts were created successfully.'], biz_register_students_page.messages)
        self._verify_sent_email(inactive_user, True, self.email_client.get_latest_message())
        LogoutPage(self.browser).visit()
        login_page = CombinedLoginAndRegisterPage(self.browser, start_page='login')
        login_page.visit().login(inactive_user['email'], inactive_user['password'])
        self.assertEqual([
            u'This account has not been activated. We have sent another activation message. Please check your email for the activation instructions.'],
                login_page.wait_for_errors())

        # Case 9
        self.email_client.clear_messages()
        biz_register_students_page = self._visit_biz_register_students_page(A_DIRECTOR_USER_INFO)
        students = u'{},{},{}'.format(existing_users[0]['email'], existing_users[0]['username'], '')
        biz_register_students_page.input_students(students).click_register_button()
        self.assertEqual(['All accounts were created successfully.'], biz_register_students_page.messages)
        # Check activation email.
        self._verify_sent_email(existing_users[0], True, self.email_client.get_latest_message())

        # Case 10, existing user, no name input
        students = u'{},{},{}'.format(existing_users[2]['email'], existing_users[2]['username'], '')
        biz_register_students_page.input_students(students).click_register_button()
        self.assertEqual(['All accounts were created successfully.'], biz_register_students_page.messages)
        # Check activation email.
        self._verify_sent_email(existing_users[2], True, self.email_client.get_latest_message())
        # Check username on account settings
        self.switch_to_user(existing_users[2])
        account_settings = AccountSettingsPage(self.browser).visit()
        account_settings.wait_for_field('name')
        self.assertEqual(existing_users[2]['username'], account_settings.value_for_text_field('name'))

        # Case 11, new user, no username input
        biz_register_students_page = self._visit_biz_register_students_page(A_DIRECTOR_USER_INFO)
        students = u'{},{},{}'.format(new_users[2]['email'], '', self.unique_id[0:8])
        biz_register_students_page.input_students(students).click_register_button()
        self.assertEqual(['Username must be minimum of two characters long'],
                         biz_register_students_page.messages)

        # Case 12, existing user, no username input
        students = u'{},{},{}'.format(existing_users[3]['email'], '', self.unique_id[0:8])
        biz_register_students_page.input_students(students).click_register_button()
        self.assertEqual([
            'An account with email {} exists but the registered username {} is different.'.format(
                    existing_users[3]['email'], existing_users[3]['username'])],
                biz_register_students_page.messages)
        # Check activation email.
        self._verify_sent_email(existing_users[3], True, self.email_client.get_latest_message())

        # Case 13
        username = 'test_' + self.unique_id[0:8]
        students = u'{},{},{}'.format(existing_users[4]['email'], username, self.unique_id[0:8])
        biz_register_students_page.input_students(students).click_register_button()
        self.assertEqual([
            'An account with email {} exists but the registered username {} is different.'.format(
                    existing_users[4]['email'], existing_users[4]['username'])],
                biz_register_students_page.messages)
        # Check activation email.
        self._verify_sent_email(existing_users[4], True, self.email_client.get_latest_message())

        # Case 14
        email = 'test_' + self.unique_id[0:8] + '@example.com'
        students = u'{},{},{}'.format(email, existing_users[5]['username'], self.unique_id[0:8])
        biz_register_students_page.input_students(students).click_register_button()
        self.assertEqual(['Username {} already exists.'.format(existing_users[5]['username'])],
                         biz_register_students_page.messages)

        # Case 15
        students = u'{},{},{}'.format(existing_users[6]['email'], existing_users[7]['username'], self.unique_id[0:8])
        biz_register_students_page.input_students(students).click_register_button()
        self.assertEqual([
            'An account with email {} exists but the registered username {} is different.'.format(
                    existing_users[6]['email'], existing_users[6]['username'])],
                biz_register_students_page.messages)
        # Check activation email.
        self._verify_sent_email(existing_users[6], True, self.email_client.get_latest_message())

        # Case 16
        students = u'{},{},{}\r\n'.format(existing_users[6]['email'], existing_users[6]['username'],
                                          self.unique_id[0:8]) + \
                   u'{},{},{}\r\n'.format(existing_users[7]['email'], existing_users[7]['username'],
                                          self.unique_id[0:8]) + \
                   u'{},{},{}\r\n'.format(new_users[6]['email'], new_users[6]['username'], self.unique_id[0:8]) + \
                   u'{},{},{}\r\n'.format(new_users[7]['email'], new_users[7]['username'], self.unique_id[0:8]) + \
                   u'{},{},{}\r\n'.format(existing_users[8]['email'], ',', self.unique_id[0:8]) + \
                   u'{},{},{}'.format(existing_users[9]['email'], ',', self.unique_id[0:8])
        biz_register_students_page.input_students(students).click_register_button()
        self._verify_sent_email(existing_users[6], True, self._get_message_from_messages(existing_users[6]['email']))
        self._verify_sent_email(existing_users[7], True, self._get_message_from_messages(existing_users[7]['email']))
        self._verify_sent_email(new_users[6], False, self._get_message_from_messages(new_users[6]['email']))
        self._verify_sent_email(new_users[7], False, self._get_message_from_messages(new_users[7]['email']))
        self.assertIsNone(self._get_message_from_messages(existing_users[8]['email']))
        self.assertIsNone(self._get_message_from_messages(existing_users[9]['email']))
        self.assertEqual([u'Data in row #5 must have exactly three columns: email, username, and full name.',
                          u'Data in row #6 must have exactly three columns: email, username, and full name.'],
                         biz_register_students_page.messages)

    def _visit_biz_register_students_page(self, user_info):
        self.switch_to_user(user_info)
        return BizNavPage(self.browser).visit() \
            .change_role(self.organization, self.contract['Contract Name'], self.course_key).click_register_students()

    def _verify_sent_email(self, user_info, is_existing_user, send_message):
        self.assertEqual(user_info['email'], send_message['to_addresses'])
        self.assertEqual(u'オンライン学習「edX」の受講予定者の方へ', send_message['subject'])
        if is_existing_user:
            self.assertIn(u'{}様'.format(user_info['username']), send_message['body'].decode('utf-8'))
        else:
            self.assertIn(u'{} の所有者の方へ'.format(user_info['email']), send_message['body'].decode('utf-8'))

    def _get_message_from_messages(self, to_addresses):
        for send_message in self.email_client.get_messages():
            if send_message['to_addresses'] == to_addresses:
                return send_message
        return None

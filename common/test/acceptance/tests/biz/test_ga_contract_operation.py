# -*- coding: utf-8 -*-
"""
End-to-end tests for survey of biz feature
"""
from datetime import datetime
from flaky import flaky
from unittest import skip

from bok_choy.web_app_test import WebAppTest
from django.utils.crypto import get_random_string
from nose.plugins.attrib import attr

from lms.envs.bok_choy import EMAIL_FILE_PATH

from . import GaccoBizTestMixin, PLAT_COMPANY_CODE, PLATFORMER_USER_INFO
from ..ga_helpers import NoEmailFileException, SUPER_USER_INFO
from ...pages.biz.ga_invitation import BizInvitationPage, BizInvitationConfirmPage
from ...pages.biz.ga_login import BizLoginPage
from ...pages.biz.ga_navigation import BizNavPage
from ...pages.lms.account_settings import AccountSettingsPage
from ...pages.lms.ga_dashboard import DashboardPage
from ...pages.lms.ga_django_admin import DjangoAdminPage
from ...pages.lms.ga_password_reset import PasswordResetCompletePage, PasswordResetConfirmPage
from ...pages.lms.login_and_register import CombinedLoginAndRegisterPage


class BizStudentRegisterMixin(object):

    def _make_students(self, user_info_list):
        return '\r\n'.join([
            '{},{},{}'.format(
                user_info['email'],
                user_info['username'],
                user_info['fullname'] if 'fullname' in user_info else 'Full Name'
            )
            for user_info in user_info_list
        ])

    def _make_students_auth(self, user_info_list):
        return '\r\n'.join([
            '{},{},{},{},{}'.format(
                user_info['email'],
                user_info['username'],
                user_info['fullname'] if 'fullname' in user_info else 'Full Name',
                user_info['login_code'] if 'login_code' in user_info else user_info['username'],
                user_info['password']
            )
            for user_info in user_info_list
        ])

    def _assert_register_student_task_history(self, grid_row, total, success, skipped, failed, user_info):
        self.assertEqual(u'Student Register', grid_row['Task Type'])
        self.assertEqual(u'Complete', grid_row['State'])
        self.assertEqual(u'Total: {}, Success: {}, Skipped: {}, Failed: {}'.format(total, success, skipped, failed), grid_row['Execution Result'])
        self.assertEqual(user_info['username'], grid_row['Execution Username'])
        self.assertIsNotNone(datetime.strptime(grid_row['Execution Datetime'], '%Y/%m/%d %H:%M:%S'))

    def _assert_no_send_email(self, user_info):
        try:
            send_message = self._get_message(user_info['email'])
        except NoEmailFileException:
            send_message = None
        self.assertIsNone(send_message)

    def _assert_send_email(self, user_info, is_existing_user):
        send_message = self._get_message(user_info['email'])
        self.assertIsNotNone(send_message)
        self.assertEqual(u'オンライン学習「edX」の受講予定者の方へ', send_message['subject'])
        if is_existing_user:
            self.assertIn(u'{}様'.format(user_info['username']), send_message['body'].decode('utf-8'))
        else:
            self.assertIn(u'{} の所有者の方へ'.format(user_info['email']), send_message['body'].decode('utf-8'))

    def _get_message(self, to_addresses):
        for send_message in self.email_client.get_messages():
            if send_message['to_addresses'] == to_addresses:
                return send_message
        return None


@attr('shard_ga_biz_1')
@flaky
class BizStudentRegisterTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):
    """
    Tests that the student register functionality of biz works
    """

    def setUp(self):
        super(BizStudentRegisterTest, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # Register organization
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', self.new_director)

        # Register contract
        new_course_key, _ = self.install_course(PLAT_COMPANY_CODE)
        new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], detail_info=[new_course_key])

        # Test user
        self.existing_users = [self.register_user() for _ in range(3)]
        self.new_users = [self.new_user_info for _ in range(3)]

    def test_register_students_06(self):
        """
        Case 6, registered users and new users
        """
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students([
            self.existing_users[0],
            self.existing_users[1],
            self.new_users[0],
            self.new_users[1],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            4, 4, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            biz_register_students_page.task_messages,
        )
        self._assert_send_email(self.existing_users[0], True)
        self._assert_send_email(self.existing_users[1], True)
        self._assert_send_email(self.new_users[0], False)
        self._assert_send_email(self.new_users[1], False)

    def test_register_students_07_11_12_13_14_15(self):
        """
        Case 7, new user
        Case 11, new user, no username input
        Case 12, existing user, no username input
        Case 13
        Case 14
        Case 15
        """
        # Test user update
        self.new_users[0].update({'fullname': ''})
        self.new_users[1].update({'username': ''})
        test_existing_users_0 = self.existing_users[0].copy()
        test_existing_users_0['username'] = ''
        test_existing_users_1 = self.existing_users[1].copy()
        test_existing_users_1['username'] = 'newusername'
        self.new_users[2].update({'username': self.existing_users[0]['username']})
        test_existing_users_2 = self.existing_users[2].copy()
        test_existing_users_2['username'] = self.existing_users[0]['username']

        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students([
            self.new_users[0],
            self.new_users[1],
            test_existing_users_0,
            test_existing_users_1,
            self.new_users[2],
            test_existing_users_2,
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            6, 3, 0, 3,
            self.new_director,
        )
        self.assertEqual(
            [
                u'Line 1:Your legal name must be a minimum of two characters long',
                u'Line 2:Username must be minimum of two characters long',
                u'Line 3:Warning, an account with email {} exists but the registered username {} is different.'.format(
                    self.existing_users[0]['email'],
                    self.existing_users[0]['username'],
                ),
                u'Line 4:Warning, an account with email {} exists but the registered username {} is different.'.format(
                    self.existing_users[1]['email'],
                    self.existing_users[1]['username'],
                ),
                u'Line 5:Username {} already exists.'.format(self.new_users[2]['username']),
                u'Line 6:Warning, an account with email {} exists but the registered username {} is different.'.format(
                    self.existing_users[2]['email'],
                    self.existing_users[2]['username'],
                ),
            ],
            biz_register_students_page.task_messages,
        )
        self._assert_no_send_email(self.new_users[0])
        self._assert_no_send_email(self.new_users[1])
        self._assert_send_email(self.existing_users[0], True)
        self._assert_send_email(self.existing_users[1], True)
        self._assert_no_send_email(self.new_users[2])
        self._assert_send_email(self.existing_users[2], True)

    def test_register_students_08_10(self):
        """
        Case 8, inactive user
        Case 10, existing user, no name input
        """
        # Test user update
        inactive_user = {
            'username': 'acom_student1',
            'password': 'edx',
            'email': 'acom_student1@example.com',
        }
        self.existing_users[0].update({'fullname': ''})

        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students([
            inactive_user,
            self.existing_users[0],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            2, 2, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            biz_register_students_page.task_messages
        )
        self._assert_send_email(inactive_user, True)
        self._assert_send_email(self.existing_users[0], True)

    def test_register_students_09(self):
        """
        Case 9
        """
        # First: Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students([
            self.new_users[0],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director
        )
        self.assertEqual(
            [u'No messages.'],
            biz_register_students_page.task_messages
        )
        self._assert_send_email(self.new_users[0], False)

        self.email_client.clear_messages()

        # Second: Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students([
            self.new_users[0],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director
        )
        self.assertEqual(
            [u'No messages.'],
            biz_register_students_page.task_messages
        )
        self._assert_send_email(self.new_users[0], True)

    def test_register_students_16(self):
        """
        Case 16
        """
        # Test user update
        self.existing_users[2].update({'fullname': ','})
        self.new_users[2].update({'fullname': ','})

        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students([
            self.existing_users[0],
            self.existing_users[1],
            self.new_users[0],
            self.new_users[1],
            self.existing_users[2],
            self.new_users[2],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            6, 4, 0, 2,
            self.new_director,
        )
        self.assertEqual(
            [
                u'Line 5:Data must have exactly three columns: email, username, and full name.',
                u'Line 6:Data must have exactly three columns: email, username, and full name.',
            ],
            biz_register_students_page.task_messages,
        )
        self._assert_send_email(self.existing_users[0], True)
        self._assert_send_email(self.existing_users[1], True)
        self._assert_send_email(self.new_users[0], False)
        self._assert_send_email(self.new_users[1], False)
        self._assert_no_send_email(self.existing_users[2])
        self._assert_no_send_email(self.new_users[2])


@attr('shard_ga_biz_1')
@flaky
class BizStudentRegisterWithContractAuthTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):
    """
    Tests that the student register functionality with contract auth of biz works
    Case detail: #1318
    """

    def setUp(self):
        super(BizStudentRegisterWithContractAuthTest, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # url code
        self.new_url_code = get_random_string(8)
        self.new_url_code_other = get_random_string(8)
        self.new_url_code_disabled = get_random_string(8)

        # page
        self.login_page = CombinedLoginAndRegisterPage(self.browser, 'login')
        self.dashboard_page = DashboardPage(self.browser)
        self.django_admin_page = DjangoAdminPage(self.browser)

        self.biz_login_page = BizLoginPage(self.browser, self.new_url_code)
        self.biz_login_page_other = BizLoginPage(self.browser, self.new_url_code_other)
        self.biz_login_page_disabled = BizLoginPage(self.browser, self.new_url_code_disabled, not_found=True)

        # Register organization
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)
        new_org_info_other = self.register_organization(PLATFORMER_USER_INFO)
        new_org_info_disabled = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', self.new_director)
        self.new_director_other = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info_other['Organization Name'], 'director', self.new_director_other)

        # Register contract
        new_course_key, _ = self.install_course(PLAT_COMPANY_CODE)
        self.new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], detail_info=[new_course_key])
        self.invitation_confirm_page = BizInvitationConfirmPage(self.browser, self.new_contract['Invitation Code'])

        # Register contract other
        new_course_key_other, _ = self.install_course(PLAT_COMPANY_CODE)
        self.new_contract_other = self.register_contract(PLATFORMER_USER_INFO, new_org_info_other['Organization Name'], detail_info=[new_course_key_other])

        # Register contract disabled
        new_course_key_disabled, _ = self.install_course(PLAT_COMPANY_CODE)
        self.new_contract_disabled = self.register_contract(PLATFORMER_USER_INFO, new_org_info_disabled['Organization Name'], end_date='2000/12/31', detail_info=[new_course_key_disabled])

        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractauth')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'url_code': self.new_url_code,
            'send_mail': True,
        }).save()
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractauth')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract_other['Contract Name'],
            'url_code': self.new_url_code_other,
            'send_mail': True,
        }).save()
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractauth')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract_disabled['Contract Name'],
            'url_code': self.new_url_code_disabled,
            'send_mail': True,
        }).save()

        # Test user
        self.existing_users = [self.register_user() for _ in range(3)]
        self.new_users = [self.new_user_info for _ in range(10)]

    def test_26_27(self):
        """
        Case 26, register users limit count
        Case 27, register users over count
        """
        # Case 26
        new_users_10 = [self.new_user_info for _ in range(10)]
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth(new_users_10)).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            10, 10, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            biz_register_students_page.task_messages,
        )
        for new_user in new_users_10:
            self._assert_send_email(new_user, False)

        # Case 27
        new_users_11 = [self.new_user_info for _ in range(11)]
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth(new_users_11)).click_register_button().click_popup_yes()

        self.assertEqual(
            [u'It has exceeded the number(10) of cases that can be a time of registration.'],
            biz_register_students_page.messages
        )

    def test_22_23_24_25(self):
        """
        Case 22, invalid login code
        Case 23, invalid password
        Case 24, change password
        Case 25, register invitation code
        """
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth([
            self.new_users[0],
            self.new_users[1],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            2, 2, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            biz_register_students_page.task_messages,
        )
        self._assert_send_email(self.new_users[0], False)
        self._assert_send_email(self.new_users[1], False)
        self.email_client.clear_messages()

        # Test user update
        self.new_users[0].update({
            'login_code': self.new_users[2]['username'],
        })
        self.new_users[1].update({
            'password': self.new_users[2]['password'],
        })
        # Go to register again
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth([
            self.new_users[0],
            self.new_users[1],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            2, 2, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [
                u'Line 1:Warning, an account with email {} exists but the registered login code {} is different.'.format(self.new_users[0]['email'], self.new_users[0]['username']),
                u'Line 2:Warning, an account with email {} exists but the registered password is different.'.format(self.new_users[1]['email']),
            ],
            biz_register_students_page.task_messages,
        )
        self._assert_send_email(self.new_users[0], True)
        self._assert_send_email(self.new_users[1], True)
        self.email_client.clear_messages()

        # Case 24
        new_password = self.new_password
        self.switch_to_user(self.new_users[0])
        AccountSettingsPage(self.browser).visit().click_on_link_in_link_field('password')
        uidb36, token = self.assert_email_password_reset()
        password_reset_confirm_page = PasswordResetConfirmPage(self.browser, uidb36, token).visit()
        password_reset_confirm_page.fill_password(new_password, new_password).submit()
        PasswordResetCompletePage(self.browser).wait_for_page()

        # Case 25
        self.new_users[0].update({
            'password': new_password,
        })
        self.switch_to_user(self.new_users[0])
        AccountSettingsPage(self.browser).visit().click_on_link_in_link_field('invitation_code')
        BizInvitationPage(self.browser).wait_for_page().input_invitation_code(self.new_contract['Invitation Code']).click_register_button()
        BizInvitationConfirmPage(self.browser, self.new_contract['Invitation Code']).wait_for_page().click_register_button()
        DashboardPage(self.browser).wait_for_page()

    def test_19_20_21(self):
        """
        Case 19, 3 column
        Case 20, invalid login code
        Case 21, invalid password
        """
        # Test user update
        self.new_users[1].update({
            'login_code': '@hoge-$',
        })
        self.new_users[2].update({
            'password': '@hoge-$',
        })
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students('\r\n'.join([self._make_students([
                self.new_users[0],
            ]),
            self._make_students_auth([
                self.new_users[1],
                self.new_users[2],
            ])
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            3, 0, 0, 3,
            self.new_director,
        )
        self.assertEqual(
            [
                u'Line 1:Data must have exactly five columns: email, username, full name, login code and password.',
                u'Line 2:Invalid login code {}.'.format(self.new_users[1]['login_code']),
                u'Line 3:Invalid password {}.'.format(self.new_users[2]['password']),
            ],
            biz_register_students_page.task_messages,
        )
        self._assert_no_send_email(self.new_users[0])
        self.email_client.clear_messages()

    def test_07_12_13_15_16_17_18(self):
        """
        Case 7, disabled contract can not login
        Case 12, exist username
        Case 13, exist login_code
        Case 15, exist email
        Case 16, exist email, username
        Case 17, exist email, username, login_code(registerd)
        Case 18, exist email, username, login_code
        """
        # Case 7, disabled contract can not login
        self.biz_login_page_disabled.visit()

        # Test user update
        self.new_users[0].update({
            'username': self.existing_users[0]['username'],
        })
        self.new_users[2].update({
            'email': self.existing_users[0]['email'],
            'login_code': self.existing_users[0]['username'],
        })
        self.new_users[3].update({
            'email': self.existing_users[1]['email'],
            'username': self.existing_users[1]['username'],
        })
        self.new_users[1].update({
            'login_code': self.existing_users[0]['username'],
        })

        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth([
            self.new_users[0],
            self.new_users[2],
            self.new_users[3],
            self.new_users[1],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            4, 2, 0, 2,
            self.new_director,
        )
        self.assertEqual(
            [
                u'Line 1:Username {} already exists.'.format(self.new_users[0]['username']),
                u'Line 2:Warning, an account with email {email} exists but the registered username {username} is different.Warning, an account with email {email} exists but the registered password is different.'.format(
                    email=self.new_users[2]['email'],
                    username=self.existing_users[0]['username']
                ),
                u'Line 3:Warning, an account with email {} exists but the registered password is different.'.format(self.new_users[3]['email']),
                u'Line 4:Login code {} already exists.'.format(self.new_users[1]['login_code'])
            ],
            biz_register_students_page.task_messages,
        )
        self._assert_no_send_email(self.new_users[0])
        self._assert_no_send_email(self.new_users[1])
        self._assert_send_email(self.existing_users[0], True)
        self._assert_send_email(self.existing_users[1], True)
        self.email_client.clear_messages()

        # Case 17
        self.new_users[4].update({
            'email': self.existing_users[1]['email'],
            'username': self.existing_users[1]['username'],
            'login_code': self.existing_users[1]['username'],
        })

        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth([
            self.new_users[4],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'Line 1:Warning, an account with email {} exists but the registered password is different.'.format(self.new_users[4]['email'])],
            biz_register_students_page.task_messages,
        )
        self._assert_send_email(self.new_users[4], True)
        self.email_client.clear_messages()

        # Case 18
        self.new_users[5].update({
            'email': self.existing_users[1]['email'],
            'username': self.existing_users[1]['username'],
            'login_code': self.existing_users[0]['username'],
        })

        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth([
            self.new_users[5],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            1, 0, 0, 1,
            self.new_director,
        )
        self.assertEqual(
            [u'Line 1:Login code {} already exists.'.format(self.new_users[5]['login_code'])],
            biz_register_students_page.task_messages,
        )
        self._assert_no_send_email(self.new_users[5])

    def test_05_14(self):
        """
        Case 5, register student and register student other contract can not login other contract
        Case 14, register student same login code other contract
        """
        self.new_users[0].update({
        })
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth([
            self.existing_users[0],
            self.new_users[0],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            2, 2, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            biz_register_students_page.task_messages,
        )
        self._assert_send_email(self.existing_users[0], True)
        self._assert_send_email(self.new_users[0], False)

        # Case 14
        self.existing_users[1].update({
            'login_code': self.existing_users[0]['username'],
        })
        self.new_users[1].update({
            'login_code': self.new_users[0]['username'],
        })

        # Go to register other
        self.switch_to_user(self.new_director_other)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth([
            self.existing_users[1],
            self.new_users[1],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            2, 2, 0, 0,
            self.new_director_other,
        )
        self.assertEqual(
            [u'No messages.'],
            biz_register_students_page.task_messages,
        )
        self._assert_send_email(self.existing_users[1], True)
        self._assert_send_email(self.new_users[1], False)

        # Login existing_user
        self.logout()
        self.biz_login_page.visit().input(self.existing_users[0]['username'], self.existing_users[0]['password']).click_login()
        self.invitation_confirm_page.wait_for_page()

        # Login new_user
        self.logout()
        self.biz_login_page.visit().input(self.new_users[0]['username'], self.new_users[0]['password']).click_login()
        self.invitation_confirm_page.wait_for_page()

        # Login other existing_user
        self.logout()
        self.biz_login_page_other.visit().input(self.existing_users[1]['login_code'], self.existing_users[1]['password']).click_login()
        self.invitation_confirm_page.wait_for_page()

        # Login other new_user
        self.logout()
        self.biz_login_page_other.visit().input(self.new_users[1]['login_code'], self.new_users[1]['password']).click_login()
        self.invitation_confirm_page.wait_for_page()

        # Login existing_user to other
        self.logout()
        self.biz_login_page_other.visit().input(self.existing_users[0]['username'], self.existing_users[0]['password']).click_login()
        self.assertEqual(
            [u'Login code or password is incorrect.'],
            self.biz_login_page_other.error_messages,
        )

        # Login new_user to other
        self.logout()
        self.biz_login_page_other.visit().input(self.new_users[0]['username'], self.new_users[0]['password']).click_login()
        self.assertEqual(
            [u'Login code or password is incorrect.'],
            self.biz_login_page_other.error_messages,
        )

        # Login other existing_user to other
        self.logout()
        self.biz_login_page.visit().input(self.existing_users[1]['login_code'], self.existing_users[1]['password']).click_login()
        self.assertEqual(
            [u'Login code or password is incorrect.'],
            self.biz_login_page.error_messages,
        )

        # Login other new_user to other
        self.logout()
        self.biz_login_page.visit().input(self.new_users[1]['login_code'], self.new_users[1]['password']).click_login()
        self.assertEqual(
            [u'Login code or password is incorrect.'],
            self.biz_login_page.error_messages,
        )

    def test_01_02_03_04_06_08_09_10_11_28_29(self):
        """
        Case 1, register student and login with login_code and register invitation code to dashboard
        Case 2, bizlogin with login_code after register invitation code to dashboard
        Case 3, login with email after register invitation code to dashboard
        Case 4, bizlogin with email after register invitation code to occur error
        Case 6, Not found url_code to 404
        Case 8, Update url_code to dashboard
        Case 9, Update illegal url_code
        Case 10, Delete url_code to 404
        Case 11, (See:Case 1)
        Case 28, Success new user
        Case 29, Success existing user
        """
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth([
            self.existing_users[0],
            self.new_users[0],
        ])).click_register_button().click_popup_yes()

        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Show task history
        biz_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            biz_register_students_page.task_history_grid_row,
            2, 2, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            biz_register_students_page.task_messages,
        )
        self._assert_send_email(self.existing_users[0], True)
        self._assert_send_email(self.new_users[0], False)

        # Login existing_user first
        self.logout()
        self.biz_login_page.visit().input(self.existing_users[0]['username'], self.existing_users[0]['password']).click_login()
        self.invitation_confirm_page.wait_for_page().click_register_button()
        self.dashboard_page.wait_for_page()

        # Login new_user first
        self.logout()
        self.biz_login_page.visit().input(self.new_users[0]['username'], self.new_users[0]['password']).click_login()
        self.invitation_confirm_page.wait_for_page().click_register_button()
        self.dashboard_page.wait_for_page()

        # Login existing_user second
        self.logout()
        self.biz_login_page.visit().input(self.existing_users[0]['username'], self.existing_users[0]['password']).click_login()
        self.dashboard_page.wait_for_page()

        # Login new_user second
        self.logout()
        self.biz_login_page.visit().input(self.new_users[0]['username'], self.new_users[0]['password']).click_login()
        self.dashboard_page.wait_for_page()

        # Login existing_user with email
        self.logout()
        self.login_page.visit().login(self.existing_users[0]['email'], self.existing_users[0]['password'])
        self.dashboard_page.wait_for_page()

        # Login new_user with email
        self.logout()
        self.login_page.visit().login(self.new_users[0]['email'], self.new_users[0]['password'])
        self.dashboard_page.wait_for_page()

        # Login existing_user with email
        self.logout()
        self.biz_login_page.visit().input(self.existing_users[0]['email'], self.existing_users[0]['password']).click_login()
        self.assertEqual([
            u'Login code or password is incorrect.'
        ], self.biz_login_page.error_messages)

        # Login new_user with email
        self.logout()
        self.biz_login_page.visit().input(self.new_users[0]['email'], self.new_users[0]['password']).click_login()
        self.assertEqual([
            u'Login code or password is incorrect.'
        ], self.biz_login_page.error_messages)

        # Go to illegal url_code
        self.logout()
        BizLoginPage(self.browser, 'hogehoge', not_found=True).visit()

        # Update url_code
        self.switch_to_user(SUPER_USER_INFO)
        modified_url_code = get_random_string(8)
        django_admin_list_page = self.django_admin_page.visit().click_list('ga_contract', 'contractauth')
        django_admin_list_page.click_grid_anchor(django_admin_list_page.get_row({
            'Contract auth': '{}({})'.format(self.new_contract['Contract Name'], self.new_url_code),
        })).input({
            'url_code': modified_url_code,
        }).save()
        modified_url_code_biz_login_page = BizLoginPage(self.browser, modified_url_code)

        # Login existing_user modified url_code biz_login_page
        self.logout()
        modified_url_code_biz_login_page.visit().input(self.existing_users[0]['username'], self.existing_users[0]['password']).click_login()
        self.dashboard_page.wait_for_page()

        # Login new_user modified url_code biz_login_page
        self.logout()
        modified_url_code_biz_login_page.visit().input(self.new_users[0]['username'], self.new_users[0]['password']).click_login()
        self.dashboard_page.wait_for_page()

        # Update url_code of illegal
        self.switch_to_user(SUPER_USER_INFO)
        illegal_url_code = get_random_string(7)
        django_admin_list_page = self.django_admin_page.visit().click_list('ga_contract', 'contractauth')
        django_admin_modify_page = django_admin_list_page.click_grid_anchor(django_admin_list_page.get_row({
            'Contract auth': '{}({})'.format(self.new_contract['Contract Name'], modified_url_code),
        })).input({
            'url_code': illegal_url_code,
        }).save(success=False)
        self.assertEqual([u'Url code is invalid. Please enter alphanumeric 8-255 characters.'], django_admin_modify_page.error_messages)

        # Delete url_code
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_list_page = self.django_admin_page.visit().click_list('ga_contract', 'contractauth')
        django_admin_list_page.click_grid_anchor(django_admin_list_page.get_row({
            'Contract auth': '{}({})'.format(self.new_contract['Contract Name'], modified_url_code),
        })).click_delete().click_yes()

        # Go to deleted url_code
        self.logout()
        BizLoginPage(self.browser, modified_url_code, not_found=True).visit()

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
from ...pages.biz.ga_contract_operation import BizBulkStudentsPage, BizStudentsPage
from ...pages.biz.ga_course_about import CourseAboutPage
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
        self.assertEqual(u'Student Member Register', grid_row['Task Type'])
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
        self.assertEqual(u'オンライン学習「gacco」の受講予定者の方へ', send_message['subject'])
        if is_existing_user:
            self.assertIn(u'{}様'.format(user_info['username']), send_message['body'].decode('utf-8'))
        else:
            self.assertIn(u'{} の所有者の方へ'.format(user_info['email']), send_message['body'].decode('utf-8'))

    def _get_message(self, to_addresses):
        for send_message in self.email_client.get_messages():
            if send_message['to_addresses'] == to_addresses:
                return send_message
        return None

    def _assert_can_register_invitation_code(self):
        self.account_settings_page.visit().click_on_link_in_link_field('invitation_code')
        self.invitation_page.wait_for_page().input_invitation_code(self.new_invitation_code).click_register_button()
        self.invitation_confirm_page.wait_for_page().click_register_button()
        self.dashboard_page.wait_for_page()

    def _assert_cannot_register_invitation_code(self):
        self.account_settings_page.visit().click_on_link_in_link_field('invitation_code')
        self.invitation_page.wait_for_page().input_invitation_code(self.new_invitation_code).click_register_button()
        self.assertIn('Please ask your administrator to register the invitation code.', self.invitation_page.messages)


@attr('shard_ga_biz_2')
@flaky
class BizOneStudentRegisterTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):
    """
    Tests that one student register functionality of biz works
    """

    def setUp(self):
        super(BizOneStudentRegisterTest, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # Register organization
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', self.new_director)

        # Register contract
        new_course_key, new_course_name = self.install_course(PLAT_COMPANY_CODE)
        self.new_course_name = new_course_name
        new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], detail_info=[new_course_key])
        self.new_invitation_code = new_contract['Invitation Code']
        self.invitation_confirm_page = BizInvitationConfirmPage(self.browser, self.new_invitation_code)

        # Test user
        self.existing_user = self.register_user()
        self.new_user = self.new_user_info

    def test_register_one_student_new_user(self):
        """
        Case: registered one user and new user
        """
        # Go to register
        self.switch_to_user(self.new_director)
        one_register_students_page = BizNavPage(self.browser).visit().click_register_students().click_tab_one_register_student()
        one_register_students_page.input_one_user_info(self.new_user).click_one_register_button().click_popup_yes()

        one_register_students_page.wait_for_message(
            u'Began the processing of Student Member Register.Execution status, please check from the task history.'
        )

        # Show task history
        one_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            one_register_students_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            one_register_students_page.task_messages,
        )
        self._assert_send_email(self.new_user, False)

    def test_register_one_student_existing_user(self):
        """
        Case: registered one user and existing user
        """
        # Go to register
        self.switch_to_user(self.new_director)
        one_register_students_page = BizNavPage(self.browser).visit().click_register_students().click_tab_one_register_student()
        one_register_students_page.input_one_user_info(self.existing_user).click_one_register_button().click_popup_yes()

        one_register_students_page.wait_for_message(
            u'Began the processing of Student Member Register.Execution status, please check from the task history.'
        )

        # Show task history
        one_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            one_register_students_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            one_register_students_page.task_messages,
        )
        self._assert_send_email(self.existing_user, True)


@attr('shard_ga_biz_2')
@flaky
class BizOneStudentRegisterWithContractAuthTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):
    """
    Tests that one student register functionality with contract auth of biz works
    """

    def setUp(self):
        super(BizOneStudentRegisterWithContractAuthTest, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # url code
        self.new_url_code = get_random_string(8)

        # page
        self.login_page = CombinedLoginAndRegisterPage(self.browser, 'login')
        self.dashboard_page = DashboardPage(self.browser)
        self.django_admin_page = DjangoAdminPage(self.browser)

        self.biz_login_page = BizLoginPage(self.browser, self.new_url_code)

        # Register organization
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', self.new_director)

        # Register contract
        new_course_key, new_course_name = self.install_course(PLAT_COMPANY_CODE)
        self.new_course_name = new_course_name
        self.new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], detail_info=[new_course_key])

        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractauth')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'url_code': self.new_url_code,
            'send_mail': True,
        }).save()

        # Test user
        self.existing_user = self.register_user()
        self.new_user = self.new_user_info

    def test_register_one_student_new_user_with_auth(self):
        """
        Case: registered one user and new user with contract auth
        """
        # Go to register
        self.switch_to_user(self.new_director)
        one_register_students_page = BizNavPage(self.browser).visit().click_register_students().click_tab_one_register_student()
        one_register_students_page.input_one_user_info_auth(self.new_user).click_one_register_button().click_popup_yes()

        one_register_students_page.wait_for_message(
            u'Began the processing of Student Member Register.Execution status, please check from the task history.'
        )

        # Show task history
        one_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            one_register_students_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            one_register_students_page.task_messages,
        )
        self._assert_send_email(self.new_user, False)

    def test_register_one_student_existing_user_with_auth(self):
        """
        Case: registered one user and existing user with contract auth
        """
        # Go to register
        self.switch_to_user(self.new_director)
        one_register_students_page = BizNavPage(self.browser).visit().click_register_students().click_tab_one_register_student()
        one_register_students_page.input_one_user_info_auth(self.existing_user).click_one_register_button().click_popup_yes()

        one_register_students_page.wait_for_message(
            u'Began the processing of Student Member Register.Execution status, please check from the task history.'
        )

        # Show task history
        one_register_students_page.click_show_history()

        self._assert_register_student_task_history(
            one_register_students_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            one_register_students_page.task_messages,
        )
        self._assert_send_email(self.existing_user, True)


@attr('shard_ga_biz_2')
@flaky
class BizStudentRegisterTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):
    """
    Tests that the student register functionality of biz works
    """

    def setUp(self):
        super(BizStudentRegisterTest, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # page
        self.dashboard_page = DashboardPage(self.browser)
        self.account_settings_page = AccountSettingsPage(self.browser)
        self.invitation_page = BizInvitationPage(self.browser)

        # Register organization
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', self.new_director)

        # Register contract
        new_course_key, new_course_name = self.install_course(PLAT_COMPANY_CODE)
        self.new_course_name = new_course_name
        new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], detail_info=[new_course_key])
        self.new_invitation_code = new_contract['Invitation Code']
        self.invitation_confirm_page = BizInvitationConfirmPage(self.browser, self.new_invitation_code)

        # Test user
        self.existing_users = [self.register_user() for _ in range(3)]
        self.new_users = [self.new_user_info for _ in range(3)]

    @skip("Modified by JAST later")
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

    @skip("Modified by JAST later")
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
                u'Line 3:Warning, an account with the e-mail {} exists but the registered username {} is different.'.format(
                    self.existing_users[0]['email'],
                    self.existing_users[0]['username'],
                ),
                u'Line 4:Warning, an account with the e-mail {} exists but the registered username {} is different.'.format(
                    self.existing_users[1]['email'],
                    self.existing_users[1]['username'],
                ),
                u'Line 5:Username {} already exists.'.format(self.new_users[2]['username']),
                u'Line 6:Warning, an account with the e-mail {} exists but the registered username {} is different.'.format(
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

    @skip("Modified by JAST later")
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

    @skip("Modified by JAST later")
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

    @skip("Modified by JAST later")
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

    @skip("Modified by JAST later")
    def test_register_students_checked_register_status(self):
        """
        Case, registered users and new users with checked register status
        """
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students([
            self.existing_users[0],
            self.existing_users[1],
            self.new_users[0],
            self.new_users[1],
        ])).click_register_status().click_popup_ok().click_register_button().click_popup_yes()

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

        # Login existing user
        self.switch_to_user(self.existing_users[0])
        self.dashboard_page.visit()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertTrue(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        self.switch_to_user(self.existing_users[1])
        self.dashboard_page.visit()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertTrue(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        # Login new user
        self.switch_to_user(self.new_users[0])
        self.dashboard_page.visit()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertTrue(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        self.switch_to_user(self.new_users[1])
        self.dashboard_page.visit()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertTrue(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()


@attr('shard_ga_biz_3')
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
        self.account_settings_page = AccountSettingsPage(self.browser)
        self.invitation_page = BizInvitationPage(self.browser)

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
        new_course_key, new_course_name = self.install_course(PLAT_COMPANY_CODE)
        self.new_course_name = new_course_name
        self.new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], detail_info=[new_course_key])
        self.new_invitation_code = self.new_contract['Invitation Code']
        self.invitation_confirm_page = BizInvitationConfirmPage(self.browser, self.new_invitation_code)

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

    @skip("Modified by JAST later")
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

    @skip("Modified by JAST later")
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
                u'Line 1:Warning, an account with the e-mail {} exists but the registered login code {} is different.'.format(self.new_users[0]['email'], self.new_users[0]['username']),
                u'Line 2:Warning, an account with the e-mail {} exists but the registered password is different.'.format(self.new_users[1]['email']),
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
        self._assert_can_register_invitation_code()

    @skip("Modified by JAST later")
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

    @skip("Modified by JAST later")
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
                u'Line 2:Warning, an account with the e-mail {email} exists but the registered username {username} is different.Warning, an account with the e-mail {email} exists but the registered password is different.'.format(
                    email=self.new_users[2]['email'],
                    username=self.existing_users[0]['username']
                ),
                u'Line 3:Warning, an account with the e-mail {} exists but the registered password is different.'.format(self.new_users[3]['email']),
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
            [u'Line 1:Warning, an account with the e-mail {} exists but the registered password is different.'.format(self.new_users[4]['email'])],
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

    @skip("Modified by JAST later")
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

    @skip("Modified by JAST later")
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

    @skip("Modified by JAST later")
    def test_register_students_checked_register_status(self):
        """
        Case, registered users and new users with checked register status
        """
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students()
        biz_register_students_page.input_students(self._make_students_auth([
            self.existing_users[0],
            self.existing_users[1],
            self.new_users[0],
            self.new_users[1],
        ])).click_register_status().click_popup_ok().click_register_button().click_popup_yes()

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

        # Login existing user
        self.logout()
        self.biz_login_page.visit().input(self.existing_users[0]['username'], self.existing_users[0]['password']).click_login()
        self.dashboard_page.wait_for_page()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertTrue(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        self.logout()
        self.biz_login_page.visit().input(self.existing_users[1]['username'], self.existing_users[1]['password']).click_login()
        self.dashboard_page.wait_for_page()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertTrue(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        # Login new user
        self.logout()
        self.biz_login_page.visit().input(self.new_users[0]['username'], self.new_users[0]['password']).click_login()
        self.dashboard_page.wait_for_page()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertTrue(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        self.logout()
        self.biz_login_page.visit().input(self.new_users[1]['username'], self.new_users[1]['password']).click_login()
        self.dashboard_page.wait_for_page()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertTrue(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()


class BizStudentManagementTestBase(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):

    def setUp(self):
        super(BizStudentManagementTestBase, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # Register organization
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', self.new_director)

        # Register contract
        self.new_course_key, _ = self.install_course(PLAT_COMPANY_CODE)
        self.new_contract = self.register_contract(
            PLATFORMER_USER_INFO, new_org_info['Organization Name'],
            detail_info=[self.new_course_key]
        )

        self.users = [self.register_user() for _ in range(3)]
        self._register_student(self.users[0], do_register=True)
        self._register_student(self.users[1])
        self._register_student(self.users[2])

        self.students_page = BizStudentsPage(self.browser)
        self.bulk_students_page = BizBulkStudentsPage(self.browser)

    def _register_student(self, user, do_register=False):
        self.switch_to_user(user)
        AccountSettingsPage(self.browser).visit().click_on_link_in_link_field('invitation_code')
        BizInvitationPage(self.browser).wait_for_page().input_invitation_code(self.new_contract['Invitation Code']).click_register_button()
        biz_invitation_confirm_page = BizInvitationConfirmPage(self.browser, self.new_contract['Invitation Code']).wait_for_page()
        if do_register:
            biz_invitation_confirm_page.input_additional_info(
                'info1-{}'.format(user['username']), 0
            ).input_additional_info(
                'info2-{}'.format(user['username']), 1
            ).click_register_button()
            DashboardPage(self.browser).wait_for_page()
            user['status'] = 'Register Invitation'
        else:
            user['status'] = 'Input Invitation'

    def _assert_grid_row(self, grid_row, expected_user, expected_status=None):
        if expected_status is None:
            expected_status = expected_user['status']
        self.assert_grid_row(grid_row, {
            'Register Status': expected_status,
            'Email Address': expected_user['email'],
            'Username': expected_user['username'],
            'Full Name': expected_user['username'],
        })

    def _assert_task_history(self, grid_row, task_type, state, username, total=0, success=0, skipped=0, failed=0):
        self.assertEqual(task_type, grid_row['Task Type'])
        self.assertEqual(state, grid_row['State'])
        self.assertEqual(
            u'Total: {}, Success: {}, Skipped: {}, Failed: {}'.format(total, success, skipped, failed),
            grid_row['Execution Result']
        )
        self.assertEqual(username, grid_row['Execution Username'])
        self.assertIsNotNone(datetime.strptime(grid_row['Execution Datetime'], '%Y/%m/%d %H:%M:%S'))


@attr('shard_ga_biz_3')
class BizStudentListTest(BizStudentManagementTestBase):

    @skip("Modified by JAST later")
    def test_students_grid_column(self):
        self.switch_to_user(self.new_director)
        self.students_page.visit()

        # Check data rows of student grid
        for user in self.users:
            self._assert_grid_row(self.students_page.student_grid.get_row({'Username': user['username']}), user)
        # Task History should be empty.
        self.assertFalse(self.students_page.task_history_grid.grid_rows)

        # Check default columns
        grid_columns = self.students_page.student_grid.grid_columns
        self.assertItemsEqual(grid_columns, [
            '', 'Register Status', 'Full Name', 'Username', 'Email Address',
        ])

        # Check icon columns on/off
        self.students_page.student_grid.click_grid_icon_columns()
        for c in self.students_page.student_grid.grid_icon_columns:
            if c in grid_columns:
                self.assertTrue(self.students_page.student_grid.is_checked_grid_icon_columns(c))
            else:
                self.assertFalse(self.students_page.student_grid.is_checked_grid_icon_columns(c))

        self.students_page.student_grid.click_grid_icon_columns_checkbox('Register Status')

        grid_columns = self.students_page.student_grid.grid_columns
        self.assertItemsEqual(grid_columns, [
            '', 'Full Name', 'Username', 'Email Address',
        ])

        self.students_page.student_grid.click_grid_icon_columns_checkbox('Register Status')

        grid_columns = self.students_page.student_grid.grid_columns
        self.assertItemsEqual(grid_columns, [
            '', 'Register Status', 'Full Name', 'Username', 'Email Address',
        ])

        # Check columns of grid for search
        """
        'All search items' are not English-ready.
        Because UTF - 16 is used for code conversion, we make the following description
        u'\u5168\u3066\u306e\u691c\u7d22\u9805\u76ee'
        """
        self.students_page.student_grid.click_grid_icon_search()
        grid_icon_search = self.students_page.student_grid.grid_icon_search
        self.assertItemsEqual(grid_icon_search, [
            u'\u5168\u3066\u306e\u691c\u7d22\u9805\u76ee', 'Register Status', 'Full Name', 'Username', 'Email Address',
        ])
        self.assertTrue(self.students_page.student_grid.is_checked_grid_icon_search(u'\u5168\u3066\u306e\u691c\u7d22\u9805\u76ee'))

        # Check search
        self.students_page.student_grid.click_grid_icon_search_label('Username')
        self.students_page.student_grid.search(self.users[1]['username'])

        grid_rows = self.students_page.student_grid.grid_rows
        self.assertEqual(len(grid_rows), 1)
        self._assert_grid_row(grid_rows[0], self.users[1])

        self.students_page.student_grid.clear_search()
        for user in self.users:
            self._assert_grid_row(self.students_page.student_grid.get_row({'Username': user['username']}), user)

        # Check sort
        grid_rows = self.students_page.student_grid.grid_rows

        # sort by Username
        self.students_page.student_grid.click_sort('Username')
        grid_rows.sort(key=lambda x: x['Username'])
        self.assert_grid_row_equal(grid_rows, self.students_page.student_grid.grid_rows)
        # sort by Username reverse
        self.students_page.student_grid.click_sort('Username')
        grid_rows.sort(key=lambda x: x['Username'], reverse=True)
        self.assert_grid_row_equal(grid_rows, self.students_page.student_grid.grid_rows)

        # Check search of all keywords
        self.students_page.student_grid.click_grid_icon_search()
        self.students_page.student_grid.click_grid_icon_all_search_label()
        self.students_page.student_grid.search(self.users[2]['email'])
        grid_rows = self.students_page.student_grid.grid_rows

        self.assertEqual(len(grid_rows), 1)
        self._assert_grid_row(grid_rows[0], self.users[2])
        self.students_page.student_grid.clear_search()


class BizPersonalinfoMaskTestBase(BizStudentManagementTestBase):

    def _assert_masked_grid_row(self, grid_row, expected_user):
        # not masked value
        self.assertEqual(grid_row['Register Status'], 'Unregister Invitation')
        self.assertEqual(grid_row['Username'], expected_user['username'])
        # masked value
        self.assertNotEqual(grid_row['Email Address'], expected_user['email'])
        self.assertNotEqual(grid_row['Full Name'], expected_user['username'])

    def _assert_personalinfo_mask_task_history(self, grid_row, username, total=0, success=0, skipped=0, failed=0):
        self._assert_task_history(grid_row,
            task_type='Personal Information Mask',
            state='Complete',
            total=total, success=success, skipped=skipped, failed=failed,
            username=username,
        )

    def _assert_login(self, user, can_login=True):
        self.logout()
        login_page = CombinedLoginAndRegisterPage(self.browser, 'login')
        login_page.visit().login(user['email'], user['password'])
        if can_login:
            DashboardPage(self.browser).wait_for_page()
        else:
            login_page.wait_for_errors()


@attr('shard_ga_biz_3')
class BizPersonalinfoMaskTest(BizPersonalinfoMaskTestBase):

    @skip("Modified by JAST later")
    def test_success(self):
        # Check that can login
        for user in self.users:
            self._assert_login(user)

        self.switch_to_user(self.new_director)
        self.students_page.visit()

        # Check initial data rows of student grid
        for user in self.users:
            self._assert_grid_row(self.students_page.student_grid.get_row({'Username': user['username']}), user)

        # Check error message when target is not selected.
        self.students_page.click_personalinfo_mask_button()
        self.assertEqual(['Please select a target.'], self.students_page.messages)

        # Select target users and execute
        self.students_page.student_grid.click_grid_row_checkbox({'Username': self.users[0]['username']})
        self.students_page.student_grid.click_grid_row_checkbox({'Username': self.users[2]['username']})

        self.students_page.click_personalinfo_mask_button().click_popup_yes()
        self.students_page.wait_for_ajax()

        self.assertEqual(
            ['Began the processing of Personal Information Mask.Execution status, please check from the task history.'],
            self.students_page.messages
        )

        # Check task histories
        self.students_page.wait_for_task_complete()
        self._assert_personalinfo_mask_task_history(
            self.students_page.task_history_grid_row,
            self.new_director['username'], 2, 2, 0, 0
        )

        self.students_page.visit()

        # Check unmasked data rows of student grid
        self._assert_grid_row(self.students_page.student_grid.get_row({'Username': self.users[1]['username']}), self.users[1])
        # Check masked data rows of student grid
        self._assert_masked_grid_row(self.students_page.student_grid.get_row({'Username': self.users[0]['username']}), self.users[0])
        self._assert_masked_grid_row(self.students_page.student_grid.get_row({'Username': self.users[2]['username']}), self.users[2])

        # Check that masked user cannot login
        self._assert_login(self.users[0], False)
        self._assert_login(self.users[1])
        self._assert_login(self.users[2], False)


class BizStudentUnregisterTestBase(BizStudentManagementTestBase):

    def _assert_access_course_about(self, user, can_access=True):
        self.switch_to_user(user)
        CourseAboutPage(self.browser, self.new_course_key, not can_access).visit()


@attr('shard_ga_biz_3')
class BizStudentUnregisterTest(BizStudentUnregisterTestBase):

    @skip("Modified by JAST later")
    def test_success(self):
        # Check registered user can access to course about
        self._assert_access_course_about(self.users[0])

        self.switch_to_user(self.new_director)
        self.students_page.visit()

        # Check initial data rows of student grid
        for user in self.users:
            self._assert_grid_row(self.students_page.student_grid.get_row({'Username': user['username']}), user)

        # Check error message when target is not selected.
        self.students_page.click_unregister_button()
        self.assertEqual(['Please select a target.'], self.students_page.messages)

        # Select target users and execute
        self.students_page.student_grid.click_grid_row_checkbox({'Username': self.users[0]['username']})
        self.students_page.student_grid.click_grid_row_checkbox({'Username': self.users[2]['username']})

        self.students_page.click_unregister_button().click_popup_yes()
        self.students_page.wait_for_ajax()

        self.assertEqual(
            ['Succeed to unregister 2 users.'],
            self.students_page.messages
        )

        self.students_page.visit()

        # Check data rows after unregister
        self._assert_grid_row(self.students_page.student_grid.get_row({'Username': self.users[0]['username']}), self.users[0], expected_status='Unregister Invitation')
        self._assert_grid_row(self.students_page.student_grid.get_row({'Username': self.users[1]['username']}), self.users[1])
        self._assert_grid_row(self.students_page.student_grid.get_row({'Username': self.users[2]['username']}), self.users[2], expected_status='Unregister Invitation')

        # Check unregistered user can not access to course about
        self._assert_access_course_about(self.users[0], False)


@attr('shard_ga_biz_2')
@flaky
class BizStudentRegisterWithDisableRegisterStudentSelfTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):
    """
    Tests that the student register functionality with register type disable register student self of biz works
    """

    def setUp(self):
        super(BizStudentRegisterWithDisableRegisterStudentSelfTest, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # page
        self.dashboard_page = DashboardPage(self.browser)
        self.account_settings_page = AccountSettingsPage(self.browser)
        self.invitation_page = BizInvitationPage(self.browser)

        # Register organization
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', self.new_director)

        # Register contract
        new_course_key, new_course_name = self.install_course(PLAT_COMPANY_CODE)
        self.new_course_name = new_course_name
        new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], register_type='DRS', detail_info=[new_course_key])
        self.new_invitation_code = new_contract['Invitation Code']
        self.invitation_confirm_page = BizInvitationConfirmPage(self.browser, self.new_invitation_code)

        # Test user
        self.existing_users = [self.register_user() for _ in range(3)]
        self.new_users = [self.new_user_info for _ in range(3)]

    def test_register_students_checked_register_status(self):
        """
        Case, registered users and new users with checked register status
        """
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students().click_tab_one_register_student()

        students = [
            self.existing_users[0], self.existing_users[1], self.new_users[0], self.new_users[1]
        ]
        for student in students:
            biz_register_students_page.input_one_user_info(student).click_one_register_button().click_popup_yes()

            biz_register_students_page.wait_for_message(
                u'Began the processing of Student Member Register.Execution status, please check from the task history.'
            )
            # Show task history
            biz_register_students_page.click_show_history()

            self._assert_register_student_task_history(
                biz_register_students_page.task_history_grid_row,
                1, 1, 0, 0,
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

        # Login existing user
        self.switch_to_user(self.existing_users[0])
        self.dashboard_page.visit()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.dashboard_page.show_settings(self.new_course_name)
        self.assertFalse(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        self.switch_to_user(self.existing_users[1])
        self.dashboard_page.visit()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertFalse(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        # Login new user
        self.switch_to_user(self.new_users[0])
        self.dashboard_page.visit()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertFalse(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        self.switch_to_user(self.new_users[1])
        self.dashboard_page.visit()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertFalse(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

    def test_register_students_nochecked_register_status(self):
        """
        Case, registered users and new users without checked register status
        """
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students().click_tab_one_register_student()
        # Change register status
        biz_register_students_page.click_one_register_status()

        students = [
            self.existing_users[0], self.existing_users[1], self.new_users[0], self.new_users[1]
        ]
        for student in students:
            biz_register_students_page.input_one_user_info(student).click_one_register_button().click_popup_yes()

            biz_register_students_page.wait_for_message(
                u'Began the processing of Student Member Register.Execution status, please check from the task history.'
            )

            # Show task history
            biz_register_students_page.click_show_history()

            self._assert_register_student_task_history(
                biz_register_students_page.task_history_grid_row,
                1, 1, 0, 0,
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

        # Login existing user
        self.switch_to_user(self.existing_users[0])
        self.dashboard_page.visit()
        self.assertNotIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self._assert_cannot_register_invitation_code()

        self.switch_to_user(self.existing_users[1])
        self.dashboard_page.visit()
        self.assertNotIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self._assert_cannot_register_invitation_code()

        # Login new user
        self.switch_to_user(self.new_users[0])
        self.dashboard_page.visit()
        self.assertNotIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self._assert_cannot_register_invitation_code()

        self.switch_to_user(self.new_users[1])
        self.dashboard_page.visit()
        self.assertNotIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self._assert_cannot_register_invitation_code()


@attr('shard_ga_biz_1')
@flaky
class BizStudentRegisterWithContractAuthAndDisableRegisterStudentSelfTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):
    """
    Tests that the student register functionality with contract auth of biz works
    """

    def setUp(self):
        super(BizStudentRegisterWithContractAuthAndDisableRegisterStudentSelfTest, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # url code
        self.new_url_code = get_random_string(8)

        # page
        self.dashboard_page = DashboardPage(self.browser)
        self.biz_login_page = BizLoginPage(self.browser, self.new_url_code)
        self.account_settings_page = AccountSettingsPage(self.browser)
        self.invitation_page = BizInvitationPage(self.browser)

        # Register organization
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', self.new_director)

        # Register contract
        new_course_key, new_course_name = self.install_course(PLAT_COMPANY_CODE)
        self.new_course_name = new_course_name
        new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], register_type='DRS', detail_info=[new_course_key])
        self.new_invitation_code = new_contract['Invitation Code']
        self.invitation_confirm_page = BizInvitationConfirmPage(self.browser, self.new_invitation_code)

        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = DjangoAdminPage(self.browser).visit().click_add('ga_contract', 'contractauth')
        django_admin_list_page = django_admin_add_page.input({
            'contract': new_contract['Contract Name'],
            'url_code': self.new_url_code,
            'send_mail': False,
        }).save()

        # Test user
        self.existing_users = [self.register_user() for _ in range(3)]
        self.new_users = [self.new_user_info for _ in range(3)]

    def test_register_students_checked_register_status(self):
        """
        Case, registered users and new users with checked register status
        """
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students().click_tab_one_register_student()

        students = [
            self.existing_users[0], self.existing_users[1], self.new_users[0], self.new_users[1]
        ]
        for student in students:
            biz_register_students_page.input_one_user_info_auth(student).click_one_register_button().click_popup_yes()

            biz_register_students_page.wait_for_message(
                u'Began the processing of Student Member Register.Execution status, please check from the task history.'
            )

            # Show task history
            biz_register_students_page.click_show_history()

            self._assert_register_student_task_history(
                biz_register_students_page.task_history_grid_row,
                1, 1, 0, 0,
                self.new_director,
            )
            self.assertEqual(
                [u'No messages.'],
                biz_register_students_page.task_messages,
            )

        self._assert_no_send_email(self.existing_users[0])
        self._assert_no_send_email(self.existing_users[1])
        self._assert_no_send_email(self.new_users[0])
        self._assert_no_send_email(self.new_users[1])

        # Login existing user
        self.logout()
        self.biz_login_page.visit().input(self.existing_users[0]['username'], self.existing_users[0]['password']).click_login()
        self.dashboard_page.wait_for_page()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertFalse(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        self.logout()
        self.biz_login_page.visit().input(self.existing_users[1]['username'], self.existing_users[1]['password']).click_login()
        self.dashboard_page.wait_for_page()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertFalse(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        # Login new user
        self.logout()
        self.biz_login_page.visit().input(self.new_users[0]['username'], self.new_users[0]['password']).click_login()
        self.dashboard_page.wait_for_page()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertFalse(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

        self.logout()
        self.biz_login_page.visit().input(self.new_users[1]['username'], self.new_users[1]['password']).click_login()
        self.dashboard_page.wait_for_page()
        self.assertIn(self.new_course_name, self.dashboard_page.current_courses_text)
        self.assertFalse(self.dashboard_page.is_enable_unenroll(self.new_course_name))
        self._assert_can_register_invitation_code()

    def test_register_students_nochecked_register_status(self):
        """
        Case, registered users and new users without checked register status
        """
        # Go to register
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().click_register_students().click_tab_one_register_student()
        # Change register status
        biz_register_students_page.click_one_register_status()

        students = [
            self.existing_users[0], self.existing_users[1], self.new_users[0], self.new_users[1]
        ]
        for student in students:
            biz_register_students_page.input_one_user_info_auth(student).click_one_register_button().click_popup_yes()

            biz_register_students_page.wait_for_message(
                u'Began the processing of Student Member Register.Execution status, please check from the task history.'
            )

            # Show task history
            biz_register_students_page.click_show_history()

            self._assert_register_student_task_history(
                biz_register_students_page.task_history_grid_row,
                1, 1, 0, 0,
                self.new_director,
            )
            self.assertEqual(
                [u'No messages.'],
                biz_register_students_page.task_messages,
            )

        self._assert_no_send_email(self.existing_users[0])
        self._assert_no_send_email(self.existing_users[1])
        self._assert_no_send_email(self.new_users[0])
        self._assert_no_send_email(self.new_users[1])

        # Login existing user
        self.logout()
        self.biz_login_page.visit().input(self.existing_users[0]['username'], self.existing_users[0]['password']).click_login()
        self.assertEqual([
            u'Please ask your administrator to register the invitation code.'
        ], self.biz_login_page.error_messages)

        self.logout()
        self.biz_login_page.visit().input(self.existing_users[1]['username'], self.existing_users[1]['password']).click_login()
        self.assertEqual([
            u'Please ask your administrator to register the invitation code.'
        ], self.biz_login_page.error_messages)

        # Login new user
        self.logout()
        self.biz_login_page.visit().input(self.new_users[0]['username'], self.new_users[0]['password']).click_login()
        self.assertEqual([
            u'Please ask your administrator to register the invitation code.'
        ], self.biz_login_page.error_messages)

        self.logout()
        self.biz_login_page.visit().input(self.new_users[1]['username'], self.new_users[1]['password']).click_login()
        self.assertEqual([
            u'Please ask your administrator to register the invitation code.'
        ], self.biz_login_page.error_messages)


@attr('shard_ga_biz_2')
class BizMailTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):
    """
    Tests that the mail functionality of biz works
    """

    def setUp(self):
        super(BizMailTest, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # page
        self.django_admin_page = DjangoAdminPage(self.browser)

        # Register organization
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', self.new_director)

        # Register contract
        new_course_key, new_course_name = self.install_course(PLAT_COMPANY_CODE)
        self.new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], detail_info=[new_course_key])

        # Test user
        self.new_user = self.new_user_info

    def test_normal(self):
        # Can not customize
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertFalse('Welcome E-Mail Management' in nav.left_menu_items.keys())

        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractoption')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'customize_mail': True,
        }).save()

        # Can customize
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertTrue('Welcome E-Mail Management' in nav.left_menu_items.keys())

        # Mail Management
        mail_page = nav.click_mail_management()
        self.assertEqual([u'username', u'password', u'email_address'], mail_page.parameter_keys)
        self.assertEqual(u'オンライン学習「gacco」の受講予定者の方へ', mail_page.subject)
        self.assertEqual(u'{email_address} の所有者の方へ Default Body For New User', mail_page.body)

        mail_page.input('Test Subject {username}', 'Test Body {email_address} PW:{password}').click_save_template().click_popup_yes()
        mail_page.wait_for_ajax()
        self.assertEqual([u'Successfully to save the template e-mail.'], mail_page.messages)

        mail_page.click_send_test_mail().click_popup_yes()
        mail_page.wait_for_ajax()
        self.assertEqual([u'Successfully to send the test e-mail.'], mail_page.messages)

        test_mail = self._get_message(self.new_director['email'])
        self.assertIsNotNone(test_mail)
        self.assertEqual(u'Test Subject {}'.format(self.new_director['username']), test_mail['subject'])
        self.assertEqual(u'Test Body {} PW:dummyPassword'.format(self.new_director['email']), test_mail['body'].decode('utf-8'))
        self.email_client.clear_messages()

        # Register
        register_page = nav.click_register_students().click_tab_one_register_student()
        register_page.input_one_user_info(self.new_user).click_one_register_button().click_popup_yes()

        register_page.wait_for_message(
            u'Began the processing of Student Member Register.Execution status, please check from the task history.'
        )

        register_page.click_show_history()

        self._assert_register_student_task_history(
            register_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            register_page.task_messages,
        )
        register_mail = self._get_message(self.new_user['email'])
        self.assertIsNotNone(register_mail)
        self.assertEqual(u'Test Subject {}'.format(self.new_user['username']), register_mail['subject'])
        self.assertIn(u'Test Body {} PW:'.format(self.new_user['email']), register_mail['body'].decode('utf-8'))

    def test_auth(self):
        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = DjangoAdminPage(self.browser).visit().click_add('ga_contract', 'contractauth')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'url_code': get_random_string(8),
            'send_mail': True,
        }).save()

        # Can not customize
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertFalse('Welcome E-Mail Management' in nav.left_menu_items.keys())

        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractoption')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'customize_mail': True,
        }).save()

        # Can customize
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertTrue('Welcome E-Mail Management' in nav.left_menu_items.keys())

        # Mail Management
        mail_page = nav.click_mail_management()
        self.assertEqual([u'username', u'password', u'email_address', u'logincode', u'urlcode'], mail_page.parameter_keys)
        self.assertEqual(u'オンライン学習「gacco」の受講予定者の方へ', mail_page.subject)
        self.assertEqual(u'{email_address} の所有者の方へ Default Body Send Registration Mail for New User', mail_page.body)

        mail_page.input('Test Subject {username}', 'Test Body {email_address} PW:{password}').click_save_template().click_popup_yes()
        mail_page.wait_for_ajax()
        self.assertEqual([u'Successfully to save the template e-mail.'], mail_page.messages)

        mail_page.click_send_test_mail().click_popup_yes()
        mail_page.wait_for_ajax()
        self.assertEqual([u'Successfully to send the test e-mail.'], mail_page.messages)

        test_mail = self._get_message(self.new_director['email'])
        self.assertIsNotNone(test_mail)
        self.assertEqual(u'Test Subject {}'.format(self.new_director['username']), test_mail['subject'])
        self.assertEqual(u'Test Body {} PW:dummyPassword'.format(self.new_director['email']), test_mail['body'].decode('utf-8'))
        self.email_client.clear_messages()

        # Register
        register_page = nav.click_register_students().click_tab_one_register_student()
        register_page.input_one_user_info_auth(self.new_user).click_one_register_button().click_popup_yes()

        register_page.wait_for_message(
            u'Began the processing of Student Member Register.Execution status, please check from the task history.'
        )

        register_page.click_show_history()

        self._assert_register_student_task_history(
            register_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            register_page.task_messages,
        )
        register_mail = self._get_message(self.new_user['email'])
        self.assertIsNotNone(register_mail)
        self.assertEqual(u'Test Subject {}'.format(self.new_user['username']), register_mail['subject'])
        self.assertIn(u'Test Body {} PW:'.format(self.new_user['email']), register_mail['body'].decode('utf-8'))

    def test_auth_no_send(self):
        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = DjangoAdminPage(self.browser).visit().click_add('ga_contract', 'contractauth')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'url_code': get_random_string(8),
            'send_mail': False,
        }).save()

        # Can not customize
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertFalse('Welcome E-Mail Management' in nav.left_menu_items.keys())

        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractoption')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'customize_mail': True,
        }).save()

        # Can customize
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertFalse('Welcome E-Mail Management' in nav.left_menu_items.keys())

    @skip("This won't work with mod #1906")
    def test_normal_existing_user(self):
        # Can not customize
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertFalse('Welcome E-Mail Management' in nav.left_menu_items.keys())

        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractoption')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'customize_mail': True,
        }).save()

        # Can customize
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertTrue('Welcome E-Mail Management' in nav.left_menu_items.keys())

        # Mail Management
        mail_page = nav.click_mail_management().click_tab_for_existing_user()
        self.assertEqual([u'username', u'email_address'], mail_page.parameter_keys)
        self.assertEqual(u'オンライン学習「gacco」の受講予定者の方へ', mail_page.subject)
        self.assertEqual(u'{username}様 Default Body For Existing User', mail_page.body)

        mail_page.input('Existing Test Subject {username}', 'Existing Test Body {email_address} PW:{password}').click_save_template().click_popup_yes()
        mail_page.wait_for_ajax()
        self.assertEqual([u'Successfully to save the template e-mail.'], mail_page.messages)

        mail_page.click_send_test_mail().click_popup_yes()
        mail_page.wait_for_ajax()
        self.assertEqual([u'Successfully to send the test e-mail.'], mail_page.messages)

        test_mail = self._get_message(self.new_director['email'])
        self.assertIsNotNone(test_mail)
        self.assertEqual(u'Existing Test Subject {}'.format(self.new_director['username']), test_mail['subject'])
        self.assertEqual(u'Existing Test Body {} PW:{{password}}'.format(self.new_director['email']), test_mail['body'].decode('utf-8'))
        self.email_client.clear_messages()

        # Register
        register_page = nav.click_register_students().click_tab_one_register_student()
        register_page.input_one_user_info(self.new_user).click_one_register_button().click_popup_yes()

        register_page.wait_for_message(
            u'Began the processing of Student Member Register.Execution status, please check from the task history.'
        )

        register_page.click_show_history()

        self._assert_register_student_task_history(
            register_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            register_page.task_messages,
        )
        register_mail = self._get_message(self.new_user['email'])
        self.assertIsNotNone(register_mail)
        self.assertEqual(u'Existing Test Subject {}'.format(self.new_user['username']), register_mail['subject'])
        self.assertEqual(u'Existing Test Body {} PW:{{password}}'.format(self.new_user['email']), register_mail['body'].decode('utf-8'))

    @skip("This won't work with mod #1906")
    def test_auth_existing_user(self):
        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = DjangoAdminPage(self.browser).visit().click_add('ga_contract', 'contractauth')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'url_code': get_random_string(8),
            'send_mail': True,
        }).save()

        # Can not customize
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertFalse('Welcome E-Mail Management' in nav.left_menu_items.keys())

        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractoption')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'customize_mail': True,
        }).save()

        # Can customize
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertTrue('Welcome E-Mail Management' in nav.left_menu_items.keys())

        # Mail Management
        mail_page = nav.click_mail_management().click_tab_for_existing_user_login_code()
        self.assertEqual([u'username', u'email_address', u'logincode', u'urlcode'], mail_page.parameter_keys)
        self.assertEqual(u'オンライン学習「gacco」の受講予定者の方へ', mail_page.subject)
        self.assertEqual(u'{username}様 Default Body Send Registration Mail for Existing User', mail_page.body)

        mail_page.input('Existing Test Subject {username}', 'Existing Test Body {email_address} PW:{password}').click_save_template().click_popup_yes()
        mail_page.wait_for_ajax()
        self.assertEqual([u'Successfully to save the template e-mail.'], mail_page.messages)

        mail_page.click_send_test_mail().click_popup_yes()
        mail_page.wait_for_ajax()
        self.assertEqual([u'Successfully to send the test e-mail.'], mail_page.messages)

        test_mail = self._get_message(self.new_director['email'])
        self.assertIsNotNone(test_mail)
        self.assertEqual(u'Existing Test Subject {}'.format(self.new_director['username']), test_mail['subject'])
        self.assertEqual(u'Existing Test Body {} PW:{{password}}'.format(self.new_director['email']), test_mail['body'].decode('utf-8'))
        self.email_client.clear_messages()

        # Register
        register_page = nav.click_register_students().click_tab_one_register_student()
        register_page.input_one_user_info_auth(self.new_user).click_one_register_button().click_popup_yes()

        register_page.wait_for_message(
            u'Began the processing of Student Member Register.Execution status, please check from the task history.'
        )

        register_page.click_show_history()

        self._assert_register_student_task_history(
            register_page.task_history_grid_row,
            1, 1, 0, 0,
            self.new_director,
        )
        self.assertEqual(
            [u'No messages.'],
            register_page.task_messages,
        )
        register_mail = self._get_message(self.new_user['email'])
        self.assertIsNotNone(register_mail)
        self.assertEqual(u'Existing Test Subject {}'.format(self.new_user['username']), register_mail['subject'])
        self.assertEqual(u'Existing Test Body {} PW:{{password}}'.format(self.new_user['email']), register_mail['body'].decode('utf-8'))


@attr('shard_ga_biz_3')
class BizReminderMailTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):
    """
    Tests that the reminder mail functionality of biz works
    """

    def setUp(self):
        super(BizReminderMailTest, self).setUp()

        # setup mail client
        self.setup_email_client(EMAIL_FILE_PATH)

        # page
        self.django_admin_page = DjangoAdminPage(self.browser)
        self.account_settings_page = AccountSettingsPage(self.browser)

        # Register organization
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.new_director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'director', self.new_director)
        self.fullname = get_random_string(12)

        # Register contract
        new_course_key, new_course_name = self.install_course(PLAT_COMPANY_CODE)
        self.new_contract = self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], detail_info=[new_course_key])

        # Test user
        self.new_user = self.new_user_info

    @skip("Modified by JAST later")
    def test_submission_reminder_mail_setting(self):
        # Can not send submission reminder
        self.switch_to_user(self.new_director)
        nav = BizNavPage(self.browser).visit()

        self.assertFalse('Reminder Mail Setting' in nav.left_menu_items.keys())

        # Make contract auth
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractoption')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.new_contract['Contract Name'],
            'send_submission_reminder': True,
        }).save()

        # Update fullname
        self.switch_to_user(self.new_director)
        self.account_settings_page.visit().wait_for_ajax()
        self.account_settings_page.update_full_name(self.fullname)

        # Can send submission reminder
        nav = BizNavPage(self.browser).visit()

        self.assertTrue('Reminder Mail Setting' in nav.left_menu_items.keys())

        # Reminder Mail Setting
        reminder_mail_page = nav.click_reminder_mail_setting()
        self.assertEqual([u'username', u'fullname'], reminder_mail_page.parameter_keys)
        self.assertEqual('3', reminder_mail_page.reminder_email_days)
        self.assertEqual(u'■gacco 未提出課題のお知らせ', reminder_mail_page.subject)
        self.assertEqual(u'Default Body For Submission Reminder Mail', reminder_mail_page.body)
        self.assertEqual(u'Default Body2 For Submission Reminder Mail', reminder_mail_page.body2)

        reminder_mail_page.input('5',
                                 'Test Subject {username}, {fullname}',
                                 'Test Body {username}, {fullname}',
                                 'Test Body2').click_save_template().click_popup_yes()
        reminder_mail_page.wait_for_ajax()
        self.assertEqual([u'Successfully to save the template e-mail.'], reminder_mail_page.messages)

        reminder_mail_page.click_send_test_mail().click_popup_yes()
        reminder_mail_page.wait_for_ajax()
        self.assertEqual([u'Successfully to send the test e-mail.'], reminder_mail_page.messages)

        test_mail = self._get_message(self.new_director['email'])
        self.assertIsNotNone(test_mail)
        self.assertEqual(
            u'Test Subject {}, {}'.format(self.new_director['username'], self.fullname),
            test_mail['subject'].decode('utf-8'))
        self.assertIn(
            u'Test Body {}, {}'.format(self.new_director['username'], self.fullname),
            test_mail['body'].decode('utf-8'))
        self.assertIn(u'Test Body2', test_mail['body'].decode('utf-8'))
        self.email_client.clear_messages()

# -*- coding: utf-8 -*-
"""
    End-to-end tests for contract operation additional info of biz feature
"""
from bok_choy.web_app_test import WebAppTest
from datetime import datetime
from nose.plugins.attrib import attr

from django.utils.crypto import get_random_string

from . import GaccoBizTestMixin, PLAT_COMPANY_CODE, PLATFORMER_USER_INFO
from .test_ga_contract_operation import BizStudentRegisterMixin
from ...pages.biz.ga_navigation import BizNavPage


@attr('shard_ga_biz_1')
class BizAdditionalInfoTest(WebAppTest, GaccoBizTestMixin):

    def setUp(self):
        super(BizAdditionalInfoTest, self).setUp()

        # Register organization
        self.org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, self.org_info['Organization Name'], 'director', self.director)

        # Register contract
        course_key, course_name = self.install_course(PLAT_COMPANY_CODE)
        self.course_name = course_name
        self.course_key = course_key
        self.contract = self.register_contract(PLATFORMER_USER_INFO,
                                               self.org_info['Organization Name'],
                                               detail_info=[self.course_key])

    def test_success(self):
        self.switch_to_user(self.director)
        nav = BizNavPage(self.browser).visit()
        nav.change_manage_target(self.org_info['Organization Name'], self.contract['Contract Name'], self.course_key)

        # Go to additional info page
        self.register_students_page = nav.click_register_students()
        self.additional_info_page = self.register_students_page.click_tab_additional_info()

        # Check error message
        self.additional_info_page.click_additional_info_register_button()
        self.assertEqual(
            u"Please enter the name of item you wish to add.",
            self.additional_info_page.error_messages[0],
        )

        # Register additional info
        additional_input_value1 = get_random_string(10)
        self.additional_info_page.input_additional_info_register(additional_input_value1)
        self.additional_info_page.click_additional_info_register_button()
        self.assertEqual(
            u"New item has been registered.",
            self.additional_info_page.messages[0],
        )

        additional_input_value2 = get_random_string(10)
        self.additional_info_page.input_additional_info_register(additional_input_value2)
        self.additional_info_page.click_additional_info_register_button()
        self.assertEqual(
            u"New item has been registered.",
            self.additional_info_page.messages[0],
        )

        # Check additional info value
        self.assertEqual(
            [additional_input_value1],
            self.additional_info_page.get_display_name_values(0),
        )
        self.assertEqual(
            [additional_input_value2],
            self.additional_info_page.get_display_name_values(1),
        )

        # Edit additional info
        # Check error message
        self.additional_info_page.edit_additional_info_value('')
        self.assertEqual(
            u"Please enter the name of item you wish to add.",
            self.additional_info_page.error_messages[0],
        )

        additional_input_value3 = get_random_string(10)
        self.additional_info_page.edit_additional_info_value(additional_input_value3)
        self.assertEqual(
            u"New item has been updated.",
            self.additional_info_page.messages[0],
        )

        # Check additional info value
        self.assertEqual(
            [additional_input_value3],
            self.additional_info_page.get_display_name_values(0),
        )
        self.assertEqual(
            [additional_input_value2],
            self.additional_info_page.get_display_name_values(1),
        )

        # Delete additional info
        self.additional_info_page.click_additional_info_delete_button().click_popup_yes()
        self.assertEqual(
            u"New item has been deleted.",
            self.additional_info_page.messages[0],
        )

        # Check additional info value
        self.assertEqual(
            [additional_input_value2],
            self.additional_info_page.get_display_name_values(0),
        )


@attr('shard_ga_biz_1')
class BizBulkAdditionalInfoRegisterTest(WebAppTest, GaccoBizTestMixin, BizStudentRegisterMixin):

    def setUp(self):
        super(BizBulkAdditionalInfoRegisterTest, self).setUp()

        # Register organization
        self.org_info = self.register_organization(PLATFORMER_USER_INFO)

        # Register user as director
        self.director = self.register_user()
        self.grant(PLATFORMER_USER_INFO, self.org_info['Organization Name'], 'director', self.director)

        # Register contract
        course_key, course_name = self.install_course(PLAT_COMPANY_CODE)
        self.course_name = course_name
        self.course_key = course_key
        self.contract = self.register_contract(PLATFORMER_USER_INFO,
                                               self.org_info['Organization Name'],
                                               detail_info=[self.course_key])

        # Register users
        self.new_users = [self.register_user() for _ in range(3)]

    @staticmethod
    def _make_additional_info_csv(email, add_info_x, add_info_y):
        return u'{},{},{}\r\n'.format(email, add_info_x, add_info_y)

    def _assert_additional_info_update_task_history(self, grid_row, total, success, skipped, failed, user_info):
        self.assertEqual(u"Additional Item Update", grid_row['Task Type'])
        self.assertEqual(u"Complete", grid_row['State'])
        self.assertEqual(u"Total: {}, Success: {}, Skipped: {}, Failed: {}".format(
            total, success, skipped, failed), grid_row['Execution Result'])
        self.assertEqual(user_info['username'], grid_row['Execution Username'])
        self.assertIsNotNone(datetime.strptime(grid_row['Execution Datetime'], '%Y/%m/%d %H:%M:%S'))

    def test_success(self):
        self.switch_to_user(self.director)
        nav = BizNavPage(self.browser).visit()
        nav.change_manage_target(self.org_info['Organization Name'], self.contract['Contract Name'], self.course_key)

        # Register students
        register_students_page = nav.click_register_students().click_tab_one_register_student()
        register_students_page.input_one_user_info(self.new_users[0]).click_one_register_button().click_popup_yes()
        register_students_page.input_one_user_info(self.new_users[1]).click_one_register_button().click_popup_yes()
        register_students_page.input_one_user_info(self.new_users[2]).click_one_register_button().click_popup_yes()

        # Add additional info
        additional_info_page = nav.click_register_students().click_tab_additional_info()
        additional_input_x = get_random_string(10)
        additional_info_page.input_additional_info_register(additional_input_x)
        additional_info_page.click_additional_info_register_button()
        additional_input_y = get_random_string(10)
        additional_info_page.input_additional_info_register(additional_input_y)
        additional_info_page.click_additional_info_register_button()

        # Go to update additional info page
        update_additional_info_page = register_students_page.click_tab_update_additional_info()
        self.assertIn(
            u"{}: 255 characters or less.".format(additional_input_x),
            update_additional_info_page.get_additional_infos(),
        )
        self.assertIn(
            u"{}: 255 characters or less.".format(additional_input_y),
            update_additional_info_page.get_additional_infos(),
        )

        # Check error message
        update_additional_info_page.click_additional_info_update_button()
        self.assertEqual(
            u"Could not find student list.",
            update_additional_info_page.error_messages[0],
        )

        # Update additional info
        additional_input_x_user1 = get_random_string(10)
        additional_input_y_user1 = get_random_string(10)
        additional_input_x_user2 = get_random_string(10)
        additional_input_y_user2 = get_random_string(10)
        additional_input_x_user3 = get_random_string(10)
        additional_input_y_user3 = get_random_string(10)
        csv_list = self._make_additional_info_csv(self.new_users[0]['email'],
                                                  additional_input_x_user1,
                                                  additional_input_y_user1)
        csv_list += self._make_additional_info_csv(self.new_users[1]['email'],
                                                   additional_input_x_user2,
                                                   additional_input_y_user2)
        csv_list += self._make_additional_info_csv(self.new_users[2]['email'],
                                                   additional_input_x_user3,
                                                   additional_input_y_user3)
        update_additional_info_page.input_additional_info_list(csv_list)
        update_additional_info_page.click_additional_info_update_button().click_popup_yes()

        # Check message
        self.assertEqual(
            u"Began the processing of Additional Item Update.Execution status, please check from the task history.",
            update_additional_info_page.messages[0],
        )

        # Check task history
        update_additional_info_page.click_task_reload_button()
        self._assert_additional_info_update_task_history(
            update_additional_info_page.task_history_grid_row,
            3, 3, 0, 0,
            self.director,
        )
        self.assertEqual(
            [u"No messages."],
            update_additional_info_page.task_messages,
        )

    def test_no_additional_item(self):
        self.switch_to_user(self.director)
        nav = BizNavPage(self.browser).visit()
        nav.change_manage_target(self.org_info['Organization Name'], self.contract['Contract Name'], self.course_key)

        # Register students
        register_students_page = nav.click_register_students().click_tab_one_register_student()
        register_students_page.input_one_user_info(self.new_users[0]).click_one_register_button().click_popup_yes()

        # Update additional info
        update_additional_info_page = nav.click_register_students().click_tab_update_additional_info()
        additional_input_x_user1 = get_random_string(10)
        additional_input_y_user1 = get_random_string(10)
        csv_list = self._make_additional_info_csv(self.new_users[0]['email'],
                                                  additional_input_x_user1,
                                                  additional_input_y_user1)

        update_additional_info_page.input_additional_info_list(csv_list)
        update_additional_info_page.click_additional_info_update_button().click_popup_yes()

        # Confirm error message
        self.assertEqual(
            u"No additional item registered.",
            update_additional_info_page.error_messages[0]
        )

    def test_errors_user(self):
        self.switch_to_user(self.director)
        nav = BizNavPage(self.browser).visit()
        nav.change_manage_target(self.org_info['Organization Name'], self.contract['Contract Name'], self.course_key)

        # Register students
        register_students_page = nav.click_register_students().click_tab_one_register_student()
        register_students_page.input_one_user_info(self.new_users[0]).click_one_register_button().click_popup_yes()

        # Add additional info
        additional_info_page = nav.click_register_students().click_tab_additional_info()
        additional_input_x = get_random_string(10)
        additional_info_page.input_additional_info_register(additional_input_x)
        additional_info_page.click_additional_info_register_button()
        additional_input_y = get_random_string(10)
        additional_info_page.input_additional_info_register(additional_input_y)
        additional_info_page.click_additional_info_register_button()

        # Update additional info
        update_additional_info_page = nav.click_register_students().click_tab_update_additional_info()
        additional_input_x_user1 = get_random_string(10)
        additional_input_y_user1 = get_random_string(10)

        # Note:
        # Line1 : success
        # Line2 : user does not exists
        # Line3 : user not registered in contract
        csv_list = self._make_additional_info_csv(self.new_users[0]['email'],
                                                  additional_input_x_user1,
                                                  additional_input_y_user1)
        email = 'test_user_does_not_exist@gacco.org'
        csv_list += self._make_additional_info_csv(email,
                                                   additional_input_x_user1,
                                                   additional_input_y_user1)
        csv_list += self._make_additional_info_csv(self.new_users[1]['email'],
                                                   additional_input_x_user1,
                                                   additional_input_y_user1)

        update_additional_info_page.input_additional_info_list(csv_list)
        update_additional_info_page.click_additional_info_update_button().click_popup_yes()

        # Confirm message
        self.assertEqual(
            u"Began the processing of Additional Item Update.Execution status, please check from the task history.",
            update_additional_info_page.messages[0]
        )

        # Check task history
        update_additional_info_page.click_task_reload_button()
        self._assert_additional_info_update_task_history(
            update_additional_info_page.task_history_grid_row,
            3, 1, 0, 2,
            self.director
        )
        self.assertEqual(
            [
                u"Line 2:The user does not exist. ({})".format(email),
                u"Line 3:Could not find target user.",
            ],
            update_additional_info_page.task_messages
        )

    def test_errors_other(self):
        self.switch_to_user(self.director)
        nav = BizNavPage(self.browser).visit()
        nav.change_manage_target(self.org_info['Organization Name'], self.contract['Contract Name'], self.course_key)

        # Register students
        register_students_page = nav.click_register_students().click_tab_one_register_student()
        register_students_page.input_one_user_info(self.new_users[0]).click_one_register_button().click_popup_yes()
        register_students_page.input_one_user_info(self.new_users[1]).click_one_register_button().click_popup_yes()
        register_students_page.input_one_user_info(self.new_users[2]).click_one_register_button().click_popup_yes()

        # Add additional info
        additional_info_page = nav.click_register_students().click_tab_additional_info()
        additional_input_x = get_random_string(10)
        additional_info_page.input_additional_info_register(additional_input_x)
        additional_info_page.click_additional_info_register_button()
        additional_input_y = get_random_string(10)
        additional_info_page.input_additional_info_register(additional_input_y)
        additional_info_page.click_additional_info_register_button()

        # Update additional info
        update_additional_info_page = nav.click_register_students().click_tab_update_additional_info()
        additional_input_x_user1 = get_random_string(10)
        additional_input_y_user1 = get_random_string(10)

        # Note:
        # Line1 : success
        # Line2 : Too many columns
        # Line3 : Input blank line
        # Line4 : Over max character
        csv_list = self._make_additional_info_csv(self.new_users[0]['email'],
                                                  additional_input_x_user1,
                                                  additional_input_y_user1)
        csv_list += self._make_additional_info_csv(self.new_users[1]['email'],
                                                   additional_input_x_user1,
                                                   ',')
        csv_list += u'\r\n'
        csv_list += self._make_additional_info_csv(self.new_users[2]['email'],
                                                   additional_input_x_user1,
                                                   get_random_string(256))

        update_additional_info_page.input_additional_info_list(csv_list)
        update_additional_info_page.click_additional_info_update_button().click_popup_yes()

        # Confirm message
        self.assertEqual(
            u"Began the processing of Additional Item Update.Execution status, please check from the task history.",
            update_additional_info_page.messages[0]
        )

        # Check task history
        update_additional_info_page.click_task_reload_button()
        self._assert_additional_info_update_task_history(
            update_additional_info_page.task_history_grid_row,
            4, 1, 1, 2,
            self.director
        )
        self.assertEqual(
            [
                u"Line 2:Number of [emails] and [new items] must be the same.",
                u"Line 4:Please enter the name of item within 255 characters.",
            ],
            update_additional_info_page.task_messages
        )

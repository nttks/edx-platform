# -*- coding: utf-8 -*-
"""
    End-to-end tests for contract operation of biz a limited bulk operation feature
"""

from nose.plugins.attrib import attr
from unittest import skip

from .test_ga_contract_operation import BizPersonalinfoMaskTestBase, BizStudentUnregisterTestBase


class BizStudentBulkManagementMixin(object):
    def _make_input_students(self, user_info_list):
        return '\r\n'.join([user_info['username'] for user_info in user_info_list])


@attr('shard_ga_biz_3')
class BizBulkPersonalinfoMaskTest(BizPersonalinfoMaskTestBase, BizStudentBulkManagementMixin):

    @skip("Modified by JAST later")
    def test_success(self):
        # Check that can login
        for user in self.users:
            self._assert_login(user)

        self.switch_to_user(self.new_director)
        self.bulk_students_page.visit()

        # Check error message when target is not selected.
        self.bulk_students_page.input_students('')
        self.bulk_students_page.click_bulk_personalinfo_mask_button()
        self.assertEqual(['Could not find student list.'], self.bulk_students_page.messages)

        # Input student list and execute
        csv_content = self._make_input_students([
            self.users[0],
            self.users[2],
        ])
        self.bulk_students_page.input_students(csv_content)
        self.bulk_students_page.click_bulk_personalinfo_mask_button().click_popup_yes()
        self.students_page.wait_for_ajax()

        self.assertEqual(
            ['Began the processing of Personal Information Mask.Execution status, please check from the task history.'],
            self.bulk_students_page.messages
        )

        # Check task histories
        self.bulk_students_page.wait_for_task_complete()
        self._assert_personalinfo_mask_task_history(
            self.bulk_students_page.task_history_grid_row,
            self.new_director['username'], 2, 2, 0, 0
        )

        # go to students list and check
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


@attr('shard_ga_biz_3')
class BizStudentUnregisterTest(BizStudentUnregisterTestBase, BizStudentBulkManagementMixin):

    @skip("Modified by JAST later")
    def test_success(self):
        # Check registered user can access to course about
        self._assert_access_course_about(self.users[0])

        self.switch_to_user(self.new_director)
        self.bulk_students_page.visit()

        # Check error message when target is not selected.
        self.bulk_students_page.input_students('')
        self.bulk_students_page.click_bulk_unregister_button()
        self.assertEqual(['Could not find student list.'], self.bulk_students_page.messages)

        # Input student list and execute
        csv_content = self._make_input_students([
            self.users[0],
            self.users[2],
        ])
        self.bulk_students_page.input_students(csv_content)
        self.bulk_students_page.click_bulk_unregister_button().click_popup_yes()
        self.bulk_students_page.wait_for_ajax()

        self.assertEqual(
            ['Began the processing of Student Unregister.Execution status, please check from the task history.'],
            self.bulk_students_page.messages
        )

        # go to students list and check
        self.students_page.visit()
        # Check data rows after unregister
        self._assert_grid_row(self.students_page.student_grid.get_row({'Username': self.users[0]['username']}), self.users[0], expected_status='Unregister Invitation')
        self._assert_grid_row(self.students_page.student_grid.get_row({'Username': self.users[1]['username']}), self.users[1])
        self._assert_grid_row(self.students_page.student_grid.get_row({'Username': self.users[2]['username']}), self.users[2], expected_status='Unregister Invitation')

        # Check unregistered user can not access to course about
        self._assert_access_course_about(self.users[0], False)

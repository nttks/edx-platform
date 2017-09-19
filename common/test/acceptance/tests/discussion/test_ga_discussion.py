# -*- coding: utf-8 -*-
"""
End-to-end tests for discussion
"""
import bok_choy.browser

from ..helpers import UniqueCourseTest
from ...fixtures.course import CourseFixture
from ...pages.lms.auto_auth import AutoAuthPage

from ..ga_helpers import GaccoTestMixin, SUPER_USER_INFO
from ...pages.lms.ga_discussion import DiscussionTabHomePage
from ...pages.lms.ga_django_admin import DjangoAdminPage


class DiscussionPageTest(UniqueCourseTest, GaccoTestMixin):
    """
    Tests that the discussion page.
    """

    def _login_get_userid(self, user_info):
        auto_auth_page = AutoAuthPage(self.browser, username=user_info['username'], email=user_info['email']).visit()
        return auto_auth_page.get_user_id()

    def setUp(self):
        super(DiscussionPageTest, self).setUp()
        CourseFixture(**self.course_info).install()

    def test_not_present_input_upload_file(self):
        self.switch_to_user(SUPER_USER_INFO)

        DjangoAdminPage(self.browser).visit().click_add('ga_optional', 'courseoptionalconfiguration').input({
            'enabled': False,
            'key': 'disccusion-image-upload-settings',
            'course_key': self.course_id,
        }).save()

        AutoAuthPage(self.browser, course_id=self.course_id).visit()
        self.discussion_page = DiscussionTabHomePage(self.browser, self.course_id)
        self.discussion_page.visit()

        self.discussion_page.click_new_post_button()
        self.discussion_page.view_dialog_image_insert()
        bok_choy.browser.save_screenshot(self.browser, 'test_not_present_input_upload_file')
        self.assertFalse(self.discussion_page.view_dialog_image_insert().exists_input_file_on_dialog())

    def test_present_input_upload_file(self):
        self.switch_to_user(SUPER_USER_INFO)

        DjangoAdminPage(self.browser).visit().click_add('ga_optional', 'courseoptionalconfiguration').input({
            'enabled': True,
            'key': 'disccusion-image-upload-settings',
            'course_key': self.course_id,
        }).save()

        AutoAuthPage(self.browser, course_id=self.course_id).visit()
        self.discussion_page = DiscussionTabHomePage(self.browser, self.course_id)
        self.discussion_page.visit()

        self.discussion_page.click_new_post_button()
        self.discussion_page.view_dialog_image_insert()
        bok_choy.browser.save_screenshot(self.browser, 'test_present_input_upload_file')
        self.assertTrue(self.discussion_page.view_dialog_image_insert().exists_input_file_on_dialog())

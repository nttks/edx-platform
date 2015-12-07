# -*- coding: utf-8 -*-
"""
End-to-end tests for discussion
"""

from ..helpers import UniqueCourseTest
from ...fixtures.course import CourseFixture
from ...pages.lms.auto_auth import AutoAuthPage

from ..ga_helpers import GaccoTestMixin
from ...pages.lms.ga_discussion import DiscussionTabHomePage


class DiscussionPageTest(UniqueCourseTest, GaccoTestMixin):
    """
    Tests that the discussion page.
    """

    def setUp(self):
        super(DiscussionPageTest, self).setUp()
        CourseFixture(**self.course_info).install()
        AutoAuthPage(self.browser, course_id=self.course_id).visit()
        self.discussion_page = DiscussionTabHomePage(self.browser, self.course_id)
        self.discussion_page.visit()

    def test_not_present_input_upload_file(self):
        self.discussion_page.click_new_post_button()
        self.assertFalse(self.discussion_page.view_dialog_image_insert().exists_input_file_on_dialog())

"""
Acceptance tests for Studio's Course Name(Course display name) Length
"""
from ..ga_helpers import GaccoTestMixin

from .base_studio_test import StudioCourseTest

from ...pages.studio.ga_overview import CourseOutlinePage
from ...pages.studio.ga_users import CourseTeamPage


class CourseMenuTest(StudioCourseTest, GaccoTestMixin):

    def setUp(self):
        super(CourseMenuTest, self).setUp(is_staff=True)
        self.course_outline = CourseOutlinePage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )
        self.course_team = CourseTeamPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )

        self.course_admin = self.register_user()
        self.course_staff = self.register_user()

    def test_present_each_role(self):
        """
        Test course menu present each role.
        """
        # staff
        self.switch_to_user(self.user)
        self.course_team.visit().add_course_staff(self.course_staff['email']).add_course_admin(self.course_admin['email'])
        self.course_outline.visit()
        self.assertEqual([u'Course\nContent', u'Course\nSettings', u'Tools'], self.course_outline.course_menu)
        self.assertEqual([u'Outline', u'Updates', u'Pages', u'Files & Uploads', u'Textbooks'], self.course_outline.course_menu_item(0))
        self.assertEqual([u'Schedule & Details', u'Grading', u'Course Team', u'Group Configurations', u'Advanced Settings', u'Certificates'], self.course_outline.course_menu_item(1))
        self.assertEqual([u'Import', u'Export'], self.course_outline.course_menu_item(2))

        # course admin
        self.switch_to_user(self.course_admin)
        self.course_outline.visit()
        self.assertEqual([u'Course\nContent', u'Course\nSettings', u'Tools'], self.course_outline.course_menu)
        self.assertEqual([u'Outline', u'Updates', u'Pages', u'Files & Uploads', u'Textbooks'], self.course_outline.course_menu_item(0))
        self.assertEqual([u'Schedule & Details', u'Grading', u'Course Team', u'Group Configurations', u'Advanced Settings', u'Certificates'], self.course_outline.course_menu_item(1))
        self.assertEqual([u'Import', u'Export'], self.course_outline.course_menu_item(2))

        # course staff
        self.switch_to_user(self.course_staff)
        self.course_outline.visit()
        self.assertEqual([u'Course\nContent', u'Course\nSettings'], self.course_outline.course_menu)
        self.assertEqual([u'Outline', u'Updates', u'Pages', u'Files & Uploads'], self.course_outline.course_menu_item(0))
        self.assertEqual([u'Grading'], self.course_outline.course_menu_item(1))

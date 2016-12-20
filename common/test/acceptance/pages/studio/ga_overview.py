"""
Course Outline page in Studio.
"""
from .overview import CourseOutlinePage as EdXCourseOutlinePage


class CourseOutlinePage(EdXCourseOutlinePage):

    @property
    def course_menu(self):
        return self.q(css='.nav-course .nav-item .title').text

    def course_menu_item(self, index):
        self.click_course_menu(index)
        return self.q(css='.nav-course .nav-item>.is-shown>.nav-sub .nav-item').text

    def click_course_menu(self, index):
        return self.q(css='.nav-course .nav-item .title').nth(index).click()

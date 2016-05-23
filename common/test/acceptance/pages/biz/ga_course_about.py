"""
Course about page of biz.
"""

from common.test.acceptance.pages.lms.course_about import CourseAboutPage as EdxCourseAboutPage


class CourseAboutPage(EdxCourseAboutPage):
    @property
    def is_register_link_displayed(self):
        return len(self.q(css='a.register').results) > 0

    @property
    def register_disabled_text(self):
        return self.q(css='span.disabled').text

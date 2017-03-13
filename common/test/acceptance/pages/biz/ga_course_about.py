"""
Course about page of biz.
"""

from common.test.acceptance.pages.lms.course_about import CourseAboutPage as EdxCourseAboutPage


class CourseAboutPage(EdxCourseAboutPage):

    def __init__(self, browser, course_id, not_found=False):
        super(CourseAboutPage, self).__init__(browser, course_id)
        self.not_found = not_found

    def is_browser_on_page(self):
        if self.not_found:
            return self.q(css='#summary>h1').present and u'Page not found' in self.q(css='#summary>h1').first.text[0]
        else:
            return super(CourseAboutPage, self).is_browser_on_page()

    @property
    def is_register_link_displayed(self):
        return len(self.q(css='a.register').results) > 0

    @property
    def register_disabled_text(self):
        return self.q(css='span.disabled').text

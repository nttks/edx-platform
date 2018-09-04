"""
Course info page.
"""

from .course_page import CoursePage


class CourseInfoPage(CoursePage):
    """
    Course info.
    """

    url_path = "info"

    def is_browser_on_page(self):
        return self.q(css='section.updates').present

    @property
    def num_updates(self):
        """
        Return the number of updates on the page.
        """
        return len(self.q(css='section.updates section article').results)

    @property
    def count_new_icon_updates(self):
        """
        Return the number of new icons of updates on the page.
        """
        return len(self.q(css='section.updates section article h2 span.new-icon').results)

    @property
    def handout_links(self):
        """
        Return a list of handout assets links.
        """
        return self.q(css='section.handouts ol li a').map(lambda el: el.get_attribute('href')).results

    def click_top_page(self):
        self.q(css='a.top-page').first.click()

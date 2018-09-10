"""
Student playback page
"""
from .course_page import CoursePage


class PlaybackPage(CoursePage):
    """
    Student playback page.
    """
    url_path = 'playback'

    def is_browser_on_page(self):
        return self.q(css='div.course-info').present and self.q(css='div#course-info-playback').present

    @property
    def title_name(self):
        """
        Return the name of the title
        """
        return str(self.q(css='.course-info h2').text[0])

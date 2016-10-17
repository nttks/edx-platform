"""
Course rerun page in Studio
"""

from .course_rerun import CourseRerunPage as EdXCourseRerunPage
from .utils import set_input_value


class CourseRerunPage(EdXCourseRerunPage):
    """
    Course rerun page in Studio
    """

    COURSE_NAME_INPUT = '.rerun-course-name'

    @property
    def course_name(self):
        """
        Returns the value of the course name field.
        """
        return self.q(css=self.COURSE_NAME_INPUT).text[0]

    @course_name.setter
    def course_name(self, value):
        """
        Sets the value of the course name field.
        """
        set_input_value(self, self.COURSE_NAME_INPUT, value)

    @property
    def course_rerun_error(self):
        """
        Returns course rerun error element.
        """
        return self.q(css='.wrapper-rerun-course .wrapper-error.is-shown #course_rerun_error.message')

    @property
    def course_rerun_error_message(self):
        """
        Returns text of course creation error message.
        """
        self.wait_for_element_presence(
            ".wrapper-rerun-course .wrapper-error.is-shown #course_rerun_error.message", "Course rerun error message is present"
        )
        return self.course_rerun_error.results[0].find_element_by_css_selector('p').text

    def create_rerun(self):
        """
        Clicks the create rerun button.
        """
        super(CourseRerunPage, self).create_rerun()
        self.wait_for_ajax()

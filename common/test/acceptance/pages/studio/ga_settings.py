# coding: utf-8
"""
Course Schedule and Details Settings page.
"""
from .settings import SettingsPage as EdXSettingsPage


class SettingsPage(EdXSettingsPage):
    """
    Course Schedule and Details Settings page.
    """

    ################
    # Properties
    ################
    @property
    def has_error(self):
        return self.q(css='span.message-error').present

    @property
    def deadline_start_date(self):
        """
        Returns the deadline_start_date.
        """
        self.wait_for_element_visibility(
            '#course-deadline-start-date',
            'Deadline start date element is available'
        )
        return self.get_elements('#course-deadline-start-date')

    @property
    def deadline_start_time(self):
        """
        Returns the deadline_start_time.
        """
        self.wait_for_element_visibility(
            '#course-deadline-start-time',
            'Deadline start time element is available'
        )
        return self.get_elements('#course-deadline-start-time')

    @property
    def terminate_start_date(self):
        """
        Returns the terminate_start_date.
        """
        self.wait_for_element_visibility(
            '#course-terminate-start-date',
            'Terminate start date element is available'
        )
        return self.get_elements('#course-terminate-start-date')

    @property
    def terminate_start_time(self):
        """
        Returns the terminate_start_time.
        """
        self.wait_for_element_visibility(
            '#course-terminate-start-time',
            'Terminate start time element is available'
        )
        return self.get_elements('#course-terminate-start-time')

    @property
    def course_category(self):
        """
        Returns the course_category.
        """
        self.wait_for_element_visibility(
            '#course-category',
            'Course category element is available'
        )
        return self.get_elements('#course-category')

    @property
    def is_course_category_displayed(self):
        """
        Returns whether the course_category has displayed.
        """
        return self.q(css='#course-category').present

    @property
    def is_f2f_course(self):
        """
        Returns the is_f2f_course.
        """
        self.wait_for_element_visibility(
            '#face2face-course',
            'Face2face course element is available'
        )
        return self.get_elements('#face2face-course')

    @property
    def is_f2f_course_sell(self):
        """
        Returns the is_f2f_course_sell.
        """
        self.wait_for_element_visibility(
            '#face2face-course-sell',
            'Face2face course sell element is available'
        )
        return self.get_elements('#face2face-course-sell')

    @property
    def is_f2f_course_checked(self):
        return self.q(css='#face2face-course:checked').present

    @property
    def is_f2f_course_sell_checked(self):
        return self.q(css='#face2face-course-sell:checked').present

    @property
    def course_canonical_name(self):
        """
        Returns the course_canonical_name.
        """
        self.wait_for_element_visibility(
            '#course-canonical-name',
            'Course canonical name element is available'
        )
        return self.get_elements('#course-canonical-name')

    @property
    def course_contents_provider(self):
        """
        Returns the course_contents_provider.
        """
        self.wait_for_element_visibility(
            '#course-contents-provider',
            'Course contents provider element is available'
        )
        return self.get_elements('#course-contents-provider')

    @property
    def teacher_name(self):
        """
        Returns the teacher_name.
        """
        self.wait_for_element_visibility(
            '#course-teacher-name',
            'Course teacher name element is available'
        )
        return self.get_elements('#course-teacher-name')

    @property
    def course_span(self):
        """
        Returns the course_span.
        """
        self.wait_for_element_visibility(
            '#course-span',
            'Course span element is available'
        )
        return self.get_elements('#course-span')

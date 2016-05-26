from collections import OrderedDict
import itertools

from ga_advanced_course.models import AdvancedCourse, AdvancedF2FCourse
from ga_advanced_course.utils import (
    is_advanced_course_full,
    is_advanced_course_end_of_sale,
    get_advanced_course_purchased_order,
    is_upsell_disabled,
)


class AdvancedCourseStatus(object):
    """
    Helper class for advanced courses related to the specified user and the course.
    """
    def __init__(self, request, course, advanced_courses=None):
        self.course = course
        self.disabled_upsell = is_upsell_disabled(request, course.id)
        # The methods in this class is the assumption, which is also used from the view templates.
        # Therefore, we get at the beggining of the advanced courses and status.
        self.advanced_courses = self._get_advanced_courses_with_status(request.user, course.id, advanced_courses)
        self.available_types = self._get_available_types()

    def _get_advanced_courses_with_status(self, user, course_key, advanced_courses):
        """
        Returns advanced courses associated to the course along with the status.

        The status includes the following.
            - is_purchased
                Whether user had already purchased
            - is_full
                Whether advanced course has reached the capacity
            - is_end_of_sale
                Whether all of the tickets for advanced course has been end of sale
        """
        def _get_status(advanced_course):
            order = get_advanced_course_purchased_order(user, advanced_course)
            return {
                'order': order,
                'is_purchased': order is not None,
                'is_full': is_advanced_course_full(advanced_course),
                'is_end_of_sale': is_advanced_course_end_of_sale(advanced_course),
            }

        if advanced_courses is None:
            advanced_courses = AdvancedCourse.get_advanced_courses_by_course_key(course_key)

        _ret = {
            advanced_course.id: dict({'advanced_course': advanced_course}, **_get_status(advanced_course))
            for advanced_course in advanced_courses
        }
        # sort by advanced_course.id
        return OrderedDict(sorted(_ret.items(), key=lambda x: x[0]))

    def _get_available_types(self):
        """
        Returns an available advanced course types.

        `available`, determine only the status of the advanced course. Not purchase status of the user.

        The course there is a possibility that advanced course of more than one type (ex. face-to-face
        and online session in the future) is associated.
        """
        def _is_purchase_available(statuses):
            """
            Check whether advanced course is not full or not a ticket sales end.
            """
            return any([not status['is_full'] and not status['is_end_of_sale'] for status in statuses])

        _key_func = lambda d: d['advanced_course'].__class__.__name__
        _advanced_courses = sorted(self.advanced_courses.values(), key=_key_func)
        _courses_group = itertools.groupby(_advanced_courses, _key_func)

        return [cls_name for cls_name, _dicts in _courses_group if _is_purchase_available(list(_dicts))]

    def has_available_f2f_course(self):
        return AdvancedF2FCourse.__name__ in self.available_types

    def is_purchased(self, advanced_course_id=None):
        """
        Check whether user is purchased.

        If advanced_course_id is not specified, then check all of advanced course.
        """

        if advanced_course_id and advanced_course_id not in self.advanced_courses:
            raise ValueError('no advanced_course {advanced_course_id} in {course}'.format(
                advanced_course_id=advanced_course_id, course=self.course.id
            ))

        if advanced_course_id is None:
            return any([status['is_purchased'] for status in self.advanced_courses.values()])
        else:
            return self.advanced_courses[advanced_course_id]['is_purchased']

    def get_purchased_orders(self):
        return [status['order'] for status in self.advanced_courses.values() if status['is_purchased']]

    def show_upsell_message(self):
        """
        Returns whether to show upsell.
        """
        return not (self.is_purchased() or self.disabled_upsell)

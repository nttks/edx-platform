from opaque_keys.edx.keys import CourseKey
from shoppingcart.models import Order

from ga_advanced_course.tests.utils import start_purchase_ticket
from ga_advanced_course.tests.factories import AdvancedF2FCourseFactory, AdvancedCourseTicketFactory
from verify_student.views import _purchase_with_shoppingcart as purchase_with_shoppingcart


def _create_advanced_courses(course, count, active=True):
    return [
        AdvancedF2FCourseFactory.create(
            course_id=course.id,
            display_name='display_name {}'.format(i),
            is_active=active
        )
        for i in range(count)
    ]


def _create_ticket(advanced_course, count):
    return [
        AdvancedCourseTicketFactory.create(
            advanced_course=advanced_course,
            display_name='ticket {}'.format(i)
        )
        for i in range(count)
    ]


def get_order_from_advanced_course(course, user):
    advanced_course_list = _create_advanced_courses(course, 1, active=False)
    ticket = _create_ticket(advanced_course_list[0], 1)
    return start_purchase_ticket(user, ticket[0]), advanced_course_list[0]


def get_order_from_paid_course(course_mode, course, user):
    purchase_with_shoppingcart(user,
                               course_mode,
                               CourseKey.from_string(unicode(course.id)), 1)
    return Order.objects.get(user=user, status='paying')

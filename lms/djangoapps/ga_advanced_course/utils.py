"""
Utility methods for advanced courses
"""
import logging

from ga_shoppingcart.models import AdvancedCourseItem

log = logging.getLogger(__name__)


def get_advanced_course_purchased_order(user, advanced_course):
    _orders = [
        item.order
        for item in AdvancedCourseItem.find_purchased_by_user_and_advanced_course(user, advanced_course)
    ]
    # Purchased order must be only one per advanced course.
    return _orders[0] if len(_orders) > 0 else None


def is_advanced_course_purchased(user, advanced_course):
    """
    Check whether purchased ticket of specified advanced course.
    """
    return get_advanced_course_purchased_order(user, advanced_course) is not None


def is_advanced_course_full(advanced_course):
    """
    Check whether specified advanced course is full.
    """
    count = AdvancedCourseItem.find_purchased_with_keep_by_advanced_course(advanced_course).count()
    return count >= advanced_course.capacity


def is_advanced_course_end_of_sale(advanced_course, tickets=None):
    """
    Check whether all of tickets of specified advanced course is end of sale.
    """
    if tickets is None:
        tickets = advanced_course.tickets
    return all([ticket.is_end_of_sale() for ticket in tickets])

import itertools

from django.utils.translation import ugettext as _

from student.models import CourseEnrollment

from ga_shoppingcart.models import AdvancedCourseItem


class Features(object):

    USER_ID = 'User ID'
    EMAIL = 'Email'
    USERNAME = 'Username'
    NAME = 'Name'
    ADVANCED_COURSE_NAME = 'Advanced Course Name'
    ADVANCED_COURSE_TICKET_NAME = 'Ticket Name'
    ENTRY_DATE = 'Entry Date'
    PAYMENT_METHOD = 'Payment Method'
    ENROLLMENT = 'Enrollment'

    STUDENT_FEATURES = {
        USER_ID: 'id',
        EMAIL: 'email',
        USERNAME: 'username',
    }

    PROFILE_FEATURES = {
        NAME: 'name',
    }

    ADVANCED_COURSE_FEATURES = {
        ADVANCED_COURSE_NAME: 'display_name',
    }

    ADVANCED_COURSE_TICKET_FEATURES = {
        ADVANCED_COURSE_TICKET_NAME: 'display_name',
    }

    ADVANCED_COURSE_ORDER_FEATURES = {
        ENTRY_DATE: 'purchase_time',
    }

    ADVANCED_COURSE_ORDERITEM_FEATURES = {
        PAYMENT_METHOD: 'payment_method',
    }


def advanced_course_purchased_features(course_id, features):
    """
    Returns a list of the ticket purchaser of advanced course.
    """

    def _extract_student(student, is_enrollment):
        """ convert student to dictionary """
        student_dict = {k: getattr(student, v) for k, v in Features.STUDENT_FEATURES.items() if k in features}

        profile = student.profile
        if profile is not None:
            student_dict.update(
                {k: getattr(profile, v) for k, v in Features.PROFILE_FEATURES.items() if k in features}
            )

        if Features.ENROLLMENT in features:
            student_dict[Features.ENROLLMENT] = _('Enrolled') if is_enrollment else _('Not Enrolled')

        return student_dict

    def _extract_advanced_course(advanced_course_ticket):
        """ convert advanced_course and ticket to dictionaly """

        advanced_course = advanced_course_ticket.advanced_course

        advanced_course_dict = {
            k: getattr(advanced_course, v)
            for k, v in Features.ADVANCED_COURSE_FEATURES.items() if k in features
        }

        advanced_course_dict.update({
            k: getattr(advanced_course_ticket, v)
            for k, v in Features.ADVANCED_COURSE_TICKET_FEATURES.items() if k in features
        })

        return advanced_course_dict

    def _extract_advanced_course_item(item):
        """ convert item to dictionaly """
        order_dict = {
            k: getattr(item.order, v)
            for k, v in Features.ADVANCED_COURSE_ORDER_FEATURES.items() if k in features
        }
        order_dict.update({
            k: getattr(item, v)
            for k, v in Features.ADVANCED_COURSE_ORDERITEM_FEATURES.items() if k in features
        })
        return order_dict

    event_user_items = AdvancedCourseItem.find_purchased_by_course_id(course_id).select_related(
        'advanced_course_ticket__advanced_course', 'user__profile'  # preload for performance
    )

    user_ids = set([item.user.id for item in event_user_items])
    enrollment_users = CourseEnrollment.objects.filter(
        user__in=user_ids,
        course_id=course_id,
        is_active=True
    ).values_list('user_id', flat=True)

    return [
        dict(itertools.chain(*[
            _extract_advanced_course(item.advanced_course_ticket).items(),
            _extract_advanced_course_item(item).items(),
            _extract_student(item.user, item.user.id in enrollment_users).items()
        ]))
        for item in event_user_items
    ]

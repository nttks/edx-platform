import itertools
import re

from django.utils.translation import ugettext as _

from shoppingcart.models import CertificateItem
from student.models import CourseEnrollment

from ga_shoppingcart.models import AdvancedCourseItem, PersonalInfo


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
    FULL_NAME = 'Fullname'
    KANA = 'Kana'
    POSTAL_CODE = 'Postal/Zip Code'
    ADDRESS_LINE_1 = 'Address Line 1'
    ADDRESS_LINE_2 = 'Address Line 2'
    PHONE_NUMBER = 'Phone Number'
    FREE_ENTRY_FIELD_1 = 'Free Entry Field 1'
    FREE_ENTRY_FIELD_2 = 'Free Entry Field 2'
    FREE_ENTRY_FIELD_3 = 'Free Entry Field 3'
    FREE_ENTRY_FIELD_4 = 'Free Entry Field 4'
    FREE_ENTRY_FIELD_5 = 'Free Entry Field 5'

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

    COURSE_ORDER_FEATURES = {
        ENTRY_DATE: 'purchase_time',
    }

    COURSE_ORDERITEM_FEATURES = {
        PAYMENT_METHOD: 'payment_method',
    }

    PERSONAL_INFO_FEATURES = {
        FULL_NAME: 'full_name',
        KANA: 'kana',
        POSTAL_CODE: 'postal_code',
        ADDRESS_LINE_1: 'address_line_1',
        ADDRESS_LINE_2: 'address_line_2',
        PHONE_NUMBER: 'phone_number',
        FREE_ENTRY_FIELD_1: 'free_entry_field_1',
        FREE_ENTRY_FIELD_2: 'free_entry_field_2',
        FREE_ENTRY_FIELD_3: 'free_entry_field_3',
        FREE_ENTRY_FIELD_4: 'free_entry_field_4',
        FREE_ENTRY_FIELD_5: 'free_entry_field_5',
    }


def _get_general_features(item, enrollment_users, features):
    """
    Returns of the items which student and personal info.
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

    def _extract_personal_info(item):
        """ convert personal info to dictionary """
        try:
            personal_info = PersonalInfo.objects.get(order_id=item.order.id)
        except PersonalInfo.DoesNotExist:
            order_dict = {
                k: '#N/A'
                for k, v in Features.PERSONAL_INFO_FEATURES.items() if k in features
            }
        else:
            order_dict = {
                k: re.sub('\r\n|\r|\n', ' ', getattr(personal_info, v)) or '#N/A'
                for k, v in Features.PERSONAL_INFO_FEATURES.items() if k in features
            }
        return order_dict

    return _extract_student(item.user, item.user.id in enrollment_users).items() + _extract_personal_info(item).items()


def advanced_course_purchased_features(course_id, features):
    """
    Returns a list of the ticket purchaser of advanced course.
    """

    def _extract_advanced_course(advanced_course_ticket):
        """ convert advanced_course and ticket to dictionary """

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
        """ convert item to dictionary """
        order_dict = {
            k: getattr(item.order, v)
            for k, v in Features.COURSE_ORDER_FEATURES.items() if k in features
        }
        order_dict.update({
            k: getattr(item, v)
            for k, v in Features.COURSE_ORDERITEM_FEATURES.items() if k in features
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
        dict(itertools.chain(
            _extract_advanced_course(item.advanced_course_ticket).items(),
            _extract_advanced_course_item(item).items(),
            _get_general_features(item, enrollment_users, features)
        ))
        for item in event_user_items
    ]


def paid_course_purchased_features(course_id, features):
    """
    Returns a list of the paid course.
    """

    def _extract_paid_course_item(item):
        """ convert item to dictionary """
        order_dict = {
            k: getattr(item.order, v)
            for k, v in Features.COURSE_ORDER_FEATURES.items() if k in features
        }
        order_dict.update({
            k: getattr(item.order, v)
            for k, v in Features.COURSE_ORDERITEM_FEATURES.items() if k in features
        })
        return order_dict

    event_user_items = CertificateItem.objects.filter(
        course_id=course_id,
        status='purchased',
        order__status='purchased',
    )
    user_ids = set([item.user.id for item in event_user_items])
    enrollment_users = CourseEnrollment.objects.filter(
        user__in=user_ids,
        course_id=course_id,
        is_active=True
    ).values_list('user_id', flat=True)

    return [
        dict(itertools.chain(
            _extract_paid_course_item(item).items(),
            _get_general_features(item, enrollment_users, features),
        ))
        for item in event_user_items
    ]

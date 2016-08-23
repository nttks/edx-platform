"""
API for managing user accounts for gacco.
"""
import logging

from bulk_email.models import Optout
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting

from ..errors import UserAPIInternalError, UserAPIRequestError, UserNotFound, ReceiveEmailNotFoundGlobalCourseError
from ..helpers import intercept_errors

log = logging.getLogger(__name__)


def _validate_user_and_global_course_ids(requesting_user):

    if requesting_user is None:
        raise UserNotFound()

    global_course_ids = CourseGlobalSetting.all_course_id()

    if not global_course_ids:
        raise ReceiveEmailNotFoundGlobalCourseError()

    return global_course_ids


@intercept_errors(UserAPIInternalError, ignore_errors=[UserAPIRequestError])
def can_receive_email_global_course(requesting_user):
    """Return bool that user can receive email.

    Args:
        requesting_user (User): The user requesting to receive email as global course.

    Returns:
        If True, user can receive email. If False, can not.

    Raises:
        UserNotFound: requesting_user is None.
        UserAPIInternalError: the operation failed due to an unexpected error.
        ReceiveEmailNotFoundGlobalCourseError: not found global courses of enabled.
    """
    return not Optout.objects.filter(
        user=requesting_user,
        course_id__in=_validate_user_and_global_course_ids(requesting_user)
    ).exists()


@intercept_errors(UserAPIInternalError, ignore_errors=[UserAPIRequestError])
def optout_global_course(requesting_user):
    """Optout from all global course.

    Args:
        requesting_user (User): The user requesting to optout as global course.

    Raises:
        UserNotFound: requesting_user is None.
        UserAPIInternalError: the operation failed due to an unexpected error.
        ReceiveEmailNotFoundGlobalCourseError: not found global courses of enabled.
    """
    for course_id in _validate_user_and_global_course_ids(requesting_user):
        Optout.objects.get_or_create(user=requesting_user, course_id=course_id)


@intercept_errors(UserAPIInternalError, ignore_errors=[UserAPIRequestError])
def optin_global_course(requesting_user):
    """Optin from all global course.

    Args:
        requesting_user (User): The user requesting to optin as global course.

    Raises:
        UserNotFound: requesting_user is None.
        UserAPIInternalError: the operation failed due to an unexpected error.
        ReceiveEmailNotFoundGlobalCourseError: not found global courses of enabled.
    """
    Optout.objects.filter(
        user=requesting_user,
        course_id__in=_validate_user_and_global_course_ids(requesting_user)
    ).delete()

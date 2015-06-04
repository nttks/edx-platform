from django.contrib.auth.models import User
from student.models import UserStanding


def users_unenrolled_in(course_id):
    """
    Returns users which are not enrolled in specify course_id.
    """
    return User.objects.filter(
        is_active=True
    ).exclude(
        standing__account_status=UserStanding.ACCOUNT_DISABLED
    ).exclude(
        courseenrollment__course_id=course_id, courseenrollment__is_active=True
    )

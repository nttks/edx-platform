
from django.conf import settings

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from student.models import CourseEnrollment
from xmodule.course_module import CourseDescriptor


def is_terminated_tab(tab, course, user, is_staff):
    for config in getattr(settings, 'COURSE_TERMINATED_CHECK_EXCLUDE_PATH', []):
        if tab.type == config.get('tab', ''):
            return False
    return is_terminated(course, user, is_staff)


def is_terminated(courselike, user, is_staff):
    if not (isinstance(courselike, CourseDescriptor) or isinstance(courselike, CourseOverview)):
        raise ValueError("courselike object must be instance of CourseDescriptor or CourseOverview. {}".format(type(courselike)))
    return not is_staff and (_is_terminated(courselike) or _is_individual_closed(courselike, user))


def _is_terminated(courselike):
    if isinstance(courselike, CourseDescriptor):
        return courselike.has_terminated()
    elif isinstance(courselike, CourseOverview):
        return courselike.extra and courselike.extra.has_terminated


def _is_individual_closed(courselike, user):
    # Check whether self-paced course for performance.
    if not (
        (isinstance(courselike, CourseDescriptor) and courselike.self_paced) or
        (isinstance(courselike, CourseOverview) and courselike.extra and courselike.extra.self_paced)
    ):
        return False

    if not user.is_authenticated():
        return False

    enrollment = CourseEnrollment.get_enrollment(user, courselike.id)
    return enrollment and enrollment.is_individual_closed()

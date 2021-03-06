from django.conf import settings

from courseware.access import has_access, GA_ACCESS_CHECK_TYPE_GLOBAL_COURSE_CREATOR, GA_ACCESS_CHECK_TYPE_OLD_COURSE_VIEW
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from student.models import CourseEnrollment
from xmodule.course_module import CourseDescriptor


def is_terminated_tab(tab, course, user):
    for config in getattr(settings, 'COURSE_TERMINATED_CHECK_EXCLUDE_PATH', []):
        if tab.type == config.get('tab', ''):
            return False
    return is_terminated(course, user)


def is_terminated(courselike, user):
    if not (isinstance(courselike, CourseDescriptor) or isinstance(courselike, CourseOverview)):
        raise ValueError("courselike object must be instance of CourseDescriptor or CourseOverview. {}".format(type(courselike)))

    is_global_staff = has_access(user, 'staff', 'global')
    is_old_course_viewer = has_access(user, GA_ACCESS_CHECK_TYPE_OLD_COURSE_VIEW, 'global')
    is_ga_global_course_creator = has_access(user, GA_ACCESS_CHECK_TYPE_GLOBAL_COURSE_CREATOR, 'global')
    is_course_staff = has_access(user, 'staff', courselike)
    is_course_beta_tester = has_access(user, 'beta_tester', courselike)

    # (#2197, #2150, #2478-1)
    # Note1: Even if course terminate date has passed, these users can access it.
    #        - is_staff
    #        - ga_old_course_viewer
    #        - ga_global_course_creator
    #        - instructor
    #        - staff
    #        - ga_course_scorer
    # Note2: Even if self-paced course and its individual end date has passed, these users can access it.
    #        - is_staff
    #        - ga_old_course_viewer
    #        - ga_global_course_creator
    #        - instructor
    #        - staff
    #        - ga_course_scorer
    #        - beta_testers
    return (
              not (is_global_staff or is_old_course_viewer or is_ga_global_course_creator or is_course_staff)
              and _is_terminated(courselike)
           ) or (
              not (is_global_staff or is_old_course_viewer or is_ga_global_course_creator or is_course_beta_tester)
              and _is_individual_closed(courselike, user)
           )


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

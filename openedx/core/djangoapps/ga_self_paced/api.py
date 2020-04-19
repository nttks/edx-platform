"""
API for ga-self-paced.
"""
from datetime import timedelta

from django.utils import timezone


def get_individual_date(base_date, timedelta_info):
    if not base_date:
        return None
    if timedelta_info.get('days'):
        base_date += timedelta(days=timedelta_info.get('days'))
    if timedelta_info.get('hours'):
        base_date += timedelta(hours=timedelta_info.get('hours'))
    if timedelta_info.get('minutes'):
        base_date += timedelta(minutes=timedelta_info.get('minutes'))
    return base_date


def get_base_date(enrollment):
    """
    Returns the base date for self-paced course.

    If the student has been enrolled before starting course, then base date is
    course start date. Otherwise, base date is enrollment date.

    Enrollment date is create date of CourseEnrollment. However, in case of paid course,
    CourseEnrollment are created in the inactive state and become active after payment
    process is completed. Therefore, use the latest date of histories.
    """
    if not enrollment:
        return None
    if enrollment.is_paid_course():
        enrollment_date = enrollment.history.filter(is_active=True, mode=enrollment.mode).latest('history_date').history_date
    else:
        enrollment_date = enrollment.created
    return max(enrollment.course_overview.start, enrollment_date)


def get_course_end_date(enrollment):
    if not enrollment:
        return None
    _extra = enrollment.course_overview.extra
    if not (_extra and _extra.self_paced and _extra.has_individual_end):
        return None
    individual_end_date = get_individual_date(get_base_date(enrollment), {
        'days': _extra.individual_end_days,
        'hours': _extra.individual_end_hours,
        'minutes': _extra.individual_end_minutes
    })
    # If course terminate date is earlier than individual end date, then set course terminate date. #2479
    terminate_date = _extra.terminate_start
    return terminate_date if terminate_date and individual_end_date > terminate_date else individual_end_date


def is_course_closed(enrollment):
    end_date = get_course_end_date(enrollment)
    return end_date and timezone.now() > end_date


def get_course_end_date_dashboard(enrollment, extra):
    if not enrollment:
        return None
    _extra = extra
    if not (_extra and _extra['self_paced'] and
            (_extra['individual_end_days'] is not None or
            _extra['individual_end_hours'] is not None or
            _extra['individual_end_minutes'] is not None)):
        return None
    individual_end_date = get_individual_date(get_base_date(enrollment), {
        'days': _extra['individual_end_days'],
        'hours': _extra['individual_end_hours'],
        'minutes': _extra['individual_end_minutes']
    })
    # If course terminate date is earlier than individual end date, then set course terminate date. #2479
    terminate_date = _extra['terminate_start']
    return terminate_date if terminate_date and individual_end_date > terminate_date else individual_end_date
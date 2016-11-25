"""
API for management optional features.
"""
from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration


def is_available(key, course_key=None):
    if course_key is not None:
        return CourseOptionalConfiguration.current(key, course_key).enabled
    return False

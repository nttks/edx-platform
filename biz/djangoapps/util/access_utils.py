"""
Access utilities
"""

from django.http import Http404

from courseware.courses import get_course_with_access


def has_staff_access(user, course_key):
    try:
        get_course_with_access(user, 'staff', course_key)
        return True
    except Http404:
        return False

"""
Gacco Course utilities
"""

GA_JWPLAYER_XBLOCK = 'jwplayerxblock'


def is_using_jwplayer_course(course):
    if course is None:
        return False

    return GA_JWPLAYER_XBLOCK in course.advanced_modules


def sort_by_start_date(courses, desc=True):
    """
    Courses objects sorted by start date.
    If the start date is None and desc it is the last.
    :param courses: course objects
    :param desc: True is desc, False is asc
    :return: sorted course objects
    """
    return sorted(
        courses,
        key=lambda c: (c.start is not None, c.start),
        reverse=desc
    )

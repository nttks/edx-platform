"""
Gacco Course utilities
"""

GA_JWPLAYER_XBLOCK = 'jwplayerxblock'


def is_using_jwplayer_course(course):
    if course is None:
        return False

    return GA_JWPLAYER_XBLOCK in course.advanced_modules

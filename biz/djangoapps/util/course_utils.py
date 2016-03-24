"""
Course utilities
"""
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore


def get_course(course_id):
    """
    Get modulestore's course by course_id (not only str but also CourseKey)

    :param course_id: course_id (str or CourseKey): Id for the course
    :return: A course object or None (if course_id does not match any course)
    """
    if not isinstance(course_id, CourseKey):
        try:
            course_id = CourseKey.from_string(course_id)
        except InvalidKeyError:
            return None

    return modulestore().get_course(course_id)

# -*- coding: utf-8 -*-
"""
Management command to reset attendance status.
"""
import json
import logging
from django.core.management.base import BaseCommand
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from optparse import make_option
from opaque_keys import InvalidKeyError
from student.models import CourseEnrollment, CourseEnrollmentAttribute
from util.ga_attendance_status import AttendanceStatusExecutor, KEY_COMPLETE_DATE

log = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """
    Reset completed of attendance status.

    Example:
      python manage.py lms --settings=aws ga_reset_attendance_status -c "course_id"
    """

    option_list = BaseCommand.option_list + (
        make_option('-c', '--course',
                    metavar='COURSE_ID',
                    dest='course',
                    default=False,
                    help='Course ID for reset target.'),
    )

    def handle(self, *args, **options):
        # check course
        course_id = options['course']
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)

        # execute
        total_counter = 0
        updated_counter = 0
        failed_counter = 0
        for enrollment in CourseEnrollment.objects.filter(course_id=course_key):
            try:
                total_counter += 1
                executor = AttendanceStatusExecutor(enrollment=enrollment)
                if executor.attr is None:
                    continue
                else:
                    enrollment_attr = executor.attr

                value = json.loads(enrollment_attr.value)
                if KEY_COMPLETE_DATE in value:
                    del value[KEY_COMPLETE_DATE]
                    enrollment_attr.value = json.dumps(value)
                    enrollment_attr.save()
                    updated_counter += 1

            except CourseEnrollmentAttribute.DoesNotExist:
                pass

            except Exception as e:
                failed_counter += 1
                log.error(e)
                log.error('Error happened at {}'.format(enrollment['id']))

        log.info('total:{}, updated:{}, failed:{}'.format(
            str(total_counter), str(updated_counter), str(failed_counter)))

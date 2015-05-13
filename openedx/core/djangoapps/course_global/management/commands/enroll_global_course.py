from django.core.management.base import BaseCommand, CommandError
from optparse import make_option

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locations import SlashSeparatedCourseKey

from student.models import CourseEnrollment
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from openedx.core.djangoapps.course_global.management.commands import users_unenrolled_in


class Command(BaseCommand):
    """
    Enroll all users to all global courses.
    """

    option_list = BaseCommand.option_list + (
        make_option('-a', '--all',
                    action='store_true',
                    dest='all',
                    default=False,
                    help="Enroll all of global courses, if you specified this option"),
        make_option('-c', '--course',
                    metavar='COURSE_ID',
                    dest='course_id',
                    default=False,
                    help="course id to enroll")
    )

    def handle(self, *args, **options):
        if not options['course_id'] and not options['all']:
            raise CommandError("You must specify either one of course id or 'all' for this command")
        if options['course_id'] and options['all']:
            raise CommandError("You must specify either one of course id or 'all' for this command")

        if options['course_id']:
            try:
                course_key = CourseKey.from_string(options['course_id'])
            except InvalidKeyError:
                course_key = SlashSeparatedCourseKey.from_deprecated_string(options['course_id'])
            global_course_ids = [CourseGlobalSetting.objects.get(course_id=course_key).course_id]
        else:
            global_course_ids = CourseGlobalSetting.all_course_id()

        for global_course_id in global_course_ids:
            for user in users_unenrolled_in(global_course_id):
                CourseEnrollment.enroll(user, global_course_id)
            print "Enroll in the {} has been completed".format(global_course_id)

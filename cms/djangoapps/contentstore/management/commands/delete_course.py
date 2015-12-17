"""
    Command for deleting courses

    Arguments:
        arg1 (str): Course key of the course to delete
        arg2 (str): 'commit'

    Returns:
        none
"""
from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from .prompt import query_yes_no
from contentstore.utils import delete_course_and_groups
from opaque_keys.edx.keys import CourseKey
from opaque_keys import InvalidKeyError
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore


class Command(BaseCommand):
    """
    Delete a MongoDB backed course
    """
    help = '''Delete a MongoDB backed course'''

    def add_arguments(self, parser):
        parser.add_argument('course_key', help="ID of the course to delete.")
        parser.add_argument('--purge', action='store_true', dest='purge', default=False)

    def handle(self, *args, **options):
        try:
            course_key = CourseKey.from_string(options['course_key'])
        except InvalidKeyError:
            raise CommandError("Invalid course_key: '%s'." % options['course_key'])

        if not modulestore().get_course(course_key):
            raise CommandError("Course with '%s' key not found." % options['course_key'])

        purge = options['purge']
        print 'Going to delete the %s course from DB....' % options['course_key']
        if query_yes_no("Deleting course {course_key}. Purge assets is {purge}. Confirm?".format(
            course_key=course_key, purge=purge), default="no"):
            if query_yes_no("Are you sure. This action cannot be undone!", default="no"):
                delete_course_and_groups(course_key, ModuleStoreEnum.UserID.mgmt_command, purge=purge)
                print "Deleted course {}".format(course_key)

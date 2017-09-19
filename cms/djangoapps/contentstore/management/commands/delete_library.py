"""
    Command for deleting library

    Arguments:
        arg1 (str): library key of the library to delete

    Returns:
        none
"""
from django.core.management.base import BaseCommand, CommandError

from .prompt import query_yes_no
from contentstore.utils import delete_course_and_groups
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore


class Command(BaseCommand):
    """
    Delete a MongoDB backed library
    """
    help = '''Delete a MongoDB backed library'''

    def add_arguments(self, parser):
        parser.add_argument('library_key', help="ID of the library to delete.")
        parser.add_argument('--purge', action='store_true', dest='purge', default=False)

    def handle(self, *args, **options):
        try:
            library_key = CourseKey.from_string(options['library_key'])
        except InvalidKeyError:
            raise CommandError("Invalid course_key: '%s'." % options['library_key'])

        if not modulestore().get_library(library_key):
            raise CommandError("Library with '%s' key not found." % options['library_key'])

        purge = options['purge']
        print 'Going to delete the %s library from DB....' % options['library_key']
        if query_yes_no("Deleting library {library_key}. Purge assets is {purge}. Confirm?".format(
                        library_key=library_key, purge=purge), default="no"):
            if query_yes_no("Are you sure. This action cannot be undone!", default="no"):
                delete_course_and_groups(library_key, ModuleStoreEnum.UserID.mgmt_command, purge=purge)
                print "Deleted library {}".format(library_key)

                courses = modulestore().get_courses()
                for course in courses:
                    target_libraries = getattr(course, 'target_library', [])
                    if unicode(library_key) in target_libraries:
                        target_libraries.remove(unicode(library_key))
                        setattr(course, 'target_library', target_libraries)
                        modulestore().update_item(course, None)

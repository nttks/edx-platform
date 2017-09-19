"""
Unittests for deleting a library in an chosen modulestore
"""

import mock

from django.core.management import call_command, CommandError

from contentstore.tests.utils import CourseTestCase
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.factories import CourseFactory, LibraryFactory


class DeleteLibraryTest(CourseTestCase):
    """
    Test for library deleting functionality of the 'delete_library' command
    """

    YESNO_PATCH_LOCATION = 'contentstore.management.commands.delete_library.query_yes_no'

    def setUp(self):
        super(DeleteLibraryTest, self).setUp()

        org = 'TestX'
        course_number = 'TS01'
        course_run = '2015_Q1'

        # Create a course using split modulestore
        self.course = CourseFactory.create(
            org=org,
            number=course_number,
            run=course_run
        )
        self.libraries = LibraryFactory.create()
        target_libraries = getattr(self.course, 'target_library', [])
        target_libraries.append(unicode(self.libraries.location.library_key))
        setattr(self.course, 'target_library', target_libraries)
        modulestore().update_item(self.course, self.user.id)

    def test_invalid_key_not_found(self):
        """
        Test for when a library key is malformed
        """
        errstring = "Invalid course_key: 'foo/TestX/TS01/2015_Q7'"
        with self.assertRaisesRegexp(CommandError, errstring):
            call_command('delete_library', 'foo/TestX/TS01/2015_Q7')

    def test_library_key_not_found(self):
        """
        Test for when a non-existing library key is entered
        """
        errstring = "Library with 'TestX/TS01/2015_Q7' key not found."
        with self.assertRaisesRegexp(CommandError, errstring):
            call_command('delete_library', 'TestX/TS01/2015_Q7')

    def test_library_deleted(self):
        """
        Testing if the entered library was deleted
        """
        lib_key = self.libraries.location.library_key
        #Test if the library that is about to be deleted exists
        self.assertIsNotNone(modulestore().get_library(lib_key))

        with mock.patch(self.YESNO_PATCH_LOCATION) as patched_yes_no:
            patched_yes_no.return_value = True
            call_command('delete_library', unicode(lib_key))
            self.assertIsNone(modulestore().get_library(lib_key))

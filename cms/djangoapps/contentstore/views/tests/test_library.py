"""
Unit tests for contentstore.views.library

More important high-level tests are in contentstore/tests/test_libraries.py
"""
from contentstore.tests.utils import AjaxEnabledTestClient, parse_json
from contentstore.utils import reverse_course_url, reverse_library_url
from contentstore.views.component import get_component_templates
from contentstore.views.library import _get_course_and_check_access
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, LibraryFactory
from mock import patch
from opaque_keys.edx.locator import CourseKey, LibraryLocator
from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration
from student import auth
from student.roles import CourseInstructorRole
import ddt


def make_url_for_lib(course, library=None):
    """ Get the RESTful/studio URL for testing the given library """
    if library:
        lib_url = reverse_course_url('course_library_handler', course.id, kwargs={'library_key_string': unicode(library)})
    else:
        lib_url = reverse_course_url('course_library_handler', course.id)
    return lib_url


@ddt.ddt
class UnitTestLibraries(ModuleStoreTestCase):
    """
    Unit tests for library views
    """

    def setUp(self):
        user_password = super(UnitTestLibraries, self).setUp()
        self.course = CourseFactory.create()

        self.client = AjaxEnabledTestClient()
        self.client.login(username=self.user.username, password=user_password)

        CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='library-for-settings',
            course_key=self.course.id,
            changed_by_id=self.user.id
        ).save()

        self.session_data = {}  # Used by _bind_module
    ######################################################
    # Tests for /library/ - list and create libraries:

    @patch("contentstore.views.library.LIBRARIES_ENABLED", False)
    def test_with_libraries_disabled(self):
        """
        The library URLs should return 404 if libraries are disabled.
        """
        lib_url = make_url_for_lib(self.course)
        response = self.client.get_json(lib_url)
        self.assertEqual(response.status_code, 404)

    def test_redirect_libhome(self):
        """
        Redirect  /course/{}/library/ to course/{}/libhome.
        """
        # Create some more libraries
        lib_url = make_url_for_lib(self.course)
        response = self.client.get(lib_url, {
            'course_key_string': unicode(self.course.id)
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("libhome", response['location'])

    def test_library_listing(self):
        libraries = [LibraryFactory.create() for _ in range(3)]
        self.course.target_library = [unicode(library) for library in libraries]
        modulestore().update_item(self.course, self.user.id)
        lib_url = reverse_course_url('library_listing', self.course.id)
        response = self.client.get(lib_url, {
            'course_key_string': unicode(self.course.id)
        })
        self.assertEqual(response.status_code, 200)

    @ddt.data("delete", "put")
    def test_bad_http_verb(self, verb):
        """
        We should get an error if we do weird requests to /library/
        """
        lib_url = make_url_for_lib(self.course)
        response = getattr(self.client, verb)(lib_url)
        self.assertEqual(response.status_code, 405)

    def test_create_library(self):
        """ Create a library. """
        lib_url = make_url_for_lib(self.course)
        response = self.client.ajax_post(lib_url, {
            'org': 'org',
            'library': 'lib',
            'display_name': "New Library",
        })
        self.assertEqual(response.status_code, 200)
        # That's all we check. More detailed tests are in contentstore.tests.test_libraries...

    @patch.dict('django.conf.settings.FEATURES', {'ENABLE_CREATOR_GROUP': True})
    def test_lib_create_permission(self):
        """
        Users who are not given course creator roles should still be able to
        create libraries.
        """
        self.client.logout()
        ns_user, password = self.create_non_staff_user()

        instructor_role = CourseInstructorRole(self.course.id)
        auth.add_users(self.user, instructor_role, ns_user)
        CourseInstructorRole(self.course.location.course_key).add_users(ns_user)

        self.client.login(username=ns_user.username, password=password)

        lib_url = make_url_for_lib(self.course)
        response = self.client.ajax_post(lib_url, {
            'org': 'org', 'library': 'lib', 'display_name': "New Library",
        })
        self.assertEqual(response.status_code, 200)

    @ddt.data(
        {},
        {'org': 'org'},
        {'library': 'lib'},
        {'org': 'C++', 'library': 'lib', 'display_name': 'Lib with invalid characters in key'},
        {'org': 'Org', 'library': 'Wh@t?', 'display_name': 'Lib with invalid characters in key'},
    )
    def test_create_library_invalid(self, data):
        """
        Make sure we are prevented from creating libraries with invalid keys/data
        """
        lib_url = make_url_for_lib(self.course)
        response = self.client.ajax_post(lib_url, data)
        if data.get('org', '') == 'C++':
            # org uses course.org value. So, will not use org param.
            self.assertEqual(response.status_code, 200)
        else:
            self.assertEqual(response.status_code, 400)

    def test_no_duplicate_libraries(self):
        """
        We should not be able to create multiple libraries with the same key
        """
        lib = LibraryFactory.create(org=self.course.org)
        lib_key = lib.location.library_key
        lib_url = make_url_for_lib(self.course)
        response = self.client.ajax_post(lib_url, {
            'org': lib_key.org,
            'library': lib_key.library,
            'display_name': "A Duplicate key, same as 'lib'",
        })
        self.assertIn('already a library defined', parse_json(response)['ErrMsg'])
        self.assertEqual(response.status_code, 400)

    ######################################################
    # Tests for /library/:lib_key/ - get a specific library as JSON or HTML editing view

    def test_get_lib_info(self):
        """
        Test that we can get data about a library (in JSON format) using /library/:key/
        """
        # Create a library
        lib = LibraryFactory.create()
        lib_key = lib.location.library_key
        libraries = getattr(self.course, 'target_library', [])
        libraries.append(unicode(lib_key))
        setattr(self.course, 'target_library', libraries)
        modulestore().update_item(self.course, self.user.id)

        # Re-load the library from the modulestore, explicitly including version information:
        lib = self.store.get_library(lib_key, remove_version=False, remove_branch=False)
        version = lib.location.library_key.version_guid
        self.assertNotEqual(version, None)

        response = self.client.get_json(make_url_for_lib(self.course, lib_key))
        self.assertEqual(response.status_code, 200)
        info = parse_json(response)
        self.assertEqual(info['display_name'], lib.display_name)
        self.assertEqual(info['library_id'], unicode(lib_key))
        self.assertEqual(info['previous_version'], None)
        self.assertNotEqual(info['version'], None)
        self.assertNotEqual(info['version'], '')
        self.assertEqual(info['version'], unicode(version))

    def test_get_lib_edit_html(self):
        """
        Test that we can get the studio view for editing a library using /library/:key/
        """
        lib = LibraryFactory.create()
        lib_key = lib.location.library_key
        libraries = getattr(self.course, 'target_library', [])
        libraries.append(unicode(lib_key))
        setattr(self.course, 'target_library', libraries)
        modulestore().update_item(self.course, self.user.id)

        response = self.client.get(make_url_for_lib(self.course, lib_key))
        self.assertEqual(response.status_code, 200)
        self.assertIn("<html", response.content)
        self.assertIn(lib.display_name, response.content)

    @ddt.data('library-v1:Nonexistent+library', 'course-v1:Org+Course', 'course-v1:Org+Course+Run', 'invalid')
    def test_invalid_keys(self, key_str):
        """
        Check that various Nonexistent/invalid keys give 404 errors
        """
        lib_url = make_url_for_lib(self.course) + '/library/' + key_str
        response = self.client.get_json(lib_url)
        self.assertEqual(response.status_code, 404)

    def test_bad_http_verb_with_lib_key(self):
        """
        We should get an error if we do weird requests to /library/
        """
        lib = LibraryFactory.create()
        for verb in ("post", "delete", "put"):
            response = getattr(self.client, verb)(make_url_for_lib(self.course, lib.location.library_key))
            self.assertEqual(response.status_code, 405)

    def test_no_access(self):
        user, password = self.create_non_staff_user()
        self.client.login(username=user, password=password)

        lib = LibraryFactory.create()
        response = self.client.get(make_url_for_lib(self.course, lib.location.library_key))
        self.assertEqual(response.status_code, 404)

    def test_get_component_templates(self):
        """
        Verify that templates for adding discussion and advanced components to
        content libraries are not provided.
        """
        lib = LibraryFactory.create()
        lib.advanced_modules = ['lti']
        lib.save()
        templates = [template['type'] for template in get_component_templates(lib, library=True)]
        self.assertIn('problem', templates)
        self.assertNotIn('discussion', templates)
        self.assertNotIn('advanced', templates)

    def test_get_course_and_check_access(self):
        course_module = _get_course_and_check_access(self.course.id, self.user)
        self.assertIsNotNone(course_module)


class TestEnableLibraryContent(ModuleStoreTestCase):
    def setUp(self):
        user_password = super(TestEnableLibraryContent, self).setUp()
        self.course = CourseFactory.create()

        self.client = AjaxEnabledTestClient()
        self.client.login(username=self.user.username, password=user_password)

        self.session_data = {}  # Used by _bind_module

    @patch('contentstore.views.library.LIBRARIES_ENABLED', False)
    def test_disable_content_libraries(self, org='org', library='lib', display_name='Test Library'):
        response = self.client.ajax_post('/course/org.0/course_0/Run_0/library/', {
            'org': org,
            'library': library,
            'display_name': display_name,
        })
        self.assertEqual(response.status_code, 404)


class TestLibraryOption(ModuleStoreTestCase):
    def setUp(self):
        self.user_password = super(TestLibraryOption, self).setUp()
        self.course = CourseFactory.create()

        self.client = AjaxEnabledTestClient()
        self.client.login(username=self.user.username, password=self.user_password)

        self.session_data = {}  # Used by _bind_module

    def test_non_library_key(self, org='org', library='lib', display_name='Test Library'):
        lib = LibraryFactory.create()
        lib_key = lib.location.library_key
        libraries = getattr(self.course, 'target_library', [])
        libraries.append(unicode(lib_key))
        setattr(self.course, 'target_library', libraries)
        modulestore().update_item(self.course, self.user.id)

        response = self.client.ajax_post(make_url_for_lib(self.course, lib_key))
        self.assertEqual(response.status_code, 404)

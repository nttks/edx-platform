"""
Unit tests for course.py
"""
import json

from django.core.urlresolvers import reverse
from django.test.utils import override_settings

from contentstore.tests.utils import CourseTestCase, switch_ga_global_course_creator
from contentstore.utils import reverse_course_url
from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration
from student.roles import CourseInstructorRole, CourseStaffRole
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.factories import CourseFactory


class TestCourseDisplayName(CourseTestCase):
    """
    Unit tests for length of display_name.
    """

    def test_course_handler_display_name_over_max_length(self):
        org = 'test-org'
        number = 'test-number'
        run = '001'
        display_name = 'Course Display Name'

        post_data = {
            'org': org,
            'number': number,
            'run': run,
            'display_name': display_name,
        }

        # Fail to create course
        with override_settings(MAX_LENGTH_COURSE_DISPLAY_NAME=18):
            resp = self.client.post(
                reverse_course_url('course_handler', self.course.id),
                data=json.dumps(post_data),
                content_type='application/json',
                HTTP_ACCEPT='application/json',
            )
        self.assertEqual({
            u'ErrMsg': u'Course name, please be up to 18 characters.',
        }, json.loads(resp.content))

        # Success to create course
        with override_settings(MAX_LENGTH_COURSE_DISPLAY_NAME=19):
            resp = self.client.post(
                reverse_course_url('course_handler', self.course.id),
                data=json.dumps(post_data),
                content_type='application/json',
                HTTP_ACCEPT='application/json',
            )

        self.assertEqual({
            u'url': u'/course/{org}/{number}/{run}'.format(org=org, number=number, run=run),
            u'course_key': u'{org}/{number}/{run}'.format(org=org, number=number, run=run),
        }, json.loads(resp.content))


class TestSettingsHandlerForGet(CourseTestCase):
    def setUp(self):
        super(TestSettingsHandlerForGet, self).setUp()
        self.course_details_url = reverse_course_url('settings_handler', self.course.id)

    def test_html_text(self):
        """
        settings_handler to html/text and get method
        check return json in custom_logo_asset_path
        """

        response = self.client.get_json(self.course_details_url)
        whole_model = json.loads(response.content)
        self.assertIn('custom_logo_name', whole_model)
        self.assertEqual(whole_model['custom_logo_name'], '')

    def test_app_json_for_get(self):
        """
        settings_handler to application/json and get method
        check return json in custom_logo_asset_path
        """

        response = self.client.get(self.course_details_url, HTTP_ACCEPT='application/json')
        whole_model = json.loads(response.content)
        self.assertIn('custom_logo_name', whole_model)
        self.assertEqual(whole_model['custom_logo_name'], '')

    def test_permission(self):
        # Global staff
        response = self.client.get_html(self.course_details_url)
        self.assertEquals(response.status_code, 200)
        self.assertIn("Course Category", response.content)

        # GaGlobalCourseCreator
        switch_ga_global_course_creator(self.user)
        response = self.client.get_html(self.course_details_url)
        self.assertEquals(response.status_code, 200)
        self.assertIn("Course Category", response.content)

        # Course staff
        user = UserFactory()
        CourseStaffRole(self.course.id).add_users(user)
        self.client.login(username=user.username, password='test')
        response = self.client.get_html(self.course_details_url)
        self.assertEquals(response.status_code, 200)
        self.assertNotIn("Course Category", response.content)


class TestLibraryOption(CourseTestCase):

    def setUp(self):
        super(TestLibraryOption, self).setUp()
        self.course = CourseFactory.create()
        CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='library-for-settings',
            course_key=self.course.id,
            changed_by_id=self.user.id
        ).save()

    def test_library_listing_in_content(self):
        library_listing_url = reverse_course_url('library_listing', self.course.id)
        response = self.client.get(library_listing_url)
        self.assertIn('class="nav-item nav-manage-library"', response.content)

    def test_course_info_handler_in_content(self):
        course_info_handler_url = reverse_course_url('course_info_handler', self.course.id)
        response = self.client.get(course_info_handler_url)
        self.assertIn('class="nav-item nav-manage-library"', response.content)

    def test_grading_handler_in_content(self):
        grading_handler_url = reverse_course_url('grading_handler', self.course.id)
        response = self.client.get(grading_handler_url, HTTP_ACCEPT='text/html')
        self.assertIn('class="nav-item nav-manage-library"', response.content)

    def test_advanced_settings_handler_in_content(self):
        advanced_settings_handler_url = reverse_course_url('advanced_settings_handler', self.course.id)
        response = self.client.get(advanced_settings_handler_url, HTTP_ACCEPT='text/html')
        self.assertIn('class="nav-item nav-manage-library"', response.content)

    def test_textbooks_list_handler_in_content(self):
        textbooks_list_handler_url = reverse_course_url('textbooks_list_handler', self.course.id)
        response = self.client.get(textbooks_list_handler_url, HTTP_ACCEPT='text/html')
        self.assertIn('class="nav-item nav-manage-library"', response.content)

    def test_group_configurations_list_handler_in_content(self):
        group_configurations_list_handler_url = reverse_course_url('group_configurations_list_handler', self.course.id)
        response = self.client.get(group_configurations_list_handler_url, HTTP_ACCEPT='text/html')
        self.assertIn('class="nav-item nav-manage-library"', response.content)

    def test_library_listing_has_error(self):
        library_listing_url = reverse_course_url('library_listing', self.course.id)
        ns_user, password = self.create_non_staff_user()
        self.client.login(username=ns_user, password=password)
        response = self.client.get(library_listing_url)
        self.assertEqual(response.status_code, 403)

    def test_permission(self):
        self.url = reverse_course_url('library_listing', self.course.id)

        # Global staff
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 200)

        # GaGlobalCourseCreator
        switch_ga_global_course_creator(self.user)
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 200)

        # Course staff
        user = UserFactory()
        CourseStaffRole(self.course.id).add_users(user)
        self.client.login(username=user.username, password='test')
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 404)


class TestLibraryOptionWithGaGlobalCourseCreator(TestLibraryOption):
    def setUp(self):
        super(TestLibraryOptionWithGaGlobalCourseCreator, self).setUp()
        switch_ga_global_course_creator(self.user)


class TestCourseRerunHandler(CourseTestCase):
    def setUp(self):
        super(TestCourseRerunHandler, self).setUp()
        self.url = reverse_course_url('course_rerun_handler', self.course.id)

    def test_permission(self):
        # Global staff
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 200)

        # GaGlobalCourseCreator
        switch_ga_global_course_creator(self.user)
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 200)

        # Course staff
        user = UserFactory()
        CourseStaffRole(self.course.id).add_users(user)
        self.client.login(username=user.username, password='test')
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 403)


class TestCourseSearchIndexHandler(CourseTestCase):
    def setUp(self):
        super(TestCourseSearchIndexHandler, self).setUp()
        self.url = reverse_course_url('course_search_index_handler', self.course.id)

    def test_permission(self):
        # Global staff
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 200)

        # GaGlobalCourseCreator
        switch_ga_global_course_creator(self.user)
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 200)

        # Course staff
        user = UserFactory()
        CourseStaffRole(self.course.id).add_users(user)
        self.client.login(username=user.username, password='test')
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 403)


class TestCourseListing(CourseTestCase):
    def setUp(self):
        super(TestCourseListing, self).setUp()
        self.url = reverse('home')

    def test_has_rerun(self):
        rerun_hanler_url = reverse_course_url('course_rerun_handler', self.course.id)

        # Global staff
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 200)
        self.assertIn(rerun_hanler_url, response.content)

        # GaGlobalCourseCreator
        switch_ga_global_course_creator(self.user)
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 200)
        self.assertIn(rerun_hanler_url, response.content)

        # Course staff
        user = UserFactory()
        CourseStaffRole(self.course.id).add_users(user)
        self.client.login(username=user.username, password='test')
        response = self.client.get_html(self.url)
        self.assertEquals(response.status_code, 200)
        self.assertNotIn(rerun_hanler_url, response.content)

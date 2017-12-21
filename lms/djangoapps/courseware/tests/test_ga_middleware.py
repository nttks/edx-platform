
from datetime import timedelta
import ddt
from mock import patch

from django.utils import timezone
from django.test.utils import override_settings

from courseware.ga_middleware import CourseTerminatedCheckMiddleware, CustomLogoMiddleware
from courseware.tests.helpers import get_request_for_user, LoginEnrollmentTestCase
from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration
from student.roles import GaCourseScorerRole, GaGlobalCourseCreatorRole
from student.tests.factories import CourseAccessRoleFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@ddt.ddt
@override_settings(
    COURSE_TERMINATED_CHECK_EXCLUDE_PATH=[
        {'path': '/exclude1'},
        {'path': 'exclude2'},
    ]
)
class CourseTerminatedCheckMiddlewareTest(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests for CourseTerminatedCheckMiddleware.
    """

    def setUp(self):
        super(CourseTerminatedCheckMiddlewareTest, self).setUp()

        self.course = CourseFactory.create(start=timezone.now() - timedelta(days=10))

    def _create_request(self, is_staff, is_old_course_viewer, path):
        self.setup_user()
        self.enroll(self.course)
        if is_staff:
            self.user.is_staff = True
            self.user.save()
        if is_old_course_viewer:
            CourseAccessRoleFactory(course_id=None, user=self.user, role='ga_old_course_viewer')
        request = get_request_for_user(self.user)
        request.path = path.format(unicode(self.course.id))
        return request

    def _assert_response(self, is_blocked, response):
        if is_blocked:
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response['Location'], '/dashboard')
        else:
            self.assertIsNone(response)

    @ddt.data(
        # target
        (True, '/courses/{}/'),
        (True, '/courses/{}/info'),
        (True, '/courses/{}/courseware/'),
        (True, '/courses/{}/discussion/forum'),
        # exclude
        (False, '/courses/{}/exclude1'),
        (False, '/courses/{}/exclude2'),
        # not target
        (False, '/courses/{}'),
        (False, '/coursesX/{}/'),
        (False, '/courses/'),
        (False, '/courses/invalid-course-key/'),
    )
    @ddt.unpack
    def test_check_target_path(self, expected, path):
        request = self._create_request(False, False, path)
        is_target, course_id = CourseTerminatedCheckMiddleware()._check_target_path(request)
        if expected:
            self.assertTrue(is_target)
            self.assertEqual(course_id, unicode(self.course.id))
        else:
            self.assertFalse(is_target)
            self.assertIsNone(course_id)

    @ddt.data(
        (False, False, False, '/courses/{}/courseware/'),
        (False, True, False, '/courses/{}/courseware/'),
        (False, False, True, '/courses/{}/courseware/'),
        (False, False, False, '/courses/{}/exclude1'),
        (False, False, False, '/courses/course-v1:org+course_non_exists+run/courseware/'),
    )
    @ddt.unpack
    def test_course_opened(self, is_blocked, is_staff, is_old_course_viewer, path):
        """
        Tests that the opened course always does not block the access.
        """
        request = self._create_request(is_staff, is_old_course_viewer, path)
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self._assert_response(is_blocked, response)

    @ddt.data(
        (True, False, False, '/courses/{}/courseware/'),
        (False, True, False, '/courses/{}/courseware/'),
        (False, False, True, '/courses/{}/courseware/'),
        (False, False, False, '/courses/{}/exclude1'),
        (False, False, False, '/courses/course-v1:org+course_non_exists+run/courseware/'),
    )
    @ddt.unpack
    def test_course_terminated(self, is_blocked, is_staff, is_old_course_viewer, path):
        """
        Tests that the terminated course block the access except by staff or gaOldCourseViewer.
        """
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        request = self._create_request(is_staff, is_old_course_viewer, path)
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self._assert_response(is_blocked, response)

    @patch('openedx.core.djangoapps.ga_self_paced.api.is_course_closed', return_value=True)
    @ddt.data(
        (True, False, False, '/courses/{}/courseware/'),
        (False, True, False, '/courses/{}/courseware/'),
        (False, False, True, '/courses/{}/courseware/'),
        (False, False, False, '/courses/{}/exclude1'),
        (False, False, False, '/courses/course-v1:org+course_non_exists+run/courseware/'),
    )
    @ddt.unpack
    def test_self_paced_course_closed(self, is_blocked, is_staff, is_old_course_viewer, path, mock_is_course_closed):
        """
        Tests that the self-paced closed course block the access except by staff or gaOldCourseViewer.
        """
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)

        request = self._create_request(is_staff, is_old_course_viewer, path)
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self._assert_response(is_blocked, response)

        if is_blocked and not is_staff:
            self.assertEqual(mock_is_course_closed.call_count, 1)


class CourseTerminatedCheckMiddlewareTestWithGaGlobalCourseCreator(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests for CourseTerminatedCheckMiddleware.
    """

    def setUp(self):
        super(CourseTerminatedCheckMiddlewareTestWithGaGlobalCourseCreator, self).setUp()
        self.course = CourseFactory.create(start=timezone.now() - timedelta(days=10))

    def _create_request(self, path):
        self.setup_user()
        GaGlobalCourseCreatorRole().add_users(self.user)
        self.enroll(self.course)
        request = get_request_for_user(self.user)
        request.path = path.format(unicode(self.course.id))
        return request

    def test_course_opened(self):
        """
        Tests that the opened course always does not block the access.
        """
        request = self._create_request('/courses/{}/courseware/')
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self.assertIsNone(response)

    def test_course_terminated(self):
        """
        Tests that the terminated course the access by GaGlobalCourseCreator.
        """
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        request = self._create_request('/courses/{}/courseware/')
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self.assertIsNone(response)

    @patch('openedx.core.djangoapps.ga_self_paced.api.is_course_closed', return_value=True)
    def test_self_paced_course_closed(self, mock_is_course_closed):
        """
        Tests that the self-paced closed course the access by GaGlobalCourseCreator.
        """
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)

        request = self._create_request('/courses/{}/courseware/')
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self.assertIsNone(response)


class CourseTerminatedCheckMiddlewareTestWithGaCourseScorer(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests for CourseTerminatedCheckMiddleware.
    """

    def setUp(self):
        super(CourseTerminatedCheckMiddlewareTestWithGaCourseScorer, self).setUp()
        self.course = CourseFactory.create(start=timezone.now() - timedelta(days=10))

    def _create_request(self, path):
        self.setup_user()
        GaCourseScorerRole(self.course.id).add_users(self.user)
        self.enroll(self.course)
        request = get_request_for_user(self.user)
        request.path = path.format(unicode(self.course.id))
        return request

    def test_course_opened(self):
        """
        Tests that the opened course always does not block the access.
        """
        request = self._create_request('/courses/{}/courseware/')
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self.assertIsNone(response)

    def test_course_terminated(self):
        """
        Tests that the terminated course block the access by GaCourseScorer.
        """
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        request = self._create_request('/courses/{}/courseware/')
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self.assertEquals(response.status_code, 302)

    @patch('openedx.core.djangoapps.ga_self_paced.api.is_course_closed', return_value=True)
    def test_self_paced_course_closed(self, mock_is_course_closed):
        """
        Tests that the self-paced closed course the access by GaCourseScorer.
        """
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)

        request = self._create_request('/courses/{}/courseware/')
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self.assertIsNone(response)


@ddt.ddt
class CourseTerminatedCheckViewTest(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests for the courseware view to confirm the execute CourseTerminatedCheckMiddleware.
    """

    def setUp(self):
        super(CourseTerminatedCheckViewTest, self).setUp()

        self.course = CourseFactory.create(start=timezone.now() - timedelta(days=10))

    def _assert_response(self, is_blocked, response):
        if is_blocked:
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response['Location'], 'http://testserver/dashboard')
        else:
            self.assertEqual(response.status_code, 200)

    def _assert_redirect_login(self, response):
        next_path = '/courses/{}/progress'.format(unicode(self.course.id))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'http://testserver/login?next={}'.format(next_path))

    def _access_page(self, is_staff, is_old_course_viewer, is_anonymous=False):
        if not is_anonymous:
            self.setup_user()
            self.enroll(self.course)
            if is_staff:
                self.user.is_staff = True
                self.user.save()
            if is_old_course_viewer:
                CourseAccessRoleFactory(course_id=None, user=self.user, role='ga_old_course_viewer')
        path = '/courses/{}/progress'.format(unicode(self.course.id))
        return self.client.get(path)

    @ddt.data((False, False, False), (False, True, False), (False, False, True))
    @ddt.unpack
    def test_course_opened(self, is_blocked, is_staff, is_old_course_viewer):
        response = self._access_page(is_staff, is_old_course_viewer)
        self._assert_response(is_blocked, response)

    def test_course_opened_not_logged_in(self):
        response = self._access_page(False, False, True)
        self._assert_redirect_login(response)

    @ddt.data((True, False, False), (False, True, False), (False, False, True))
    @ddt.unpack
    def test_course_terminated(self, is_blocked, is_staff, is_old_course_viewer):
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        response = self._access_page(is_staff, is_old_course_viewer)
        self._assert_response(is_blocked, response)

    def test_course_terminated_not_logged_in(self):
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        response = self._access_page(False, False, True)
        self._assert_response(True, response)

    @patch('openedx.core.djangoapps.ga_self_paced.api.is_course_closed', return_value=True)
    @ddt.data((True, False, False), (False, True, False), (False, False, True))
    @ddt.unpack
    def test_self_paced_course_closed(self, is_blocked, is_staff, is_old_course_viewer, mock_is_course_closed):
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)

        response = self._access_page(is_staff, is_old_course_viewer)
        self._assert_response(is_blocked, response)

        if is_blocked and not is_staff:
            self.assertEqual(mock_is_course_closed.call_count, 1)

    def test_self_paced_course_closed_not_logged_in(self):
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)

        response = self._access_page(False, False, True)
        self._assert_redirect_login(response)


class CourseTerminatedCheckViewTestWithGaGlobalCourseCreator(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests for the courseware view to confirm the execute CourseTerminatedCheckMiddleware.
    """

    def setUp(self):
        super(CourseTerminatedCheckViewTestWithGaGlobalCourseCreator, self).setUp()

        self.course = CourseFactory.create(start=timezone.now() - timedelta(days=10))

    def _access_page(self):
        self.setup_user()
        GaGlobalCourseCreatorRole().add_users(self.user)
        self.enroll(self.course)
        path = '/courses/{}/progress'.format(unicode(self.course.id))
        return self.client.get(path)

    def test_course_opened(self):
        response = self._access_page()
        self.assertEqual(response.status_code, 200)

    def test_course_terminated(self):
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        response = self._access_page()
        self.assertEqual(response.status_code, 200)

    @patch('openedx.core.djangoapps.ga_self_paced.api.is_course_closed', return_value=True)
    def test_self_paced_course_closed(self, mock_is_course_closed):
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)

        response = self._access_page()
        self.assertEqual(response.status_code, 200)


class CourseTerminatedCheckViewTestWithGaCourseScorer(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests for the courseware view to confirm the execute CourseTerminatedCheckMiddleware.
    """

    def setUp(self):
        super(CourseTerminatedCheckViewTestWithGaCourseScorer, self).setUp()

        self.course = CourseFactory.create(start=timezone.now() - timedelta(days=10))

    def _access_page(self):
        self.setup_user()
        GaCourseScorerRole(self.course.id).add_users(self.user)
        self.enroll(self.course)
        path = '/courses/{}/progress'.format(unicode(self.course.id))
        return self.client.get(path)

    def test_course_opened(self):
        response = self._access_page()
        self.assertEqual(response.status_code, 200)

    def test_course_terminated(self):
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        response = self._access_page()
        self.assertEqual(response.status_code, 302)

    @patch('openedx.core.djangoapps.ga_self_paced.api.is_course_closed', return_value=True)
    def test_self_paced_course_closed(self, mock_is_course_closed):
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)

        response = self._access_page()
        self.assertEqual(response.status_code, 200)


class CustomLogoMiddlewareTest(LoginEnrollmentTestCase, ModuleStoreTestCase):

    def setUp(self):
        super(CustomLogoMiddlewareTest, self).setUp()

        self.course = CourseFactory.create(start=timezone.now() - timedelta(days=10), custom_logo='dummy.png')

    def _create_request(self, is_staff, path):
        self.setup_user()
        self.enroll(self.course)
        if is_staff:
            self.user.is_staff = True
            self.user.save()
        request = get_request_for_user(self.user)
        request.path = path.format(unicode(self.course.id))
        return request

    def test_check_custom_logo_for_info(self):
        request = self._create_request(False, '/courses/{}/info')
        self.course_optional_configuration = CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='custom-logo-for-settings',
            course_key=self.course.id,
            changed_by_id=self.user.id
        )
        self.course_optional_configuration.save()

        CustomLogoMiddleware().process_request(request)

        self.assertIn('custom_logo_enabled', request.__dict__)
        self.assertTrue(request.custom_logo_enabled)

    def test_check_custom_logo_for_about(self):
        request = self._create_request(False, '/courses/{}/about/')
        self.course_optional_configuration = CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='custom-logo-for-settings',
            course_key=self.course.id,
            changed_by_id=self.user.id
        )
        self.course_optional_configuration.save()

        CustomLogoMiddleware().process_request(request)

        self.assertTrue(request.custom_logo_enabled)

    def test_check_custom_logo_for_login(self):
        request = self._create_request(False, '/login')
        self.course_optional_configuration = CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=True,
            key='custom-logo-for-settings',
            course_key=self.course.id,
            changed_by_id=self.user.id
        )
        self.course_optional_configuration.save()

        CustomLogoMiddleware().process_request(request)

        self.assertNotIn('custom_logo_enabled', request.__dict__)

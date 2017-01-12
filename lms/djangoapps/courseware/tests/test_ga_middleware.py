
from datetime import timedelta
import ddt
from mock import patch

from django.utils import timezone
from django.test.utils import override_settings

from courseware.ga_middleware import CourseTerminatedCheckMiddleware
from courseware.tests.helpers import get_request_for_user, LoginEnrollmentTestCase
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

    def _create_request(self, is_staff, path):
        self.setup_user()
        self.enroll(self.course)
        if is_staff:
            self.user.is_staff = True
            self.user.save()
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
        request = self._create_request(False, path)
        is_target, course_id = CourseTerminatedCheckMiddleware()._check_target_path(request)
        if expected:
            self.assertTrue(is_target)
            self.assertEqual(course_id, unicode(self.course.id))
        else:
            self.assertFalse(is_target)
            self.assertIsNone(course_id)

    @ddt.data(
        (False, False, '/courses/{}/courseware/'),
        (False, True, '/courses/{}/courseware/'),
        (False, False, '/courses/{}/exclude1'),
        (False, False, '/courses/course-v1:org+course_non_exists+run/courseware/'),
    )
    @ddt.unpack
    def test_course_opened(self, is_blocked, is_staff, path):
        """
        Tests that the opened course always does not block the access.
        """
        request = self._create_request(is_staff, path)
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self._assert_response(is_blocked, response)

    @ddt.data(
        (True, False, '/courses/{}/courseware/'),
        (False, True, '/courses/{}/courseware/'),
        (False, False, '/courses/{}/exclude1'),
        (False, False, '/courses/course-v1:org+course_non_exists+run/courseware/'),
    )
    @ddt.unpack
    def test_course_terminated(self, is_blocked, is_staff, path):
        """
        Tests that the terminated course block the access except by staff.
        """
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        request = self._create_request(is_staff, path)
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self._assert_response(is_blocked, response)

    @patch('openedx.core.djangoapps.ga_self_paced.api.is_course_closed', return_value=True)
    @ddt.data(
        (True, False, '/courses/{}/courseware/'),
        (False, True, '/courses/{}/courseware/'),
        (False, False, '/courses/{}/exclude1'),
        (False, False, '/courses/course-v1:org+course_non_exists+run/courseware/'),
    )
    @ddt.unpack
    def test_self_paced_course_closed(self, is_blocked, is_staff, path, mock_is_course_closed):
        """
        Tests that the self-paced closed course block the access except by staff.
        """
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)

        request = self._create_request(is_staff, path)
        response = CourseTerminatedCheckMiddleware().process_request(request)
        self._assert_response(is_blocked, response)

        if is_blocked and not is_staff:
            self.assertEqual(mock_is_course_closed.call_count, 1)


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

    def _access_page(self, is_staff):
        self.setup_user()
        self.enroll(self.course)
        if is_staff:
            self.user.is_staff = True
            self.user.save()
        path = '/courses/{}/progress'.format(unicode(self.course.id))
        return self.client.get(path)

    @ddt.data((False, False), (False, True))
    @ddt.unpack
    def test_course_opened(self, is_blocked, is_staff):
        response = self._access_page(is_staff)
        self._assert_response(is_blocked, response)

    @ddt.data((True, False), (False, True))
    @ddt.unpack
    def test_course_terminated(self, is_blocked, is_staff):
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        response = self._access_page(is_staff)
        self._assert_response(is_blocked, response)

    @patch('openedx.core.djangoapps.ga_self_paced.api.is_course_closed', return_value=True)
    @ddt.data((True, False), (False, True))
    @ddt.unpack
    def test_self_paced_course_closed(self, is_blocked, is_staff, mock_is_course_closed):
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)

        response = self._access_page(is_staff)
        self._assert_response(is_blocked, response)

        if is_blocked and not is_staff:
            self.assertEqual(mock_is_course_closed.call_count, 1)


from datetime import timedelta
import ddt
from mock import patch

from django.utils import timezone
from django.test.utils import override_settings

from courseware.tabs import get_course_tab_list
from courseware.tests.helpers import get_request_for_user, LoginEnrollmentTestCase
from courseware.tests.test_tabs import TabTestCase


@ddt.ddt
class CourseTerminatedCheckTabTest(LoginEnrollmentTestCase, TabTestCase):

    def _create_request(self, is_staff=False):
        self.setup_user()
        self.enroll(self.course)
        if is_staff:
            self.user.is_staff = True
            self.user.save()
        return get_request_for_user(self.user)

    def _assert_tabs(self, tabs, is_blocked, is_staff, exclude_tabs=[]):
        if is_blocked:
            expected = exclude_tabs
        elif is_staff:
            expected = ['courseware', 'course_info', 'wiki', 'progress', 'instructor']
        else:
            expected = ['courseware', 'course_info', 'wiki', 'progress']
        tab_types = [tab.type for tab in tabs]
        self.assertItemsEqual(tab_types, expected)

    @ddt.data((False, False), (False, True))
    @ddt.unpack
    def test_course_opened(self, is_blocked, is_staff):
        request = self._create_request(is_staff)
        tab_list = get_course_tab_list(request, self.course)
        self._assert_tabs(tab_list, is_blocked, is_staff)

    @ddt.data((True, False), (False, True))
    @ddt.unpack
    def test_course_terminated(self, is_blocked, is_staff):
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        request = self._create_request(is_staff)
        tab_list = get_course_tab_list(request, self.course)
        self._assert_tabs(tab_list, is_blocked, is_staff)

    @override_settings(COURSE_TERMINATED_CHECK_EXCLUDE_PATH=[{'tab': 'course_info'}])
    def test_course_terminated_with_exclude_settings(self):
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)

        request = self._create_request()
        tab_list = get_course_tab_list(request, self.course)
        self._assert_tabs(tab_list, True, False, ['course_info'])

    @patch('openedx.core.djangoapps.ga_self_paced.api.is_course_closed', return_value=True)
    @ddt.data((True, False), (False, True))
    @ddt.unpack
    def test_self_paced_course_closed(self, is_blocked, is_staff, mock_is_course_closed):
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)

        request = self._create_request(is_staff)
        tab_list = get_course_tab_list(request, self.course)
        self._assert_tabs(tab_list, is_blocked, is_staff)

        if is_blocked and not is_staff:
            self.assertEqual(mock_is_course_closed.call_count, 4)

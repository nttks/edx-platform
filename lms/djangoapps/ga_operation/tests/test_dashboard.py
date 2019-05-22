from courseware.tests.factories import GlobalStaffFactory
from student.tests.factories import CourseAccessRoleFactory
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from django.core.urlresolvers import reverse

from lms.djangoapps.courseware.tests.helpers import LoginEnrollmentTestCase


class UserDashBoardMethodTest(LoginEnrollmentTestCase):

    def setUp(self):
        super(UserDashBoardMethodTest, self).setup_user()

    def _user_dashboard(self):
        return reverse('ga_operation_user_dashboard')

    def _create_course_overview(self):
        return CourseOverview.objects.create(
            id='course-v1:org+course+run',
            _location='block-v1:demo+de001+2016_05+type@course+block@course',
            org='test',
            display_name='test_name',
            display_number_with_default='test',
            display_org_with_default='test',
            course_image_url='test',
            cert_name_short='test',
            cert_name_long='test',
            _pre_requisite_courses_json=[],
            version=5,
            modified='2018-09-06 4:09:40',
            created='2018-09-06 4:09:40',
            has_any_active_web_certificate=0,
            certificates_display_behavior=0,
            certificates_show_before_end=0,
            mobile_available=0,
            visible_to_staff_only=0,
            cert_html_view_enabled=0,
            invitation_only=0,
        )

    def test_is_staff_user(self):
        global_user = GlobalStaffFactory()
        self.client.login(username=global_user.username, password='test')
        response = self.client.get(self._user_dashboard())

        self.assertEqual(302, response.status_code)
        self.assertIn('ga_operation', response.url)

    def test_instructor_user(self):
        course_overview = self._create_course_overview()
        CourseAccessRoleFactory(course_id='course-v1:org+course+run', user=self.user, role='instructor')
        self.client.login(username=self.user.username, password='test')
        response = self.client.get(self._user_dashboard())

        self.assertEqual(200, response.status_code)
        self.assertIn(str(course_overview.id), response.content)
        self.assertIn(course_overview.display_name, response.content)

    def test_staff_user(self):
        course_overview = self._create_course_overview()
        CourseAccessRoleFactory(course_id='course-v1:org+course+run', user=self.user, role='staff')
        self.client.login(username=self.user.username, password='test')
        response = self.client.get(self._user_dashboard())

        self.assertEqual(200, response.status_code)
        self.assertIn(str(course_overview.id), response.content)
        self.assertIn(course_overview.display_name, response.content)

    def test_beta_testers_user(self):
        self._create_course_overview()
        CourseAccessRoleFactory(course_id='course-v1:org+course+run', user=self.user, role='beta_testers')
        self.client.login(username=self.user.username, password='test')
        response = self.client.get(self._user_dashboard())

        self.assertEqual(403, response.status_code)

    def test_non_authority_user(self):
        self.client.login(username=self.user.username, password='test')
        response = self.client.get(self._user_dashboard())

        self.assertEqual(403, response.status_code)

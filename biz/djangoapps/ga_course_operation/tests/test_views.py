import json
from mock import patch

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from instructor.tests.test_api import InstructorAPISurveyDownloadTestMixin
from student.models import NonExistentCourseError
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from biz.djangoapps.util.tests.testcase import BizViewTestBase


class CourseOperationViewsTest(BizViewTestBase, ModuleStoreTestCase):

    def _url_dashboard(self, course):
        return reverse('biz:course_operation:dashboard', kwargs={'course_id': course.id})

    def _url_register_students(self, course):
        return reverse('biz:course_operation:register_students', kwargs={'course_id': course.id})

    def setUp(self):
        super(CourseOperationViewsTest, self).setUp()

        self.course_spoc1 = CourseFactory.create(org='org1', number='course1', run='run1')
        self.course_spoc2 = CourseFactory.create(org='org2', number='course2', run='run2')


class CourseOperationDashboardTest(CourseOperationViewsTest):

    def test_403(self):
        self.setup_user()
        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.assert_request_status_code(403, self._url_dashboard(self.course_spoc2))

    def test_success(self):
        self.setup_user()
        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.assert_request_status_code(200, self._url_dashboard(self.course_spoc1))


class CourseOperationRegisterTest(CourseOperationViewsTest):

    def test_course_unmatch(self):
        self.setup_user()
        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.assert_request_status_code(200, self._url_register_students(self.course_spoc2))
        data = json.loads(response.content)
        self.assertNotEqual(len(data['general_errors']), 0)
        self.assertEqual(data['general_errors'][0]['response'], 'Current course is changed. Please reload this page.')

    def test_no_param(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'file_not_found': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['general_errors']), 0)
        self.assertEquals(data['general_errors'][0]['response'], 'Could not find student list.')

    def test_no_student(self):
        self.setup_user()
        csv_content = ""

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['general_errors']), 0)
        self.assertEquals(data['general_errors'][0]['response'], 'Could not find student list.')

    def test_validation(self):
        self.setup_user()
        csv_content = "test_student1@example.com,t,t"

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], ' '.join(['Username must be minimum of two characters long', 'Your legal name must be a minimum of two characters long']))

    @patch('biz.djangoapps.ga_course_operation.views.log.info')
    def test_account_creation(self, info_log):
        self.setup_user()
        csv_content = "test_student@example.com,test_student_1,tester1"

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)

        # test the log for email that's send to new created user.
        info_log.assert_called_with('email sent to new created user at %s', 'test_student@example.com')

    @patch('biz.djangoapps.ga_course_operation.views.log.info')
    def test_account_creation_with_blank_lines(self, info_log):
        self.setup_user()
        csv_content = "\ntest_student@example.com,test_student_1,tester1\n\n"

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)

        # test the log for email that's send to new created user.
        info_log.assert_called_with('email sent to new created user at %s', 'test_student@example.com')

    @patch('biz.djangoapps.ga_course_operation.views.log.info')
    def test_email_and_username_already_exist(self, info_log):
        self.setup_user()
        csv_content = "test_student@example.com,test_student_1,tester1\n" \
                      "test_student@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)

        # test the log for email that's send to new created user.
        info_log.assert_called_with(
            u"email sent to created user at %s",
            'test_student@example.com'
        )

    def test_insufficient_data(self):
        self.setup_user()
        csv_content = "test_student@example.com,test_student_1\n"

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 1)
        self.assertEquals(data['general_errors'][0]['response'], 'Data in row #1 must have exactly three columns: email, username, and full name.')

    def test_invalid_email(self):
        self.setup_user()
        csv_content = "test_student.example.com,test_student_1,tester1"

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Invalid email {0}.'.format('test_student.example.com'))

    def test_user_with_already_existing_email(self):
        self.setup_user()
        csv_content = "{email},test_student_1,tester1\n".format(email=self.email)

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        warning_message = 'An account with email {email} exists but the registered username {username} is different.'.format(
            email=self.email, username=self.username)
        self.assertNotEquals(len(data['warnings']), 0)
        self.assertEquals(data['warnings'][0]['response'], warning_message)

    def test_user_with_already_existing_username(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Username {user} already exists.'.format(user='test_student_1'))

    def test_raising_exception_in_auto_registration_case(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_course=self.course_spoc1), patch('biz.djangoapps.ga_course_operation.views._do_create_account', side_effect=Exception()):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Exception')

    def test_users_created_successfully_if_others_fail(self):

        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student3@example.com,test_student_1,tester3\n" \
                      "test_student2@example.com,test_student_2,tester2"

        with self.skip_check_course_selection(current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students(self.course_spoc1), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Username {user} already exists.'.format(user='test_student_1'))
        self.assertTrue(User.objects.filter(username='test_student_1', email='test_student1@example.com').exists())
        self.assertTrue(User.objects.filter(username='test_student_2', email='test_student2@example.com').exists())
        self.assertFalse(User.objects.filter(email='test_student3@example.com').exists())


class CourseOperationSurveyTest(InstructorAPISurveyDownloadTestMixin, CourseOperationViewsTest):
    """
    Test instructor survey for biz endpoint.
    """

    url = 'biz:course_operation:get_survey'

    def test_get_survey(self):
        with self.skip_check_course_selection():
            super(CourseOperationSurveyTest, self).test_get_survey()

    def test_get_survey_when_data_is_empty(self):
        with self.skip_check_course_selection():
            super(CourseOperationSurveyTest, self).test_get_survey_when_data_is_empty()

    def test_get_survey_when_data_is_broken(self):
        with self.skip_check_course_selection():
            super(CourseOperationSurveyTest, self).test_get_survey_when_data_is_broken()

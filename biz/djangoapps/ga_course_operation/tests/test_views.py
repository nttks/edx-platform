import json
from mock import patch

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from instructor.tests.test_api import InstructorAPISurveyDownloadTestMixin

from biz.djangoapps.ga_invitation.models import ContractRegister, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.util.tests.testcase import BizViewTestBase


class CourseOperationViewsTest(BizContractTestBase):

    def test_register_students(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.assert_request_status_code(200, reverse('biz:course_operation:register_students'))

    def _url_register_students_ajax(self):
        return reverse('biz:course_operation:register_students_ajax')

    def test_contract_unmatch(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract_mooc.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEqual(len(data['general_errors']), 0)
        self.assertEqual(data['general_errors'][0]['response'], 'Current contract is changed. Please reload this page.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_no_param(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['general_errors']), 0)
        self.assertEquals(data['general_errors'][0]['response'], 'Unauthorized access.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_no_param_students_list(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract_mooc.id})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['general_errors']), 0)
        self.assertEquals(data['general_errors'][0]['response'], 'Unauthorized access.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_no_param_contract_id(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['general_errors']), 0)
        self.assertEquals(data['general_errors'][0]['response'], 'Unauthorized access.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_no_student(self):
        self.setup_user()
        csv_content = ""

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['general_errors']), 0)
        self.assertEquals(data['general_errors'][0]['response'], 'Could not find student list.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_validation(self):
        self.setup_user()
        csv_content = "test_student1@example.com,t,t"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], ' '.join(['Username must be minimum of two characters long', 'Your legal name must be a minimum of two characters long']))

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    @patch('biz.djangoapps.ga_course_operation.views.log.info')
    def test_account_creation(self, info_log):
        self.setup_user()
        csv_content = "test_student@example.com,test_student_1,tester1"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)

        self.assertTrue(ContractRegister.objects.filter(user__email='test_student@example.com', contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email='test_student@example.com', contract=self.contract).status, INPUT_INVITATION_CODE)

        # test the log for email that's send to new created user.
        info_log.assert_called_with('email sent to new created user at %s', 'test_student@example.com')

    @patch('biz.djangoapps.ga_course_operation.views.log.info')
    def test_account_creation_with_blank_lines(self, info_log):
        self.setup_user()
        csv_content = "\ntest_student@example.com,test_student_1,tester1\n\n"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)

        self.assertTrue(ContractRegister.objects.filter(user__email='test_student@example.com', contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email='test_student@example.com', contract=self.contract).status, INPUT_INVITATION_CODE)

        # test the log for email that's send to new created user.
        info_log.assert_called_with('email sent to new created user at %s', 'test_student@example.com')

    @patch('biz.djangoapps.ga_course_operation.views.log.info')
    def test_email_and_username_already_exist(self, info_log):
        self.setup_user()
        csv_content = "test_student@example.com,test_student_1,tester1\n" \
                      "test_student@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)

        self.assertTrue(ContractRegister.objects.filter(user__email='test_student@example.com', contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email='test_student@example.com', contract=self.contract).status, INPUT_INVITATION_CODE)

        # test the log for email that's send to new created user.
        info_log.assert_called_with(
            u"email sent to created user at %s",
            'test_student@example.com'
        )

    def test_insufficient_data(self):
        self.setup_user()
        csv_content = "test_student@example.com,test_student_1\n"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 1)
        self.assertEquals(data['general_errors'][0]['response'], 'Data in row #1 must have exactly three columns: email, username, and full name.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_invalid_email(self):
        self.setup_user()
        csv_content = "test_student.example.com,test_student_1,tester1"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Invalid email {0}.'.format('test_student.example.com'))

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_user_with_already_existing_email(self):
        self.setup_user()
        csv_content = "{email},test_student_1,tester1\n".format(email=self.email)

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        warning_message = 'An account with email {email} exists but the registered username {username} is different.'.format(
            email=self.email, username=self.username)
        self.assertNotEquals(len(data['warnings']), 0)
        self.assertEquals(data['warnings'][0]['response'], warning_message)

        self.assertTrue(ContractRegister.objects.filter(user__email=self.email, contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=self.contract).status, INPUT_INVITATION_CODE)

    def test_user_with_already_existing_contract_register_input(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=INPUT_INVITATION_CODE)
        csv_content = "{email},test_student_1,tester1\n".format(email=self.email)

        self.assertTrue(ContractRegister.objects.filter(user__email=self.email, contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=self.contract).status, INPUT_INVITATION_CODE)
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        warning_message = 'An account with email {email} exists but the registered username {username} is different.'.format(
            email=self.email, username=self.username)
        self.assertNotEquals(len(data['warnings']), 0)
        self.assertEquals(data['warnings'][0]['response'], warning_message)

        self.assertTrue(ContractRegister.objects.filter(user__email=self.email, contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=self.contract).status, INPUT_INVITATION_CODE)

    def test_user_with_already_existing_contract_register_register(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        csv_content = "{email},test_student_1,tester1\n".format(email=self.email)

        self.assertTrue(ContractRegister.objects.filter(user__email=self.email, contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=self.contract).status, REGISTER_INVITATION_CODE)
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        warning_message = 'An account with email {email} exists but the registered username {username} is different.'.format(
            email=self.email, username=self.username)
        self.assertNotEquals(len(data['warnings']), 0)
        self.assertEquals(data['warnings'][0]['response'], warning_message)

        self.assertTrue(ContractRegister.objects.filter(user__email=self.email, contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=self.contract).status, REGISTER_INVITATION_CODE)

    def test_user_with_already_existing_username(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Username {user} already exists.'.format(user='test_student_1'))

        self.assertTrue(ContractRegister.objects.filter(user__email='test_student1@example.com', contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email='test_student1@example.com', contract=self.contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=self.contract).exists())

    def test_raising_exception_in_auto_registration_case(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1), patch('biz.djangoapps.ga_course_operation.views._do_create_account', side_effect=Exception()):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Exception')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_users_created_successfully_if_others_fail(self):

        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student3@example.com,test_student_1,tester3\n" \
                      "test_student2@example.com,test_student_2,tester2"

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Username {user} already exists.'.format(user='test_student_1'))
        self.assertTrue(User.objects.filter(username='test_student_1', email='test_student1@example.com').exists())
        self.assertTrue(User.objects.filter(username='test_student_2', email='test_student2@example.com').exists())
        self.assertFalse(User.objects.filter(email='test_student3@example.com').exists())

        self.assertTrue(ContractRegister.objects.filter(user__email='test_student1@example.com', contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email='test_student1@example.com', contract=self.contract).status, INPUT_INVITATION_CODE)
        self.assertTrue(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email='test_student2@example.com', contract=self.contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=self.contract).exists())

    def test_survey(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            response = self.assert_request_status_code(200, reverse('biz:course_operation:survey'))


class CourseOperationSurveyDownloadTest(InstructorAPISurveyDownloadTestMixin, BizContractTestBase):
    """
    Test instructor survey for biz endpoint.
    """

    def get_url(self):
        return reverse('biz:course_operation:survey_download')

    def test_get_survey(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            super(CourseOperationSurveyDownloadTest, self).test_get_survey()

    def test_get_survey_when_data_is_empty(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            super(CourseOperationSurveyDownloadTest, self).test_get_survey_when_data_is_empty()

    def test_get_survey_when_data_is_broken(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            super(CourseOperationSurveyDownloadTest, self).test_get_survey_when_data_is_broken()

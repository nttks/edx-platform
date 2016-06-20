"""
Test for contract_operation feature
"""
import json
from mock import patch

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import IntegrityError

from biz.djangoapps.ga_invitation.models import ContractRegister, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from student.models import CourseEnrollment


class ContractOperationViewTest(BizContractTestBase):

    def test_register_students(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.assert_request_status_code(200, reverse('biz:contract_operation:register_students'))

    def _url_register_students_ajax(self):
        return reverse('biz:contract_operation:register_students_ajax')

    def test_register_contract_unmatch(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract_mooc.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEqual(len(data['general_errors']), 0)
        self.assertEqual(data['general_errors'][0]['response'], 'Current contract is changed. Please reload this page.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_register_no_param(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['general_errors']), 0)
        self.assertEquals(data['general_errors'][0]['response'], 'Unauthorized access.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_register_no_param_students_list(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract_mooc.id})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['general_errors']), 0)
        self.assertEquals(data['general_errors'][0]['response'], 'Unauthorized access.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_register_no_param_contract_id(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['general_errors']), 0)
        self.assertEquals(data['general_errors'][0]['response'], 'Unauthorized access.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_register_no_student(self):
        self.setup_user()
        csv_content = ""

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['general_errors']), 0)
        self.assertEquals(data['general_errors'][0]['response'], 'Could not find student list.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_register_validation(self):
        self.setup_user()
        csv_content = "test_student1@example.com,t,t"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], ' '.join(['Username must be minimum of two characters long', 'Your legal name must be a minimum of two characters long']))

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_register_account_creation(self):
        self.setup_user()
        csv_content = "test_student@example.com,test_student_1,tester1"

        with self.skip_check_course_selection(current_contract=self.contract), patch('biz.djangoapps.ga_contract_operation.views.log.info') as info_log:
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
            # test the log for email that's send to new created user.
            info_log.assert_called_with('email sent to new created user at %s', 'test_student@example.com')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)

        self.assertTrue(ContractRegister.objects.filter(user__email='test_student@example.com', contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email='test_student@example.com', contract=self.contract).status, INPUT_INVITATION_CODE)

    def test_register_account_creation_with_blank_lines(self):
        self.setup_user()
        csv_content = "\ntest_student@example.com,test_student_1,tester1\n\n"

        with self.skip_check_course_selection(current_contract=self.contract), patch('biz.djangoapps.ga_contract_operation.views.log.info') as info_log:
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
            # test the log for email that's send to new created user.
            info_log.assert_called_with('email sent to new created user at %s', 'test_student@example.com')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)

        self.assertTrue(ContractRegister.objects.filter(user__email='test_student@example.com', contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email='test_student@example.com', contract=self.contract).status, INPUT_INVITATION_CODE)

    def test_register_email_and_username_already_exist(self):
        self.setup_user()
        csv_content = "test_student@example.com,test_student_1,tester1\n" \
                      "test_student@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract), patch('biz.djangoapps.ga_contract_operation.views.log.info') as info_log:
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
            # test the log for email that's send to new created user.
            info_log.assert_called_with(
                u"email sent to created user at %s",
                'test_student@example.com'
            )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertTrue(User.objects.get(email='test_student@example.com').is_active)

        self.assertTrue(ContractRegister.objects.filter(user__email='test_student@example.com', contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email='test_student@example.com', contract=self.contract).status, INPUT_INVITATION_CODE)

    def test_register_insufficient_data(self):
        self.setup_user()
        csv_content = "test_student@example.com,test_student_1\n"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 1)
        self.assertEquals(data['general_errors'][0]['response'], 'Data in row #1 must have exactly three columns: email, username, and full name.')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_register_invalid_email(self):
        self.setup_user()
        csv_content = "test_student.example.com,test_student_1,tester1"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(len(data['warnings']), 0)
        self.assertEquals(len(data['general_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Invalid email {0}.'.format('test_student.example.com'))

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_register_user_with_already_existing_email(self):
        self.setup_user()
        csv_content = "{email},test_student_1,tester1\n".format(email=self.email)

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        warning_message = 'An account with email {email} exists but the registered username {username} is different.'.format(
            email=self.email, username=self.username)
        self.assertNotEquals(len(data['warnings']), 0)
        self.assertEquals(data['warnings'][0]['response'], warning_message)

        self.assertTrue(ContractRegister.objects.filter(user__email=self.email, contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=self.contract).status, INPUT_INVITATION_CODE)

    def test_register_user_with_already_existing_contract_register_input(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=INPUT_INVITATION_CODE)
        csv_content = "{email},test_student_1,tester1\n".format(email=self.email)

        self.assertTrue(ContractRegister.objects.filter(user__email=self.email, contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=self.contract).status, INPUT_INVITATION_CODE)
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        warning_message = 'An account with email {email} exists but the registered username {username} is different.'.format(
            email=self.email, username=self.username)
        self.assertNotEquals(len(data['warnings']), 0)
        self.assertEquals(data['warnings'][0]['response'], warning_message)

        self.assertTrue(ContractRegister.objects.filter(user__email=self.email, contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=self.contract).status, INPUT_INVITATION_CODE)

    def test_register_user_with_already_existing_contract_register_register(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        csv_content = "{email},test_student_1,tester1\n".format(email=self.email)

        self.assertTrue(ContractRegister.objects.filter(user__email=self.email, contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=self.contract).status, REGISTER_INVITATION_CODE)
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        warning_message = 'An account with email {email} exists but the registered username {username} is different.'.format(
            email=self.email, username=self.username)
        self.assertNotEquals(len(data['warnings']), 0)
        self.assertEquals(data['warnings'][0]['response'], warning_message)

        self.assertTrue(ContractRegister.objects.filter(user__email=self.email, contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email=self.email, contract=self.contract).status, REGISTER_INVITATION_CODE)

    def test_register_user_with_already_existing_username(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Username {user} already exists.'.format(user='test_student_1'))

        self.assertTrue(ContractRegister.objects.filter(user__email='test_student1@example.com', contract=self.contract).exists())
        self.assertEquals(ContractRegister.objects.get(user__email='test_student1@example.com', contract=self.contract).status, INPUT_INVITATION_CODE)
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=self.contract).exists())

    def test_register_raising_exception_in_auto_registration_case(self):
        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student2@example.com,test_student_1,tester2"

        with self.skip_check_course_selection(current_contract=self.contract), patch('biz.djangoapps.ga_contract_operation.views._do_create_account', side_effect=Exception()):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotEquals(len(data['row_errors']), 0)
        self.assertEquals(data['row_errors'][0]['response'], 'Exception')

        self.assertFalse(ContractRegister.objects.filter(contract=self.contract).exists())

    def test_register_users_created_successfully_if_others_fail(self):

        self.setup_user()
        csv_content = "test_student1@example.com,test_student_1,tester1\n" \
                      "test_student3@example.com,test_student_1,tester3\n" \
                      "test_student2@example.com,test_student_2,tester2"

        with self.skip_check_course_selection(current_contract=self.contract):
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

    def test_students(self):
        self.setup_user()
        # view student management
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.assert_request_status_code(200, reverse('biz:contract_operation:students'))
        self.assertNotIn(str(self.user.email), response.content)

        # register
        self.create_contract_register(self.user, self.contract)

        # view student management
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.assert_request_status_code(200, reverse('biz:contract_operation:students'))
        self.assertIn(str(self.user.email), response.content)

    def _url_unregister_students_ajax(self):
        return reverse('biz:contract_operation:unregister_students_ajax')

    def test_unregister_get(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=INPUT_INVITATION_CODE)

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.get(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 405)

    def test_unregister_no_param(self):
        self.setup_user()

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_unregister_contract_unmatch(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=INPUT_INVITATION_CODE)

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract_mooc.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Current contract is changed. Please reload this page.')

    def test_unregister_validate_not_found_register(self):
        self.setup_user()
        register_mooc = ContractRegisterFactory.create(user=self.user, contract=self.contract_mooc, status=INPUT_INVITATION_CODE)

        with self.skip_check_course_selection(current_contract=self.contract), patch('biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register_mooc.id]})
            warning_log.assert_called_with('Not found register in contract_id({}) contract_register_id({}), user_id({})'.format(self.contract.id, register_mooc.id, self.user.id))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_unregister_validate_warning(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=UNREGISTER_INVITATION_CODE)

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['info'], 'Succeed to unregister 0 users.Already unregisterd 1 users.')

    def test_unregister_spoc(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['info'], 'Succeed to unregister 1 users.')

        self.assertEquals(ContractRegister.objects.get(user=self.user, contract=self.contract).status, UNREGISTER_INVITATION_CODE)
        self.assertFalse(CourseEnrollment.is_enrolled(self.user, self.course_spoc1.id))
        self.assertFalse(CourseEnrollment.is_enrolled(self.user, self.course_spoc2.id))

    def test_unregister_mooc(self):
        self.setup_user()
        register_mooc = ContractRegisterFactory.create(user=self.user, contract=self.contract_mooc, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_mooc1.id)

        with self.skip_check_course_selection(current_contract=self.contract_mooc):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract_mooc.id, 'target_list': [register_mooc.id]})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['info'], 'Succeed to unregister 1 users.')

        self.assertEquals(ContractRegister.objects.get(user=self.user, contract=self.contract_mooc).status, UNREGISTER_INVITATION_CODE)
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_mooc1.id))

    def test_unregister_spoc_staff(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['info'], 'Succeed to unregister 1 users.')

        self.assertEquals(ContractRegister.objects.get(user=self.user, contract=self.contract).status, UNREGISTER_INVITATION_CODE)
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc1.id))
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc2.id))

    def test_unregister_spoc_staff(self):
        self.setup_user()
        # to be staff
        self.user.is_staff = True
        self.user.save()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['info'], 'Succeed to unregister 1 users.')

        self.assertEquals(ContractRegister.objects.get(user=self.user, contract=self.contract).status, UNREGISTER_INVITATION_CODE)
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc1.id))
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc2.id))

    def test_unregister_db_error(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)

        with self.skip_check_course_selection(current_contract=self.contract), \
            patch('biz.djangoapps.ga_contract_operation.views.log.exception') as exception_log, \
            patch('biz.djangoapps.ga_contract_operation.views.ContractRegister.save', side_effect=IntegrityError()):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})
            exception_log.assert_called_with('Can not unregister. contract_id({}), unregister_list({})'.format(self.contract.id, [unicode(register.id)]))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Failed to batch unregister. Please operation again after a time delay.')

        self.assertEquals(ContractRegister.objects.get(user=self.user, contract=self.contract).status, REGISTER_INVITATION_CODE)
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc1.id))
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc2.id))

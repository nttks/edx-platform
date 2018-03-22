# -*- coding: utf-8 -*-
"""
Test for contract_operation feature
"""
from datetime import datetime, timedelta
import ddt
import hashlib
import json
from mock import patch
import pytz

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.test.utils import override_settings
from django.utils.crypto import get_random_string

from biz.djangoapps.ga_achievement.management.commands.update_biz_score_status import get_grouped_target_sections
from biz.djangoapps.ga_contract.models import AdditionalInfo
from biz.djangoapps.ga_contract_operation.models import ContractMail, ContractReminderMail, ContractTaskHistory, AdditionalInfoUpdateTaskTarget
from biz.djangoapps.ga_contract_operation.tasks import ADDITIONALINFO_UPDATE
from biz.djangoapps.ga_contract_operation.tests.factories import ContractTaskHistoryFactory, ContractTaskTargetFactory, StudentRegisterTaskTargetFactory, StudentUnregisterTaskTargetFactory
from biz.djangoapps.ga_invitation.models import ContractRegister, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.util import datetime_utils
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.tests.factories import TaskFactory
from openedx.core.lib.ga_datetime_utils import to_timezone
from student.models import CourseEnrollment
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.factories import ItemFactory

ERROR_MSG = "Test Message"


@ddt.ddt
class ContractOperationViewTest(BizContractTestBase):

    # ------------------------------------------------------------
    # Register students
    # ------------------------------------------------------------
    def test_register_students(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.assert_request_status_code(200, reverse('biz:contract_operation:register_students'))

    # ------------------------------------------------------------
    # Register students ajax
    # ------------------------------------------------------------
    def _url_register_students_ajax(self):
        return reverse('biz:contract_operation:register_students_ajax')

    def test_register_contract_unmatch(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract_mooc.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Current contract is changed. Please reload this page.')

    def test_register_validate_task_error(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], ERROR_MSG)

    def test_register_no_param(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_param_students_list(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract_mooc.id})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_param_contract_id(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_student(self):
        self.setup_user()
        csv_content = ""

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Could not find student list.')

    def test_register_student_not_allowed_method(self):
        response = self.client.get(self._url_register_students_ajax())
        self.assertEqual(405, response.status_code)

    def test_register_student_submit_successful(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)
        self.assertItemsEqual([u'Input,{}'.format(s) for s in csv_content.splitlines()], [target.student for target in history.studentregistertasktarget_set.all()])

    def test_register_student_submit_successful_register(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content, 'register_status': REGISTER_INVITATION_CODE})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)
        self.assertItemsEqual([u'Register,{}'.format(s) for s in csv_content.splitlines()], [target.student for target in history.studentregistertasktarget_set.all()])

    def test_register_student_submit_illegal_register(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content, 'register_status': UNREGISTER_INVITATION_CODE})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Invalid access.')

    def test_register_student_submit_duplicated(self):
        TaskFactory.create(task_type='student_register', task_key=hashlib.md5(str(self.contract.id)).hexdigest())
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = None
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Processing of Student Register is running.Execution status, please check from the task history.", data['error'])
        # assert not to be created new Task instance.
        self.assertEqual(1, Task.objects.count())

    @override_settings(BIZ_MAX_REGISTER_NUMBER=2)
    def test_register_students_over_max_number(self):

        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_2,テスター２\n" \
                      u"test_student3@example.com,test_student_3,テスター３"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("It has exceeded the number(2) of cases that can be a time of registration.", data['error'])

        self.assertFalse(User.objects.filter(username='test_student_1', email='test_student1@example.com').exists())
        self.assertFalse(User.objects.filter(username='test_student_2', email='test_student2@example.com').exists())
        self.assertFalse(User.objects.filter(username='test_student_3', email='test_student3@example.com').exists())

        self.assertFalse(ContractRegister.objects.filter(user__email='test_student1@example.com', contract=self.contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=self.contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=self.contract).exists())

    @override_settings(BIZ_MAX_CHAR_LENGTH_REGISTER_LINE=45)
    def test_register_students_over_max_char_length(self):

        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_2,テスター２\n" \
                      u"test_student3@example.com,test_student_3,テスター３"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("The number of lines per line has exceeded the 45 characters.", data['error'])

        self.assertFalse(User.objects.filter(username='test_student_1', email='test_student1@example.com').exists())
        self.assertFalse(User.objects.filter(username='test_student_2', email='test_student2@example.com').exists())
        self.assertFalse(User.objects.filter(username='test_student_3', email='test_student3@example.com').exists())

        self.assertFalse(ContractRegister.objects.filter(user__email='test_student1@example.com', contract=self.contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=self.contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=self.contract).exists())

    # ------------------------------------------------------------
    # Students
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # Unregister students
    # ------------------------------------------------------------
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

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_unregister_contract_unmatch(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=INPUT_INVITATION_CODE)

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract_mooc.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Current contract is changed. Please reload this page.')

    def test_unregister_validate_not_found_register(self):
        self.setup_user()
        register_mooc = ContractRegisterFactory.create(user=self.user, contract=self.contract_mooc, status=INPUT_INVITATION_CODE)

        with self.skip_check_course_selection(current_contract=self.contract), patch('biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register_mooc.id]})
            warning_log.assert_called_with('Not found register in contract_id({}) contract_register_id({}), user_id({})'.format(self.contract.id, register_mooc.id, self.user.id))

        self.assertEqual(response.status_code, 400)
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

    def test_personalinfo_mask_validate_task_error(self):
        self.setup_user()
        register = ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            response = self.client.post(self._url_unregister_students_ajax(), {'contract_id': self.contract.id, 'target_list': [register.id]})

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEquals(ERROR_MSG, data['error'])

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
            exception_log.assert_called_with('Can not unregister. contract_id({}), unregister_list({})'.format(self.contract.id, [register.id]))

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Failed to batch unregister. Please operation again after a time delay.')

        self.assertEquals(ContractRegister.objects.get(user=self.user, contract=self.contract).status, REGISTER_INVITATION_CODE)
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc1.id))
        self.assertTrue(CourseEnrollment.is_enrolled(self.user, self.course_spoc2.id))

    # ------------------------------------------------------------
    # Personalinfo Mask
    # ------------------------------------------------------------
    @property
    def _url_personalinfo_mask(self):
        return reverse('biz:contract_operation:personalinfo_mask')

    def test_personalinfo_mask_not_allowed_method(self):
        response = self.client.get(self._url_personalinfo_mask)
        self.assertEqual(405, response.status_code)

    def test_personalinfo_mask_submit_successful(self):
        """
        Tests success to submit. Processing of task is tested in test_tasks.py
        """
        registers = [
            self.create_contract_register(UserFactory.create(), self.contract),
            self.create_contract_register(UserFactory.create(), self.contract),
        ]
        params = {'target_list': [register.id for register in registers], 'contract_id': self.contract.id}

        self.setup_user()

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_personalinfo_mask, params)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Personal Information Mask.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('personalinfo_mask', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)
        self.assertItemsEqual(registers, [target.register for target in history.contracttasktarget_set.all()])

    def test_personalinfo_mask_submit_duplicated(self):
        registers = [
            self.create_contract_register(UserFactory.create(), self.contract),
            self.create_contract_register(UserFactory.create(), self.contract),
        ]
        params = {'target_list': [register.id for register in registers], 'contract_id': self.contract.id}
        TaskFactory.create(task_type='personalinfo_mask', task_key=hashlib.md5(str(self.contract.id)).hexdigest())

        self.setup_user()

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = None
            response = self.client.post(self._url_personalinfo_mask, params)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Processing of Personal Information Mask is running.Execution status, please check from the task history.", data['error'])
        # assert not to be created new Task instance.
        self.assertEqual(1, Task.objects.count())

    def test_personalinfo_mask_validate_task_error(self):
        registers = [
            self.create_contract_register(UserFactory.create(), self.contract),
            self.create_contract_register(UserFactory.create(), self.contract),
        ]
        params = {'target_list': [register.id for register in registers], 'contract_id': self.contract.id}
        TaskFactory.create(task_type='personalinfo_mask', task_key=hashlib.md5(str(self.contract.id)).hexdigest())

        self.setup_user()

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            response = self.client.post(self._url_personalinfo_mask, params)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(ERROR_MSG, data['error'])

    @ddt.data('target_list', 'contract_id')
    def test_personalinfo_mask_missing_params(self, param):
        params = {'target_list': [1, 2], 'contract_id': 1, }
        del params[param]

        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_personalinfo_mask, params)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Unauthorized access.", data['error'])

    def test_personalinfo_mask_contract_unmatch(self):
        params = {'target_list': [1, 2], 'contract_id': self.contract_mooc.id, }

        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_personalinfo_mask, params)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Current contract is changed. Please reload this page.", data['error'])

    def test_personalinfo_mask_register_unmatch(self):
        registers = [
            self.create_contract_register(UserFactory.create(), self.contract),
            self.create_contract_register(UserFactory.create(), self.contract_mooc),
        ]
        params = {'target_list': [register.id for register in registers], 'contract_id': self.contract.id, }

        self.setup_user()

        with self.skip_check_course_selection(current_contract=self.contract), patch('biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_personalinfo_mask, params)

        warning_log.assert_called_with(
            "Not found register in contract_id({}) contract_register_id({}), user_id({})".format(
                self.contract.id, registers[1].id, registers[1].user_id
            )
        )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    # ------------------------------------------------------------
    # Task History
    # ------------------------------------------------------------
    @property
    def _url_task_history_ajax(self):
        return reverse('biz:contract_operation:task_history')

    def _create_task(self, task_type, task_key, task_id, task_state, total=0, attempted=0, succeeded=0, skipped=0, failed=0):
        task_output = {
            'total': total,
            'attempted': attempted,
            'succeeded': succeeded,
            'skipped': skipped,
            'failed': failed,
        }
        return TaskFactory.create(
            task_type=task_type, task_key=task_key, task_id=task_id, task_state=task_state, task_output=json.dumps(task_output)
        )

    def _assert_task_history(self, history, recid, task_type, state, requester, created, total=0, succeeded=0, skipped=0, failed=0):
        self.assertEqual(history['recid'], recid)
        self.assertEqual(history['task_type'], task_type)
        self.assertEqual(history['task_state'], state)
        self.assertEqual(history['task_result'], "Total: {}, Success: {}, Skipped: {}, Failed: {}".format(total, succeeded, skipped, failed))
        self.assertEqual(history['requester'], requester)
        self.assertEqual(history['created'], to_timezone(created).strftime('%Y/%m/%d %H:%M:%S'))

    def test_task_history(self):
        self.setup_user()
        tasks = [
            self._create_task('personalinfo_mask', 'key1', 'task_id1', 'SUCCESS', 1, 1, 1, 0, 0),
            self._create_task('personalinfo_mask', 'key2', 'task_id2', 'FAILURE', 1, 1, 0, 1, 0),
            self._create_task('personalinfo_mask', 'key3', 'task_id3', 'QUEUING', 1, 1, 0, 0, 1),
            self._create_task('dummy_task', 'key4', 'task_id4', 'PROGRESS'),
            self._create_task('dummy_task', 'key5', 'tesk_id5', 'DUMMY'),
        ]
        # Create histories for target contract
        histories = [ContractTaskHistoryFactory.create(contract=self.contract, requester=self.user) for i in range(6)]
        _now = datetime.now(pytz.UTC)
        for i, history in enumerate(histories):
            if i < len(tasks):
                history.task_id = tasks[i].task_id
                history.created = _now + timedelta(seconds=i)
                history.save()
        # Create histories for other contract
        ContractTaskHistoryFactory.create(contract=self.contract_mooc)

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_task_history_ajax, {})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual('success', data['status'])
        self.assertEqual(5, data['total'])
        records = data['records']
        self._assert_task_history(records[0], 1, 'Unknown', 'Unknown', self.user.username, histories[4].created)
        self._assert_task_history(records[1], 2, 'Unknown', 'In Progress', self.user.username, histories[3].created)
        self._assert_task_history(records[2], 3, 'Personal Information Mask', 'Waiting', self.user.username, histories[2].created, 1, 0, 0, 1)
        self._assert_task_history(records[3], 4, 'Personal Information Mask', 'Complete', self.user.username, histories[1].created, 1, 0, 1, 0)
        self._assert_task_history(records[4], 5, 'Personal Information Mask', 'Complete', self.user.username, histories[0].created, 1, 1, 0, 0)

    def test_task_history_zero(self):
        self.setup_user()

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_task_history_ajax, {})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual('success', data['status'])
        self.assertEqual(0, data['total'])
        self.assertFalse(data['records'])

    def test_task_history_not_allowed_method(self):
        response = self.client.get(self._url_task_history_ajax)
        self.assertEqual(405, response.status_code)


@ddt.ddt
class ContractOperationMailViewTest(BizContractTestBase):

    def setUp(self):
        super(ContractOperationMailViewTest, self).setUp()

        self._create_contract_mail_default()

        self.contract_customize_mail = self._create_contract(
            contract_name='test contract customize mail',
            contractor_organization=self.contract_org,
            detail_courses=[self.course_spoc1.id, self.course_spoc2.id],
            additional_display_names=['country', 'dept'],
            customize_mail=True,
        )
        self.contract_auth_customize_mail = self._create_contract(
            contract_name='test contract auth customize mail',
            contractor_organization=self.contract_org,
            detail_courses=[self.course_spoc5.id],
            url_code='testAuthCustomizeMail',
            send_mail=True,
            customize_mail=True,
        )

    # ------------------------------------------------------------
    # Mail
    # ------------------------------------------------------------
    def _url_mail(self):
        return reverse('biz:contract_operation:register_mail')

    def test_mail_404(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract):
            self.assert_request_status_code(404, self._url_mail())

    def test_mail_404_auth(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract_auth):
            self.assert_request_status_code(404, self._url_mail())

    def test_mail(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract_customize_mail):
            response = self.assert_request_status_code(200, self._url_mail())

        self.assertIn('Test Subject New User Without Logincode', response.content)
        self.assertIn('Test Body New User Without Logincode', response.content)
        self.assertIn('Test Subject Exists User Without Logincode', response.content)
        self.assertIn('Test Body Exists User Without Logincode', response.content)
        self.assertNotIn('Test Subject New User With Logincode', response.content)
        self.assertNotIn('Test Body New User With Logincode', response.content)
        self.assertNotIn('Test Subject Exists User With Logincode', response.content)
        self.assertNotIn('Test Body Exists User With Logincode', response.content)

    def test_mail_auth(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract_auth_customize_mail):
            response = self.assert_request_status_code(200, self._url_mail())

        self.assertNotIn('Test Subject New User Without Logincode', response.content)
        self.assertNotIn('Test Body New User Without Logincode', response.content)
        self.assertNotIn('Test Subject Exists User Without Logincode', response.content)
        self.assertNotIn('Test Body Exists User Without Logincode', response.content)
        self.assertIn('Test Subject New User With Logincode', response.content)
        self.assertIn('Test Body New User With Logincode', response.content)
        self.assertIn('Test Subject Exists User With Logincode', response.content)
        self.assertIn('Test Body Exists User With Logincode', response.content)

    # ------------------------------------------------------------
    # Register mail ajax
    # ------------------------------------------------------------
    def _url_register_mail_ajax(self):
        return reverse('biz:contract_operation:register_mail_ajax')

    @ddt.data(False, True)
    def test_register_mail_no_param(self, has_auth):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_register_mail_ajax(), {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE),
    )
    @ddt.unpack
    def test_register_mail_can_not_customize(self, has_auth, mail_type):
        self.setup_user()
        contract = self.contract_auth if has_auth else self.contract
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_mail_ajax(), {
                'contract_id': self.contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    @ddt.data(False, True)
    def test_register_mail_illegal_mail_type(self, has_auth):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        with self.skip_check_course_selection(current_contract=contract), patch('biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_register_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': 'NoneType',
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        warning_log.assert_called_with("Illegal mail-type: NoneType")

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE),
    )
    @ddt.unpack
    def test_register_mail_empty_mail_subject(self, has_auth, mail_type):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_register_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': '',
                'mail_body': 'Test Body',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Please enter the subject of an e-mail.')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE),
    )
    @ddt.unpack
    def test_register_mail_illegal_mail_subject(self, has_auth, mail_type):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_register_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject,Test Subject,Test Subject,Test Subject,Test Subject,Test Subject,Test Subject,Test Subject,Test Subject,Test Subject',
                'mail_body': 'Test Body',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Subject within 128 characters.')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE),
    )
    @ddt.unpack
    def test_register_mail_empty_mail_body(self, has_auth, mail_type):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_register_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': '',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Please enter the body of an e-mail.')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE),
    )
    @ddt.unpack
    def test_register_mail_contract_unmatch(self, has_auth, mail_type):
        self.setup_user()
        contract_customize_mail = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        contract = self.contract_auth if has_auth else self.contract
        with self.skip_check_course_selection(current_contract=contract_customize_mail):
            response = self.client.post(self._url_register_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE),
    )
    @ddt.unpack
    def test_register_mail_success(self, has_auth, mail_type):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_register_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Successfully to save the template e-mail.')

        contract_mail = ContractMail.objects.get(contract=contract, mail_type=mail_type)
        self.assertEquals(contract_mail.mail_subject, 'Test Subject')
        self.assertEquals(contract_mail.mail_body, 'Test Body')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE),
    )
    @ddt.unpack
    def test_register_mail_error(self, has_auth, mail_type):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        with self.skip_check_course_selection(current_contract=contract), patch('biz.djangoapps.ga_contract_operation.views.ContractMail.objects.get_or_create', side_effect=Exception('test')):
            response = self.client.post(self._url_register_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Failed to save the template e-mail.')

    # ------------------------------------------------------------
    # Send mail ajax
    # ------------------------------------------------------------
    def _url_send_mail_ajax(self):
        return reverse('biz:contract_operation:send_mail_ajax')

    @ddt.data(False, True)
    def test_send_mail_no_param(self, has_auth):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_send_mail_ajax(), {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE),
    )
    @ddt.unpack
    def test_send_mail_can_not_customize(self, has_auth, mail_type):
        self.setup_user()
        contract = self.contract_auth if has_auth else self.contract
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    @ddt.data(False, True)
    def test_send_mail_illegal_mail_type(self, has_auth):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        with self.skip_check_course_selection(current_contract=contract), patch('biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': 'NoneType',
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        warning_log.assert_called_with("Illegal mail-type: NoneType")

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE),
    )
    @ddt.unpack
    def test_send_mail_contract_unmatch(self, has_auth, mail_type):
        self.setup_user()
        contract_customize_mail = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        contract = self.contract_auth if has_auth else self.contract
        with self.skip_check_course_selection(current_contract=contract_customize_mail):
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Current contract is changed. Please reload this page.')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE),
    )
    @ddt.unpack
    def test_send_mail_pre_update(self, has_auth, mail_type):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Please save the template e-mail before sending.')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER, False),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER, True),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE, False),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE, True),
    )
    @ddt.unpack
    def test_send_mail_success(self, has_auth, mail_type, is_existing_user):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail

        # Register
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_register_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Successfully to save the template e-mail.')

        contract_mail = ContractMail.objects.get(contract=contract, mail_type=mail_type)
        self.assertEquals(contract_mail.mail_subject, 'Test Subject')
        self.assertEquals(contract_mail.mail_body, 'Test Body')

        # Send
        with self.skip_check_course_selection(current_contract=contract), patch('biz.djangoapps.ga_contract_operation.views.send_mail') as send_mail:
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        mail_param = {
            'username': self.user.username,
            'password': 'dummyPassword',
            'email_address': self.user.email,
            'logincode': 'dummyLoginCode',
            'urlcode': contract.contractauth.url_code if has_auth else None,
        }
        if is_existing_user:
            mail_param.pop('password')
        if not has_auth:
            mail_param.pop('logincode')
            mail_param.pop('urlcode')
        send_mail.assert_called_with(self.user, 'Test Subject', 'Test Body', mail_param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Successfully to send the test e-mail.')

    @ddt.data(
        (False, ContractMail.MAIL_TYPE_REGISTER_NEW_USER, False),
        (False, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER, True),
        (True, ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE, False),
        (True, ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE, True),
    )
    @ddt.unpack
    def test_send_mail_error(self, has_auth, mail_type, is_existing_user):
        self.setup_user()
        contract = self.contract_auth_customize_mail if has_auth else self.contract_customize_mail

        # Register
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_register_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Successfully to save the template e-mail.')

        contract_mail = ContractMail.objects.get(contract=contract, mail_type=mail_type)
        self.assertEquals(contract_mail.mail_subject, 'Test Subject')
        self.assertEquals(contract_mail.mail_body, 'Test Body')

        # Send
        with self.skip_check_course_selection(current_contract=contract), patch('biz.djangoapps.ga_contract_operation.views.send_mail', side_effect=Exception('test')) as send_mail:
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
            })

        mail_param = {
            'username': self.user.username,
            'password': 'dummyPassword',
            'email_address': self.user.email,
            'logincode': 'dummyLoginCode',
            'urlcode': contract.contractauth.url_code if has_auth else None,
        }
        if is_existing_user:
            mail_param.pop('password')
        if not has_auth:
            mail_param.pop('logincode')
            mail_param.pop('urlcode')
        send_mail.assert_called_with(self.user, 'Test Subject', 'Test Body', mail_param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Failed to send the test e-mail.')


@ddt.ddt
class ContractOperationReminderMailViewTest(BizContractTestBase):

    def setUp(self):
        super(ContractOperationReminderMailViewTest, self).setUp()

        self._create_contract_reminder_mail_default()

        self.contract_submission_reminder = self._create_contract(
            contract_name='test reminder mail',
            contractor_organization=self.contract_org,
            detail_courses=[self.course_spoc1.id, self.course_spoc2.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        # Update sections and components to fit the conditions for submission reminder
        chapter_x = ItemFactory.create(parent=self.course_spoc1, category='chapter', display_name='chapter_x')
        section_x1 = ItemFactory.create(parent=chapter_x, category='sequential', display_name='sequential_x1',
                                        metadata={'graded': True, 'format': 'format_x1'})
        vertical_x1a = ItemFactory.create(parent=section_x1, category='vertical', display_name='vertical_x1a')
        component_x1a_1 = ItemFactory.create(parent=vertical_x1a, category='problem',
                                             display_name='component_x1a_1')
        self.store.update_item(chapter_x, self.user.id)

    # ------------------------------------------------------------
    # Show Reminder Mail
    # ------------------------------------------------------------
    def _url_mail(self):
        return reverse('biz:contract_operation:reminder_mail')

    def test_mail_404(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract):
            self.assert_request_status_code(404, self._url_mail())

    def test_mail(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract_submission_reminder):
            response = self.assert_request_status_code(200, self._url_mail())

        self.assertIn('Test Subject for Submission Reminder', response.content)
        self.assertIn('Test Body for Submission Reminder {username}', response.content)
        self.assertIn('Test Body2 for Submission Reminder', response.content)

    # ------------------------------------------------------------
    # Save Reminder Mail
    # ------------------------------------------------------------
    def _url_save_mail_ajax(self):
        return reverse('biz:contract_operation:reminder_mail_save_ajax')

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_can_not_send_submission_reminder(self, mail_type):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': self.contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Unauthorized access.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_contract_unmatch(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': self.contract.id,  # unmatch
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Current contract is changed. Please reload this page.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_no_contract_id(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Current contract is changed. Please reload this page.")

    def test_save_mail_illegal_mail_type(self):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': 'NoneType',
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        warning_log.assert_called_with("Illegal mail-type: NoneType")

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Unauthorized access.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_empty_reminder_email_days(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': '',
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please use the pull-down menu to choose the reminder e-mail days.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_reminder_email_days_is_not_number(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': '@',
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please use the pull-down menu to choose the reminder e-mail days.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_reminder_email_days_is_out_of_range(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': '-9999',
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please use the pull-down menu to choose the reminder e-mail days.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_empty_mail_subject(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': '',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please enter the subject of an e-mail.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_illegal_mail_subject(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'a' * 129,
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Subject within 128 characters.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_empty_mail_body(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': '',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please enter the body of an e-mail.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_empty_mail_body2(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': '',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please enter the body of an e-mail.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_success(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Successfully to save the template e-mail.")

        contract_mail = ContractReminderMail.objects.get(contract=contract, mail_type=mail_type)
        self.assertEquals(contract_mail.reminder_email_days, 3)
        self.assertEquals(contract_mail.mail_subject, 'Test Subject')
        self.assertEquals(contract_mail.mail_body, 'Test Body')
        self.assertEquals(contract_mail.mail_body2, 'Test Body2')

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_error(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.ContractReminderMail.objects.get_or_create',
                side_effect=Exception('test')):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Failed to save the template e-mail.")

    # ------------------------------------------------------------
    # Send Reminder Mail
    # ------------------------------------------------------------
    def _url_send_mail_ajax(self):
        return reverse('biz:contract_operation:reminder_mail_send_ajax')

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_can_not_send_submission_reminder(self, mail_type):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': self.contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_contract_unmatch(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': self.contract.id,  # unmatch
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Current contract is changed. Please reload this page.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_no_contract_id(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_send_mail_ajax(), {
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Current contract is changed. Please reload this page.")

    def test_send_mail_illegal_mail_type(self):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': 'NoneType',
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        warning_log.assert_called_with("Illegal mail-type: NoneType")

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Unauthorized access.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_pre_update(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Please save the template e-mail before sending.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_success(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder

        # Save
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Successfully to save the template e-mail.")

        contract_mail = ContractReminderMail.objects.get(contract=contract, mail_type=mail_type)
        self.assertEquals(contract_mail.mail_subject, 'Test Subject')
        self.assertEquals(contract_mail.mail_body, 'Test Body')

        # Send
        now = datetime_utils.timezone_now()
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.send_mail') as send_mail:
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        mail_param = {'username': self.user.username}
        target_courses = [get_grouped_target_sections(self.course_spoc1)]
        mail_body = contract_mail.compose_mail_body(target_courses)
        send_mail.assert_called_with(self.user, 'Test Subject', mail_body, mail_param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Successfully to send the test e-mail.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_error(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder

        # Save
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Successfully to save the template e-mail.")

        contract_mail = ContractReminderMail.objects.get(contract=contract, mail_type=mail_type)
        self.assertEquals(contract_mail.mail_subject, 'Test Subject')
        self.assertEquals(contract_mail.mail_body, 'Test Body')

        # Send
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.send_mail', side_effect=Exception('test')) as send_mail:
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        send_mail.assert_called()

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Failed to send the test e-mail.")


@ddt.ddt
class ContractOperationViewBulkStudentTest(BizContractTestBase):
    # ------------------------------------------------------------
    # Bulk Students
    # ------------------------------------------------------------
    def test_bulk_students(self):
        self.setup_user()
        # view student management
        with self.skip_check_course_selection(current_contract=self.contract):
            self.assert_request_status_code(200, reverse('biz:contract_operation:bulk_students'))

    # ------------------------------------------------------------
    # Bulk Unregister students
    # ------------------------------------------------------------
    @property
    def _url_bulk_unregister_students_ajax(self):
        return reverse('biz:contract_operation:bulk_unregister_students_ajax')

    def _assert_bulk_unregister_success(self, response):
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Began the processing of Student Unregister.Execution status, please check from the task history.')

    def _assert_bulk_unregister_after_success_check_db(self, contract_id, csv_content):
        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_unregister', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(contract_id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)
        self.assertItemsEqual([u'{}'.format(s) for s in csv_content.splitlines()], [target.inputdata for target in history.studentunregistertasktarget_set.all()])

    def test_bulk_unregister_contract_unmatch(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract_mooc.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Current contract is changed. Please reload this page.')

    def test_bulk_unregister_no_param(self):
        self.setup_user()

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_unregister_validate_task_error(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2"

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], ERROR_MSG)

    def test_bulk_unregister_no_param_students_list(self):
        self.setup_user()

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract_mooc.id})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_unregister_no_param_contract_id(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_unregister_no_student(self):
        self.setup_user()
        csv_content = ""

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Could not find student list.')

    def test_bulk_unregister_not_allowed_method(self):
        response = self.client.get(self._url_bulk_unregister_students_ajax)
        self.assertEqual(response.status_code, 405)

    @override_settings(BIZ_MAX_BULK_STUDENTS_NUMBER=2)
    def test_bulk_unregister_students_over_max_number(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2\n" \
                      u"test_student_3\n"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("It has exceeded the number(2) of cases that can be a time of specification.", data['error'])

    @override_settings(BIZ_MAX_CHAR_LENGTH_BULK_STUDENTS_LINE=30)
    def test_bulk_unregister_students_over_max_char_length(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)
        csv_content = u"1234567890123456789112345678931"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("The number of lines per line has exceeded the 30 characters.", data['error'])

    def test_bulk_unregister_validate_already_unregisterd(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=UNREGISTER_INVITATION_CODE)
        csv_content = self.user.username

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self._assert_bulk_unregister_success(response)

    def test_bulk_unregister_spoc(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)
        csv_content = self.user.username

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self._assert_bulk_unregister_success(response)
        self._assert_bulk_unregister_after_success_check_db(self.contract.id, csv_content)

    def test_bulk_unregister_mooc(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract_mooc, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_mooc1.id)
        csv_content = self.user.username

        with self.skip_check_course_selection(current_contract=self.contract_mooc):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract_mooc.id, 'students_list': csv_content})

        self._assert_bulk_unregister_success(response)
        self._assert_bulk_unregister_after_success_check_db(self.contract_mooc.id, csv_content)

    def test_bulk_unregister_spoc_staff(self):
        self.setup_user()
        # to be staff
        self.user.is_staff = True
        self.user.save()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)
        csv_content = self.user.username

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self._assert_bulk_unregister_success(response)
        self._assert_bulk_unregister_after_success_check_db(self.contract.id, csv_content)

    def test_bulk_unregister_student_submit_duplicated(self):
        TaskFactory.create(task_type='student_unregister', task_key=hashlib.md5(str(self.contract.id)).hexdigest())
        self.setup_user()
        csv_content = self.user.username

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = None
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Processing of Student Unregister is running.Execution status, please check from the task history.", data['error'])
        # assert not to be created new Task instance.
        self.assertEqual(1, Task.objects.count())

    # # ------------------------------------------------------------
    # # Personalinfo Mask
    # # ------------------------------------------------------------
    @property
    def _url_bulk_personalinfo_mask_students_ajax(self):
        return reverse('biz:contract_operation:bulk_personalinfo_mask_ajax')

    def _assert_bulk_personalinfo_mask_success(self, response):
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Began the processing of Personal Information Mask.Execution status, please check from the task history.')

    def _assert_bulk_personalinfo_mask_after_success_check_db(self, contract_id, csv_content):
        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('personalinfo_mask', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(contract_id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)
        self.assertItemsEqual([u'{}'.format(s) for s in csv_content.splitlines()], [target.inputdata for target in history.contracttasktarget_set.all()])

    def test_bulk_personalinfo_mask_not_allowed_method(self):
        response = self.client.get(self._url_bulk_personalinfo_mask_students_ajax)
        self.assertEqual(response.status_code, 405)

    def test_bulk_personalinfo_mask_contract_unmatch(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract_mooc.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Current contract is changed. Please reload this page.')

    def test_bulk_personalinfo_mask_no_param(self):
        self.setup_user()

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_personalinfo_mask_validate_task_error(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2"

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], ERROR_MSG)

    def test_bulk_personalinfo_mask_no_param_students_list(self):
        self.setup_user()

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract_mooc.id})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_personalinfo_mask_no_param_contract_id(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_personalinfo_mask_no_student(self):
        self.setup_user()
        csv_content = ""

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Could not find student list.')

    @override_settings(BIZ_MAX_BULK_STUDENTS_NUMBER=2)
    def test_bulk_personalinfo_mask_students_over_max_number(self):
        self.setup_user()
        csv_content = u"test_bulk_student_1\n" \
                      u"test_bulk_student_2\n" \
                      u"test_bulk_student_3\n"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("It has exceeded the number(2) of cases that can be a time of specification.", data['error'])

    @override_settings(BIZ_MAX_CHAR_LENGTH_BULK_STUDENTS_LINE=30)
    def test_bulk_personalinfo_mask_students_over_max_char_length(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)
        csv_content = u"1234567890123456789112345678931"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("The number of lines per line has exceeded the 30 characters.", data['error'])

    def test_bulk_personalinfo_mask_validate_already_personal_info_maskd(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        csv_content = self.user.username

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self._assert_bulk_personalinfo_mask_success(response)

    def test_bulk_personalinfo_mask_submit_duplicated(self):
        TaskFactory.create(task_type='personalinfo_mask', task_key=hashlib.md5(str(self.contract.id)).hexdigest())
        self.setup_user()
        csv_content = self.user.username

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = None
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Processing of Personal Information Mask is running.Execution status, please check from the task history.", data['error'])
        # assert not to be created new Task instance.
        self.assertEqual(1, Task.objects.count())

    def test_bulk_personalinfo_mask_success(self):
        self.setup_user()
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)
        csv_content = self.user.username

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self._assert_bulk_personalinfo_mask_success(response)
        self._assert_bulk_personalinfo_mask_after_success_check_db(self.contract.id, csv_content)

    # ------------------------------------------------------------
    # Task History For bulk operation
    # ------------------------------------------------------------
    @property
    def _url_task_history_ajax(self):
        return reverse('biz:contract_operation:task_history')

    def _create_task(self, task_type, task_key, task_id, task_state, total=0, attempted=0, succeeded=0, skipped=0, failed=0):
        task_output = {
            'total': total,
            'attempted': attempted,
            'succeeded': succeeded,
            'skipped': skipped,
            'failed': failed,
        }
        return TaskFactory.create(
            task_type=task_type, task_key=task_key, task_id=task_id, task_state=task_state, task_output=json.dumps(task_output)
        )

    def _create_task_mask_target(self, history, register=None, inputdata=None, message=None, completed=False):
        return ContractTaskTargetFactory.create(
            history=history, register=register, inputdata=inputdata, message=message, completed=completed
        )

    def _create_task_register_target(self, history, student='', message=None, completed=False):
        return StudentRegisterTaskTargetFactory.create(
            history=history, student=student, message=message, completed=completed
        )

    def _create_task_unregister_target(self, history, inputdata='', message=None, completed=False):
        return StudentUnregisterTaskTargetFactory.create(
            history=history, inputdata=inputdata, message=message, completed=completed
        )

    def _assert_task_history(self, history, recid, task_type, state, requester, created, total=0, succeeded=0, skipped=0, failed=0, mes_recid=0, mes_message=None):
        self.assertEqual(history['recid'], recid)
        self.assertEqual(history['task_type'], task_type)
        self.assertEqual(history['task_state'], state)
        self.assertEqual(history['task_result'], "Total: {}, Success: {}, Skipped: {}, Failed: {}".format(total, succeeded, skipped, failed))
        self.assertEqual(history['requester'], requester)
        self.assertEqual(history['created'], to_timezone(created).strftime('%Y/%m/%d %H:%M:%S'))
        if mes_recid > 0:
            self.assertEqual(history['messages'][0]['recid'], mes_recid)
        if mes_message:
            self.assertEqual(history['messages'][0]['message'], mes_message)

    def test_task_history(self):
        self.setup_user()
        tasks = [
            self._create_task('personalinfo_mask', 'key1', 'task_id1', 'SUCCESS', 1, 1, 1, 0, 0),
            self._create_task('student_unregister', 'key2', 'task_id2', 'FAILURE', 1, 1, 0, 1, 0),
            self._create_task('student_register', 'key3', 'task_id3', 'QUEUING', 1, 1, 0, 0, 1),
            self._create_task('additionalinfo_update', 'key4', 'task_id4', 'PROGRESS'),
            self._create_task('dummy_task', 'key5', 'tesk_id5', 'DUMMY'),
        ]
        # Create histories for target contract
        histories = [ContractTaskHistoryFactory.create(contract=self.contract, requester=self.user) for i in range(7)]
        task_target_mask = self._create_task_mask_target(histories[0], message='message1')
        task_target_unregister = self._create_task_unregister_target(histories[1], message='message2')
        task_target_register = self._create_task_register_target(histories[2], message='message3')
        _now = datetime.now(pytz.UTC)
        for i, history in enumerate(histories):
            if i < len(tasks):
                history.task_id = tasks[i].task_id
                history.created = _now + timedelta(seconds=i)
                history.save()
        # Create histories for other contract
        ContractTaskHistoryFactory.create(contract=self.contract_mooc)

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_task_history_ajax, {})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual('success', data['status'])
        self.assertEqual(5, data['total'])
        records = data['records']
        self._assert_task_history(records[0], 1, 'Unknown', 'Unknown', self.user.username, histories[4].created)
        self._assert_task_history(records[1], 2, 'Additional Item Update', 'In Progress', self.user.username, histories[3].created)
        self._assert_task_history(records[2], 3, 'Student Register', 'Waiting', self.user.username, histories[2].created, 1, 0, 0, 1, task_target_register.id, 'message3')
        self._assert_task_history(records[3], 4, 'Student Unregister', 'Complete', self.user.username, histories[1].created, 1, 0, 1, 0, task_target_unregister.id, 'message2')
        self._assert_task_history(records[4], 5, 'Personal Information Mask', 'Complete', self.user.username, histories[0].created, 1, 1, 0, 0, task_target_mask.id, 'message1')


@ddt.ddt
class ContractOperationViewAdditionalInfoTest(BizContractTestBase):

    def setUp(self):
        super(ContractOperationViewAdditionalInfoTest, self).setUp()
        self.setup_user()

    def _register_additional_info_ajax(self, params):
        return self.client.post(reverse('biz:contract_operation:register_additional_info_ajax'), params)

    def _edit_additional_info_ajax(self, params):
        return self.client.post(reverse('biz:contract_operation:edit_additional_info_ajax'), params)

    def _delete_additional_info_ajax(self, params):
        return self.client.post(reverse('biz:contract_operation:delete_additional_info_ajax'), params)

    def _update_additional_info_ajax(self, params):
        return self.client.post(reverse('biz:contract_operation:update_additional_info_ajax'), params)

    def _assert_response_error_json(self, response, error_message):
        self.assertEqual(400, response.status_code)
        self.assertEqual(error_message, json.loads(response.content)['error'])

    # ------------------------------------------------------------
    # register_additional_info_ajax
    # ------------------------------------------------------------
    @ddt.data('display_name', 'contract_id')
    def test_register_additional_info_no_param(self, param):
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }
        del params[param]

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Unauthorized access.")

    def test_register_additional_info_different_contract(self):
        params = {'display_name': 'test',
                  'contract_id': self._create_contract().id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Current contract is changed. Please reload this page.")

    def test_register_additional_info_validate_task_error(self):
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            self._assert_response_error_json(self._register_additional_info_ajax(params), ERROR_MSG)

    def test_register_additional_info_empty_display_name(self):
        params = {'display_name': '',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Please enter the name of item you wish to add.")

    def test_register_additional_info_over_length_display_name(self):
        max_length = AdditionalInfo._meta.get_field('display_name').max_length
        params = {'display_name': get_random_string(max_length + 1),
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Please enter the name of item within {max_number} characters.".format(max_number=max_length))

    def test_register_additional_info_same_display_name(self):
        self._create_additional_info(contract=self.contract, display_name='test')
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "The same item has already been registered.")

    @override_settings(BIZ_MAX_REGISTER_ADDITIONAL_INFO=1)
    def test_register_additional_info_max_additional_info(self):
        self._create_additional_info(contract=self.contract, display_name='hoge')
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Up to {max_number} number of additional item is created.".format(max_number=1))

    def test_register_additional_info_db_error(self):
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch.object(AdditionalInfo, 'objects') as patched_manager:
            patched_manager.create.side_effect = Exception
            patched_manager.filter.return_value.exists.return_value = False
            patched_manager.filter.return_value.count.return_value = 0

            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Failed to register item.")

    def test_register_additional_info_success(self):
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self._register_additional_info_ajax(params)
        self.assertEqual(200, response.status_code)
        self.assertEqual("New item has been registered.", json.loads(response.content)['info'])

    # ------------------------------------------------------------
    # edit_additional_info_ajax
    # ------------------------------------------------------------
    @ddt.data('additional_info_id', 'display_name', 'contract_id')
    def test_edit_additional_info_no_param(self, param):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self.contract.id, }
        del params[param]

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "Unauthorized access.")

    def test_edit_additional_info_different_contract(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self._create_contract().id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "Current contract is changed. Please reload this page.")

    def test_edit_additional_info_validate_task_error(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            self._assert_response_error_json(self._edit_additional_info_ajax(params), ERROR_MSG)

    def test_edit_additional_info_empty_display_name(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': '',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "Please enter the name of item you wish to add.")

    def test_edit_additional_info_over_length_display_name(self):
        max_length = AdditionalInfo._meta.get_field('display_name').max_length
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': get_random_string(max_length + 1),
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "Please enter the name of item within {max_number} characters.".format(max_number=max_length))

    def test_edit_additional_info_same_display_name(self):
        self._create_additional_info(contract=self.contract, display_name='test')
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "The same item has already been registered.")

    def test_edit_additional_info_db_error(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch.object(AdditionalInfo, 'objects') as patched_manager:
            patched_manager.filter.return_value.exclude.return_value.exists.return_value = False
            patched_manager.filter.return_value.update.side_effect = Exception

            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "Failed to edit item.")

    def test_edit_additional_info_success(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self._edit_additional_info_ajax(params)
        self.assertEqual(200, response.status_code)
        self.assertEqual("New item has been updated.", json.loads(response.content)['info'])

    # ------------------------------------------------------------
    # delete_additional_info_ajax
    # ------------------------------------------------------------
    @ddt.data('additional_info_id', 'contract_id')
    def test_delete_additional_info_no_param(self, param):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self.contract.id, }
        del params[param]

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._delete_additional_info_ajax(params),
                                             "Unauthorized access.")

    def test_delete_additional_info_different_contract(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self._create_contract().id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._delete_additional_info_ajax(params),
                                             "Current contract is changed. Please reload this page.")

    def test_delete_additional_info_validate_task_error(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            self._assert_response_error_json(self._delete_additional_info_ajax(params), ERROR_MSG)

    def test_delete_additional_info_does_not_exist(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch.object(AdditionalInfo, 'objects') as patched_manager:
            patched_manager.get.side_effect = AdditionalInfo.DoesNotExist

            self._assert_response_error_json(self._delete_additional_info_ajax(params),
                                             "Already deleted.")

    def test_delete_additional_info_db_error(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch.object(AdditionalInfo, 'objects') as patched_manager:
            patched_manager.get.return_value.delete.side_effect = Exception

            self._assert_response_error_json(self._delete_additional_info_ajax(params),
                                             "Failed to deleted item.")

    def test_delete_additional_info_success(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self._delete_additional_info_ajax(params)
        self.assertEqual(200, response.status_code)
        self.assertEqual("New item has been deleted.", json.loads(response.content)['info'])


class ContractOperationViewUpdateAdditionalInfoTest(BizContractTestBase):

    def setUp(self):
        super(ContractOperationViewUpdateAdditionalInfoTest, self).setUp()
        self.setup_user()

    def _update_additional_info_ajax(self, params):
        return self.client.post(reverse('biz:contract_operation:update_additional_info_ajax'), params)

    def _assert_response_error_json(self, response, error_message):
        self.assertEqual(400, response.status_code)
        self.assertEqual(error_message, json.loads(response.content)['error'])

    # ------------------------------------------------------------
    # update_additional_info_ajax
    # ------------------------------------------------------------
    def test_update_additional_info_success(self):
        contract = self._create_contract(contract_name='test_update_additional_info_success')
        self._create_user_and_contract_register(contract=contract, email='test_student1@example.com')
        self._create_user_and_contract_register(contract=contract, email='test_student2@example.com')
        additional_info1 = self._create_additional_info(contract=contract)
        additional_info2 = self._create_additional_info(contract=contract)
        input_line = u"test_student1@example.com,add1,add2\n" \
                     u"test_student2@example.com,add1,add2"

        params = {'additional_info': [additional_info1.id, additional_info2.id],
                  'contract_id': contract.id,
                  'update_students_list': input_line}

        with self.skip_check_course_selection(current_contract=contract):
            response = self._update_additional_info_ajax(params)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual(ADDITIONALINFO_UPDATE, task.task_type)
        task_input = json.loads(task.task_input)
        self.assertEqual(contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)
        for target in AdditionalInfoUpdateTaskTarget.objects.filter(history=history):
            self.assertIn(target.inputline, input_line)
        self.assertEqual(
            "Began the processing of Additional Item Update.Execution status, please check from the task history.",
            data['info'])

    def test_update_additional_info_contract_id_no_param(self):
        params = {'update_students_list': 'test',
                  'additional_info': 'test', }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._update_additional_info_ajax(params),
                                             "Unauthorized access.")

    def test_update_additional_info_student_list_no_param(self):
        params = {'contract_id': self.contract.id,
                  'additional_info': 'test', }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._update_additional_info_ajax(params),
                                             "Unauthorized access.")

    def test_update_additional_info_additional_info_no_param(self):
        params = {'update_students_list': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._update_additional_info_ajax(params),
                                             "No additional item registered.")

    def test_update_additional_info_different_contract(self):
        params = {'update_students_list': 'test',
                  'contract_id': self._create_contract().id,
                  'additional_info': 'test'}

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._update_additional_info_ajax(params),
                                             "Current contract is changed. Please reload this page.")

    def test_update_additional_info_validate_task_error(self):
        contract = self._create_contract(contract_name='test_update_additional_info_success')
        self._create_user_and_contract_register(contract=contract, email='test_student1@example.com')
        self._create_user_and_contract_register(contract=contract, email='test_student2@example.com')
        additional_info1 = self._create_additional_info(contract=contract)
        additional_info2 = self._create_additional_info(contract=contract)
        input_line = u"test_student1@example.com,add1,add2\n" \
                     u"test_student2@example.com,add1,add2"

        params = {'additional_info': [additional_info1.id, additional_info2.id],
                  'contract_id': contract.id,
                  'update_students_list': input_line}

        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            self._assert_response_error_json(self._update_additional_info_ajax(params), ERROR_MSG)

    def test_update_additional_info_not_find_student_list(self):
        params = {'update_students_list': '',
                  'contract_id': self.contract.id,
                  'additional_info': 'test'}

        self._assert_response_error_json(self._update_additional_info_ajax(params),
                                         "Could not find student list.")

    @override_settings(BIZ_MAX_REGISTER_NUMBER=2)
    def test_update_additional_info_over_max_line(self):
        input_line = u"test_student1@example.com,add1,add2\n" \
                     u"test_student2@example.com,add1,add2\n" \
                     u"test_student3@example.com,add1,add2"

        params = {'update_students_list': input_line,
                  'contract_id': self.contract.id,
                  'additional_info': 'test'}

        self._assert_response_error_json(self._update_additional_info_ajax(params),
                                         "It has exceeded the number(2) of cases that can be a time of registration.")

    def test_update_additional_info_over_max_char_length(self):
        input_line = get_random_string(3001)
        params = {'update_students_list': input_line,
                  'contract_id': self.contract.id,
                  'additional_info': 'test'}

        self._assert_response_error_json(self._update_additional_info_ajax(params),
                                         "The number of lines per line has exceeded the 3000 characters.")

    def test_update_additional_info_different_id(self):
        additional_info1 = self._create_additional_info(contract=self.contract)
        input_line = u"test_student1@example.com,add1"
        params = {'additional_info': additional_info1.id,
                  'contract_id': self.contract.id,
                  'update_students_list': input_line}

        self._assert_response_error_json(self._update_additional_info_ajax(params),
                                         "New item registered. Please reload browser.")

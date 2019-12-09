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

from django.core.urlresolvers import reverse
from django.test.utils import override_settings

from biz.djangoapps.ga_contract_operation.models import ContractMail, ContractTaskHistory
from biz.djangoapps.ga_contract_operation.tests.factories import ContractTaskHistoryFactory, ContractTaskTargetFactory,\
    StudentRegisterTaskTargetFactory, StudentUnregisterTaskTargetFactory, StudentMemberRegisterTaskTargetFactory, \
    ReminderMailTaskHistoryFactory
from biz.djangoapps.ga_invitation.models import REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.gx_students_register_batch.tests.factories import StudentsRegisterBatchTargetFactory
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.tests.factories import TaskFactory
from openedx.core.lib.ga_datetime_utils import to_timezone
from student.models import CourseEnrollment


ERROR_MSG = "Test Message"


class ContractOperationViewTestTaskHistory(BizContractTestBase):
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

        self.reminder = ReminderMailTaskHistoryFactory.create(contract=self.contract, requester=self.user)
        self.reminder_history = self._create_task('reminder_bulk_email', 'key5', 'task_id5', 'SUCCESS', 1, 1, 1, 0, 0)
        self.reminder.task_id = self.reminder_history.task_id
        self.reminder.created = _now - timedelta(seconds=10)
        self.reminder.save()

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_task_history_ajax, {})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual('success', data['status'])
        self.assertNotEqual(6, data['total'])
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

    def test_task_history_ajax(self):
        from ..views import task_history_ajax
        from django.test import RequestFactory
        reminder = ReminderMailTaskHistoryFactory.create(contract=self.contract, requester=self.user)
        reminder_history = self._create_task('reminder_bulk_email', 'key5', 'task_id5', 'SUCCESS', 1, 1, 1, 0, 0)
        reminder.task_id = reminder_history.task_id
        reminder.created = datetime.now()
        reminder.save()
        data = RequestFactory()
        data.META = {}
        data.META['HTTP_REFERER'] = 'reminder'
        data.method = 'POST'
        data.user = self.user
        response = task_history_ajax(data)
        json_data = json.loads(response.content)
        self.assertEqual('success', json_data['status'])
        self.assertEqual(1, json_data['total'])
        self.assertEqual('Reminder Bulk Email', json_data['records'][0]['task_type'])


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
class ContractOperationViewBulkStudentTest(BizContractTestBase):
    # ------------------------------------------------------------
    # Bulk Students
    # ------------------------------------------------------------
    def test_bulk_students(self):
        self.setup_user()
        # view student management
        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
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

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract_mooc.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Current contract is changed. Please reload this page.')

    def test_bulk_unregister_no_param(self):
        self.setup_user()

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_unregister_validate_task_error(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2"

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], ERROR_MSG)

    def test_bulk_unregister_no_param_students_list(self):
        self.setup_user()

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract_mooc.id})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_unregister_no_param_contract_id(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2"

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_unregister_no_student(self):
        self.setup_user()
        csv_content = ""

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
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

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
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

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("The number of lines per line has exceeded the 30 characters.", data['error'])

    def test_bulk_unregister_validate_already_unregisterd(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=UNREGISTER_INVITATION_CODE)
        csv_content = self.user.username

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self._assert_bulk_unregister_success(response)

    def test_bulk_unregister_spoc(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_spoc1.id)
        CourseEnrollment.enroll(self.user, self.course_spoc2.id)
        csv_content = self.user.username

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self._assert_bulk_unregister_success(response)
        self._assert_bulk_unregister_after_success_check_db(self.contract.id, csv_content)

    def test_bulk_unregister_mooc(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract_mooc, status=REGISTER_INVITATION_CODE)
        CourseEnrollment.enroll(self.user, self.course_mooc1.id)
        csv_content = self.user.username

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_contract=self.contract_mooc):
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

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self._assert_bulk_unregister_success(response)
        self._assert_bulk_unregister_after_success_check_db(self.contract.id, csv_content)

    def test_bulk_unregister_student_submit_duplicated(self):
        TaskFactory.create(task_type='student_unregister', task_key=hashlib.md5(str(self.contract.id)).hexdigest())
        self.setup_user()
        csv_content = self.user.username

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = None
            response = self.client.post(self._url_bulk_unregister_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Processing of Student Unregister is running.Execution status, please check from the task history.", data['error'])
        # assert not to be created new Task instance.
        self.assertEqual(1, Task.objects.count())

    # ------------------------------------------------------------
    # Personalinfo Mask
    # ------------------------------------------------------------
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

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract_mooc.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Current contract is changed. Please reload this page.')

    def test_bulk_personalinfo_mask_no_param(self):
        self.setup_user()

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_personalinfo_mask_validate_task_error(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2"

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], ERROR_MSG)

    def test_bulk_personalinfo_mask_no_param_students_list(self):
        self.setup_user()

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract_mooc.id})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_personalinfo_mask_no_param_contract_id(self):
        self.setup_user()
        csv_content = u"test_student_1\n" \
                      u"test_student_2"

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized access.')

    def test_bulk_personalinfo_mask_no_student(self):
        self.setup_user()
        csv_content = ""

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
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

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
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

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("The number of lines per line has exceeded the 30 characters.", data['error'])

    def test_bulk_personalinfo_mask_validate_already_personal_info_maskd(self):
        self.setup_user()
        ContractRegisterFactory.create(user=self.user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        csv_content = self.user.username

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_bulk_personalinfo_mask_students_ajax, {'contract_id': self.contract.id, 'students_list': csv_content})

        self._assert_bulk_personalinfo_mask_success(response)

    def test_bulk_personalinfo_mask_submit_duplicated(self):
        TaskFactory.create(task_type='personalinfo_mask', task_key=hashlib.md5(str(self.contract.id)).hexdigest())
        self.setup_user()
        csv_content = self.user.username

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_contract=self.contract), patch(
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

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
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

    def _create_task_member_register_target(self, history, inputdata='', message=None, completed=False):
        return StudentMemberRegisterTaskTargetFactory.create(
            history=history, student=inputdata, message=message, completed=completed
        )

    def _create_task_student_register_batch_target(self, history, inputdata='', message=None, completed=False):
        return StudentsRegisterBatchTargetFactory.create(
            history=history, student=inputdata, message=message, completed=completed
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
            self._create_task('student_member_register', 'key4', 'task_id4', 'SUCCESS', 1, 1, 1, 0, 0),
            self._create_task('additionalinfo_update', 'key5', 'task_id5', 'PROGRESS'),
            self._create_task('dummy_task', 'key6', 'tesk_id6', 'DUMMY'),
            self._create_task('student_register_batch', 'key7', 'task_id7', 'SUCCESS', 1, 1, 1, 0, 0),
            self._create_task('student_unregister_batch', 'key8', 'task_id8', 'SUCCESS', 1, 1, 1, 0, 0),
        ]
        # Create histories for target contract
        histories = [ContractTaskHistoryFactory.create(contract=self.contract, requester=self.user) for i in range(9)]
        task_target_mask = self._create_task_mask_target(histories[0], message='message1')
        task_target_unregister = self._create_task_unregister_target(histories[1], message='message2')
        task_target_register = self._create_task_register_target(histories[2], message='message3')
        task_target_member_register = self._create_task_member_register_target(histories[3], message='message4')
        task_target_student_register_batch = self._create_task_student_register_batch_target(histories[6], message='message5')
        task_target_student_unregister_batch = self._create_task_student_register_batch_target(histories[7], message='message6')
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
        self.assertEqual(8, data['total'])
        records = data['records']
        self._assert_task_history(records[0], 1, 'Student Unregister Batch', 'Complete', self.user.username, histories[7].created, 1, 1, 0, 0, task_target_student_unregister_batch.id, 'message6')
        self._assert_task_history(records[1], 2, 'Student Register Batch', 'Complete', self.user.username, histories[6].created, 1, 1, 0, 0, task_target_student_register_batch.id, 'message5')
        self._assert_task_history(records[2], 3, 'Unknown', 'Unknown', self.user.username, histories[5].created)
        self._assert_task_history(records[3], 4, 'Additional Item Update', 'In Progress', self.user.username, histories[4].created)
        self._assert_task_history(records[4], 5, 'Student Member Register', 'Complete', self.user.username, histories[3].created, 1, 1, 0, 0, task_target_member_register.id, 'message4')
        self._assert_task_history(records[5], 6, 'Student Register', 'Waiting', self.user.username, histories[2].created, 1, 0, 0, 1, task_target_register.id, 'message3')
        self._assert_task_history(records[6], 7, 'Student Unregister', 'Complete', self.user.username, histories[1].created, 1, 0, 1, 0, task_target_unregister.id, 'message2')
        self._assert_task_history(records[7], 8, 'Personal Information Mask', 'Complete', self.user.username, histories[0].created, 1, 1, 0, 0, task_target_mask.id, 'message1')


"""Tests for student member register task"""

import ddt
from datetime import datetime
from dateutil.tz import tzutc
import json
from mock import patch

from django.core.exceptions import ObjectDoesNotExist

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from biz.djangoapps.ga_contract_operation.models import ReminderMailTaskTarget, ReminderMailTaskHistory
from biz.djangoapps.ga_contract_operation.tasks import reminder_bulk_email
from biz.djangoapps.ga_contract_operation.tests.factories import ReminderMailTaskTargetFactory, ReminderMailTaskHistoryFactory
from biz.djangoapps.ga_invitation.models import REGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.util.tests.testcase import BizViewTestBase
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin
from student.tests.factories import UserFactory, CourseEnrollmentFactory


@ddt.ddt
class ReminderMailTaskTest(BizViewTestBase, ModuleStoreTestCase, TaskTestMixin):

    def setUp(self):
        super(ReminderMailTaskTest, self).setUp()
        # self._create_contract_mail_default()
        self.course_spoc1 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc1', run='run1')
        self.course_spoc2 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc2', run='run2')
        self.contract_org = self._create_organization(org_code='contractor')
        self.contract_org_other = self._create_organization(org_code='contractor_other')
        self.no_contract_org = self._create_organization(org_code='no_contractor')
        self.reminder_course = CourseFactory.create(
            org=self.contract_org.org_code, number='reminder_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            deadline_start=datetime(2016, 1, 5, 0, 0, 0, tzinfo=tzutc())
        )

        self.contract_submission_reminder = self._create_contract(
            contract_name='test reminder mail',
            contractor_organization=self.contract_org,
            detail_courses=[self.course_spoc1.id, self.course_spoc2.id, self.reminder_course.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        self.reminder_user = UserFactory.create()
        self.register = ContractRegisterFactory.create(user=self.reminder_user, contract=self.contract_submission_reminder, status=REGISTER_INVITATION_CODE)
        self.enroll = CourseEnrollmentFactory.create(user=self.reminder_user, course_id=self.reminder_course.id, is_active=True, mode='honor')

    def _create_targets(self, history, students, completed=False):
        for student in students:
            ReminderMailTaskTargetFactory.create(history=history, student_email=student, completed=completed)

    def _create_input_entry(self, contract=None, history=None, course_id=None, subject='test mail subject', body='test mail body', error_message=''):
        task_input = {}
        if contract is not None:
            task_input['contract_id'] = contract.id
        if history is not None:
            task_input['history_id'] = history.id
        task_input['mail_subject'] = subject
        task_input['mail_body'] = body
        task_input['course_id'] = course_id if course_id else str(self.reminder_course.id)
        task_input['error_message'] = error_message
        return TaskTestMixin._create_input_entry(self, task_input=task_input)

    def _create_reminder_task_history(self, contract, requester=None):
        return ReminderMailTaskHistoryFactory.create(contract=contract, requester=requester if requester else self.user)

    def _assert_history_after_execute_task(self, history_id, result, message=None):
        """
        Check MemberTaskHistory data has updated
        :param history_id: MemberTaskHistory.id
        :param result: 0(False) or 1(True)
        :param message: str
        """
        history = ReminderMailTaskTarget.objects.get(id=history_id)
        self.assertEqual(result, history.completed)

    def test_missing_required_input_history(self):
        entry = self._create_input_entry(contract=self._create_contract())

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(reminder_bulk_email, entry.id, entry.task_id)

        self.assertEqual("Task {}: Missing required value {}".format(
            entry.task_id, json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_missing_required_input_contract(self):
        entry = self._create_input_entry(history=self._create_task_history(self._create_contract()))

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(reminder_bulk_email, entry.id, entry.task_id)

        self.assertEqual("Task {}: Missing required value {}".format(
            entry.task_id, json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_history_does_not_exists(self):
        contract = self._create_contract()
        history = self._create_reminder_task_history(contract)
        entry = self._create_input_entry(contract=contract, history=history)
        history.delete()

        with self.assertRaises(ObjectDoesNotExist):
            self._run_task_with_mock_celery(reminder_bulk_email, entry.id, entry.task_id)

        self._assert_task_failure(entry.id)

    def test_conflict_contract(self):
        contract = self._create_contract()
        # Create history with other contract
        history = self._create_reminder_task_history(self._create_contract())
        entry = self._create_input_entry(contract=contract, history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(reminder_bulk_email, entry.id, entry.task_id)

        self.assertEqual("Contract id conflict: submitted value {} does not match {}".format(
            history.contract_id, contract.id), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_reminder_mail_validation_error(self):
        user = self.reminder_user
        contract = self._create_contract()
        history = self._create_reminder_task_history(contract=self.contract_submission_reminder)
        self._create_targets(history=history, students=[u'{},{},{},{}'.format(user.email, user.username, 'exists error', user.profile.name)])

        self._test_run_with_task(
            reminder_bulk_email,
            'reminder_bulk_email',
            task_entry=self._create_input_entry(contract=self.contract_submission_reminder, history=history),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        self.assertEqual(0, ReminderMailTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, ReminderMailTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(user.email + ':' + 'exists error', ReminderMailTaskTarget.objects.filter(history=history, completed=True).first().message)

    def test_reminder_mail_validation_success(self):
        user = self.reminder_user
        contract = self._create_contract()
        history = self._create_reminder_task_history(contract=self.contract_submission_reminder)
        self._create_targets(history=history, students=[
            u'{},{},{},{}'.format(user.email, user.username, '', user.profile.name)])

        self._test_run_with_task(
            reminder_bulk_email,
            'reminder_bulk_email',
            task_entry=self._create_input_entry(contract=self.contract_submission_reminder, history=history),
            expected_attempted=1,
            expected_num_failed=0,
            expected_num_succeeded=1,
            expected_total=1,
        )

        self.assertEqual(0, ReminderMailTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, ReminderMailTaskTarget.objects.filter(history=history, completed=True).count())

    def test_reminder_mail_validation_skip(self):
        user = self.reminder_user
        contract = self._create_contract()
        history = self._create_reminder_task_history(contract=self.contract_submission_reminder)
        self._create_targets(history=history, students=[
            u'{},{},{}'.format(user.email, user.username, user.profile.name)])

        self._test_run_with_task(
            reminder_bulk_email,
            'reminder_bulk_email',
            task_entry=self._create_input_entry(contract=self.contract_submission_reminder, history=history),
            expected_attempted=1,
            expected_num_failed=0,
            expected_num_skipped=1,
            expected_total=1,
        )

        self.assertEqual(0, ReminderMailTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, ReminderMailTaskTarget.objects.filter(history=history, completed=True).count())

    @patch('biz.djangoapps.ga_contract_operation.reminder_email.django_send_mail', side_effect=Exception)
    def test_reminder_mail_exception(self, mock_patch):
        user = self.reminder_user
        contract = self._create_contract()
        history = self._create_reminder_task_history(contract=self.contract_submission_reminder)
        self._create_targets(history=history, students=[
            u'{},{},{},{}'.format(user.email, user.username, '', user.profile.name)])

        self._test_run_with_task(
            reminder_bulk_email,
            'reminder_bulk_email',
            task_entry=self._create_input_entry(contract=self.contract_submission_reminder, history=history),
            expected_attempted=1,
            expected_num_failed=1,
            expected_total=1,
        )

        self.assertEqual(0, ReminderMailTaskTarget.objects.filter(history=history, completed=False).count())
        self.assertEqual(1, ReminderMailTaskTarget.objects.filter(history=history, completed=True).count())
        self.assertEqual(user.email + ':' + 'Failed to send the e-mail.', ReminderMailTaskTarget.objects.filter(history=history, completed=True).first().message)

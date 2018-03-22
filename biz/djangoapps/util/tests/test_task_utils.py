"""
Tests for task utilities
"""
from celery.states import FAILURE, REVOKED, SUCCESS, PENDING, STARTED
import ddt
import hashlib
from mock import patch

from django.utils.crypto import get_random_string

from biz.djangoapps.ga_contract.tests.factories import ContractFactory
from biz.djangoapps.ga_contract_operation.tasks import (
    TASKS, PERSONALINFO_MASK, STUDENT_REGISTER, STUDENT_UNREGISTER, ADDITIONALINFO_UPDATE
)
from biz.djangoapps.ga_organization.tests.factories import OrganizationFactory
from biz.djangoapps.util import task_utils
from biz.djangoapps.util.tests.testcase import BizTestBase

from openedx.core.djangoapps.ga_task.tests.factories import TaskFactory
from student.tests.factories import UserFactory


@ddt.ddt
class TaskUtilsTest(BizTestBase):
    """
    Test for task utilities
    """

    def setUp(self):
        super(TaskUtilsTest, self).setUp()

        self.user = UserFactory.create()
        org = OrganizationFactory.create(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,
            created_by=self.user,
        )
        self.contract = ContractFactory.create(
            contract_name=get_random_string(8),
            contract_type='PF',
            invitation_code=get_random_string(8),
            contractor_organization=org,
            owner_organization=org,
            created_by=UserFactory.create(),
        )
        patcher_log = patch('biz.djangoapps.util.task_utils.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

    def test_get_task_key(self):
        self.assertEqual('c4ca4238a0b923820dcc509a6f75849b', task_utils.get_task_key(self.contract))

    def _create_ready_task(self, task_type):
        TaskFactory.create(task_type=task_type,
                           task_key=hashlib.md5(str(self.contract.id)).hexdigest(),
                           task_state=SUCCESS)
        TaskFactory.create(task_type=task_type,
                           task_key=hashlib.md5(str(self.contract.id)).hexdigest(),
                           task_state=REVOKED)
        TaskFactory.create(task_type=task_type,
                           task_key=hashlib.md5(str(self.contract.id)).hexdigest(),
                           task_state=FAILURE)

    @ddt.data(PERSONALINFO_MASK, STUDENT_REGISTER, STUDENT_UNREGISTER, ADDITIONALINFO_UPDATE)
    def test_success_validate_task(self, task_type):
        self._create_ready_task(task_type)
        self.assertIsNone(task_utils.validate_task(self.contract))

    @ddt.data(PERSONALINFO_MASK, STUDENT_REGISTER, STUDENT_UNREGISTER, ADDITIONALINFO_UPDATE)
    def test_already_running_task(self, task_type):
        self._create_ready_task(task_type)
        task = TaskFactory.create(task_type=task_type,
                                  task_key=hashlib.md5(str(self.contract.id)).hexdigest(),
                                  task_state=STARTED)
        response = task_utils.validate_task(self.contract)
        self.mock_log.warning.assert_called_with(
            "Running of {task_type} is running id({task_id}).".format(task_type=task_type, task_id=task.task_id))
        self.assertEquals(
            "{} is being executed. Please check task history, leave time and try again.".format(TASKS[task_type]),
            response)

    @ddt.data(PERSONALINFO_MASK, STUDENT_REGISTER, STUDENT_UNREGISTER, ADDITIONALINFO_UPDATE)
    def test_already_running_multi_task(self, task_type):
        self._create_ready_task(task_type)
        task1 = TaskFactory.create(task_type=task_type,
                                   task_key=hashlib.md5(str(self.contract.id)).hexdigest(),
                                   task_state=PENDING)
        task2 = TaskFactory.create(task_type=task_type,
                                   task_key=hashlib.md5(str(self.contract.id)).hexdigest(),
                                   task_state=STARTED)
        task_ids = "[u'{}', u'{}']".format(task1.task_id, task2.task_id)
        response = task_utils.validate_task(self.contract)
        self.mock_log.warning.assert_called_with(
            "Running task is too many({task_ids}).".format(task_ids=task_ids))
        self.assertEquals(
            "{} is being executed. Please check task history, leave time and try again.".format(TASKS[task_type]),
            response)


import ddt
import json
import unittest

from celery.states import FAILURE, REVOKED, SUCCESS
from celery.task import task
from django.conf import settings
from django.test import RequestFactory, TestCase

from student.tests.factories import UserFactory

from openedx.core.djangoapps.ga_task.api import submit_task, AlreadyRunningError
from openedx.core.djangoapps.ga_task.models import QUEUING, Task
from openedx.core.djangoapps.ga_task.task import BaseTask


@task(base=BaseTask)
def dummy_task(entry_id):
    """
    This is a dummy task for test.
    """
    pass


# Now, ga_task are only used in the lms. Remove decorator when use in cms.
@unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
@ddt.ddt
class ApiTest(TestCase):

    def setUp(self):
        super(ApiTest, self).setUp()
        self.request = RequestFactory().request()
        self.request.user = UserFactory.create()

        self.task_type = 'test_type'
        self.task_class = dummy_task
        self.task_input = {
            'key1': 'value1',
            'key2': 1,
        }
        self.task_key = 'test_key'

    def _create_task(self, task_type, task_key, task_input, requester, task_state=None):
        # Create Task object directly
        task = Task.create(task_type, task_key, task_input, requester)
        if task_state is not None:
            task.task_state = task_state
            task.save()
        return task

    def _assert_task(self, task, task_type, task_key, task_input, requester, task_state=QUEUING):
        self.assertEqual(task_type, task.task_type)
        self.assertEqual(json.dumps(task_input), task.task_input)
        self.assertEqual(task_state, task.task_state)
        self.assertEqual(requester.id, task.requester_id)

    def test_submit_task(self):
        task = submit_task(self.request, self.task_type, self.task_class, self.task_input, self.task_key)
        self._assert_task(task, self.task_type, self.task_key, self.task_input, self.request.user)

    def test_submit_task_duplicate(self):
        self._create_task(self.task_type, self.task_key, self.task_input, self.request.user)

        with self.assertRaises(AlreadyRunningError):
            submit_task(self.request, self.task_type, self.task_class, self.task_input, self.task_key)

    def test_submit_task_duplicate_another_task_type(self):
        self._create_task(self.task_type, self.task_key, self.task_input, self.request.user)

        self.task_type = 'another_type'

        task = submit_task(self.request, self.task_type, self.task_class, self.task_input, self.task_key)
        self._assert_task(task, self.task_type, self.task_key, self.task_input, self.request.user)

    def test_submit_task_duplicate_another_task_key(self):
        self._create_task(self.task_type, self.task_key, self.task_input, self.request.user)

        self.task_key = 'another_key'

        task = submit_task(self.request, self.task_type, self.task_class, self.task_input, self.task_key)
        self._assert_task(task, self.task_type, self.task_key, self.task_input, self.request.user)

    @ddt.data(SUCCESS, FAILURE, REVOKED)
    def test_submit_task_ready_duplicate(self, task_state):
        """
        Even duplicated tasks, can run if status is READY_STATES
        """
        self._create_task(self.task_type, self.task_key, self.task_input, self.request.user, task_state)

        task = submit_task(self.request, self.task_type, self.task_class, self.task_input, self.task_key)
        self._assert_task(task, self.task_type, self.task_key, self.task_input, self.request.user)

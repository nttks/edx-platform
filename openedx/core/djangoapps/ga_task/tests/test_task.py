
import json
from mock import Mock, patch
from uuid import uuid4

from celery.states import SUCCESS, FAILURE

from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.tests.factories import TaskFactory


class TestTaskFailure(Exception):
    pass


class TaskTestMixin(object):

    def _create_input_entry(self, task_type='test_type', task_key='test_key', task_input={}):
        task_id = str(uuid4())
        return TaskFactory.create(
            task_type=task_type,
            task_key=task_key,
            task_id=task_id,
            task_input=json.dumps(task_input)
        )

    def _assert_task_failure(self, entry_id):
        task = Task.objects.get(pk=entry_id)
        self.assertEqual(FAILURE, task.task_state)

    def _run_task_with_mock_celery(self, task_class, entry_id, task_id, expected_failure_message=None):
        """Submit a task and mock how celery provides a current_task."""
        current_task = Mock()
        current_task.request = Mock()
        current_task.request.id = task_id
        current_task.update_state = Mock()
        if expected_failure_message is not None:
            current_task.update_state.side_effect = TestTaskFailure(expected_failure_message)
        task_args = [entry_id]

        with patch('openedx.core.djangoapps.ga_task.task._get_current_task') as mock_get_task:
            mock_get_task.return_value = current_task
            return task_class.apply(task_args, task_id=task_id).get()

    def _test_missing_current_task(self, task_class):
        """Check that a task_class fails when celery doesn't provide a current_task."""
        task_entry = self._create_input_entry()
        with self.assertRaises(ValueError) as cm:
            task_class(task_entry.id)
        self.assertIn("Requested task did not match actual task", cm.exception.message)

    def _test_run_with_task(self, task_class, action_name, expected_num_succeeded, expected_num_skipped=0,
                            expected_num_failed=0, expected_attempted=0, expected_total=0, task_entry=None):
        """Run a task and check the number of processed."""
        if task_entry is None:
            task_entry = self._create_input_entry()
        status = self._run_task_with_mock_celery(task_class, task_entry.id, task_entry.task_id)
        expected_attempted = expected_attempted \
            if expected_attempted else expected_num_succeeded + expected_num_skipped + expected_num_failed
        expected_total = expected_total \
            if expected_total else expected_num_succeeded + expected_num_skipped + expected_num_failed
        # check return value
        self.assertEquals(status.get('attempted'), expected_attempted)
        self.assertEquals(status.get('succeeded'), expected_num_succeeded)
        self.assertEquals(status.get('skipped'), expected_num_skipped)
        self.assertEquals(status.get('failed'), expected_num_failed)
        self.assertEquals(status.get('total'), expected_total)
        self.assertEquals(status.get('action_name'), action_name)
        self.assertGreater(status.get('duration_ms'), 0)
        # compare with entry in table:
        entry = Task.objects.get(id=task_entry.id)
        self.assertEquals(json.loads(entry.task_output), status)
        self.assertEquals(entry.task_state, SUCCESS)

    def _test_run_with_failure(self, task_class, expected_message, task_entry=None):
        """Run a task and trigger an artificial failure with the given message."""
        if task_entry is None:
            task_entry = self._create_input_entry()
        with self.assertRaises(TestTaskFailure):
            self._run_task_with_mock_celery(task_class, task_entry.id, task_entry.task_id, expected_message)
        # compare with entry in table:
        entry = Task.objects.get(id=task_entry.id)
        self.assertEquals(entry.task_state, FAILURE)
        output = json.loads(entry.task_output)
        self.assertEquals(output['exception'], 'TestTaskFailure')
        self.assertEquals(output['message'], expected_message)

    def _test_run_with_long_error_msg(self, task_class, task_entry=None):
        """
        Run with an error message that is so long it will require
        truncation (as well as the jettisoning of the traceback).
        """
        if task_entry is None:
            task_entry = self._create_input_entry()
        expected_message = "x" * 1500
        with self.assertRaises(TestTaskFailure):
            self._run_task_with_mock_celery(task_class, task_entry.id, task_entry.task_id, expected_message)
        # compare with entry in table:
        entry = Task.objects.get(id=task_entry.id)
        self.assertEquals(entry.task_state, FAILURE)
        self.assertGreater(1023, len(entry.task_output))
        output = json.loads(entry.task_output)
        self.assertEquals(output['exception'], 'TestTaskFailure')
        self.assertEquals(output['message'], expected_message[:len(output['message']) - 3] + "...")
        self.assertTrue('traceback' not in output)

    def _test_run_with_short_error_msg(self, task_class, task_entry=None):
        """
        Run with an error message that is short enough to fit
        in the output, but long enough that the traceback won't.
        Confirm that the traceback is truncated.
        """
        if task_entry is None:
            task_entry = self._create_input_entry()
        expected_message = "x" * 900
        with self.assertRaises(TestTaskFailure):
            self._run_task_with_mock_celery(task_class, task_entry.id, task_entry.task_id, expected_message)
        # compare with entry in table:
        entry = Task.objects.get(id=task_entry.id)
        self.assertEquals(entry.task_state, FAILURE)
        self.assertGreater(1023, len(entry.task_output))
        output = json.loads(entry.task_output)
        self.assertEquals(output['exception'], 'TestTaskFailure')
        self.assertEquals(output['message'], expected_message)
        self.assertEquals(output['traceback'][-3:], "...")

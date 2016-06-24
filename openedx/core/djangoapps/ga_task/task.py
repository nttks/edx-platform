
import json
import logging
import time

from celery import Task as CeleryTask, current_task
from celery.states import SUCCESS, FAILURE
from django.db import reset_queries
from django.utils.translation import ugettext as _

from openedx.core.djangoapps.ga_task.models import Task, PROGRESS, QUEUING

# define different loggers for use within tasks and on client side
log = logging.getLogger('edx.celery.ga_task')


STATES = {
    QUEUING: _("Waiting"),
    PROGRESS: _("In Progress"),
    SUCCESS: _("Success"),
    FAILURE: _("Failed"),
}


class BaseTask(CeleryTask):
    """
    Base task class for use with Task models.

    Permits updating information about task in corresponding Task for monitoring purposes.

    Assumes that the entry_id of the Task model is the first argument to the task.

    The `entry_id` is the primary key for the Task entry representing the task.  This class
    updates the entry on success and failure of the task it wraps. It is setting the entry's value
    for task_state based on what Celery would set it to once the task returns to Celery:
    FAILURE if an exception is encountered, and SUCCESS if it returns normally.
    """
    abstract = True

    def on_success(self, task_progress, task_id, args, kwargs):
        """
        Update Task object corresponding to this task with info about success.

        Updates task_output and task_state.  But it shouldn't actually do anything
        if the task is only creating subtasks to actually do the work.

        Assumes `task_progress` is a dict containing the task's result, with the following keys:

          'attempted': number of attempts made
          'succeeded': number of attempts that "succeeded"
          'skipped': number of attempts that "skipped"
          'failed': number of attempts that "failed"
          'total': number of possible subtasks to attempt
          'action_name': user-visible verb to use in status messages.  Should be past-tense.
              Pass-through of input `action_name`.
          'duration_ms': how long the task has (or had) been running.

        This is JSON-serialized and stored in the task_output column of the Task entry.
        """
        log.debug("Task {task_id}: success returned with progress: {task_progress}".format(task_id=task_id, task_progress=task_progress))
        # We should be able to find the Task object to update
        # based on the task_id here, without having to dig into the
        # original args to the task.  On the other hand, the entry_id
        # is the first value passed to all such args, so we'll use that.
        # And we assume that it exists, else we would already have had a failure.
        entry_id = args[0]
        entry = Task.objects.get(pk=entry_id)
        # Check to see if any subtasks had been defined as part of this task.
        # If not, then we know that we're done.  (If so, let the subtasks
        # handle updating task_state themselves.)
        if len(entry.subtasks) == 0:
            entry.task_output = Task.create_output_for_success(task_progress)
            entry.task_state = SUCCESS
            entry.save_now()

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Update Task object corresponding to this task with info about failure.

        Fetches and updates exception and traceback information on failure.

        If an exception is raised internal to the task, it is caught by celery and provided here.
        The information is recorded in the Task object as a JSON-serialized dict stored in the
        task_output column. It contains the following keys:

               'exception':  type of exception object
               'message': error message from exception object
               'traceback': traceback information (truncated if necessary)

        Note that there is no way to record progress made within the task (e.g. attempted,
        succeeded, etc.) when such failures occur.
        """
        log.debug(u"Task {task_id}: failure returned".format(task_id=task_id))
        entry_id = args[0]
        try:
            entry = Task.objects.get(pk=entry_id)
        except Task.DoesNotExist:
            # if the Task object does not exist, then there's no point trying to update it.
            log.error(u"Task {task_id}: No Task object for id {entry_id}".format(task_id=task_id, entry_id=entry_id))
        else:
            entry.task_output = Task.create_output_for_failure(einfo.exception, einfo.traceback)
            entry.task_state = FAILURE
            entry.save_now()
        finally:
            log.error(u"Task {task_id}: Failed to execute celery task.".format(task_id=task_id), exc_info=True)


def _get_current_task():
    """
    Stub to make it easier to test without actually running Celery.

    This is a wrapper around celery.current_task, which provides access
    to the top of the stack of Celery's tasks.  When running tests, however,
    it doesn't seem to work to mock current_task directly, so this wrapper
    is used to provide a hook to mock in tests, while providing the real
    `current_task` in production.
    """
    return current_task


class TaskProgress(object):
    """
    Encapsulates the current task's progress by keeping track of
    'attempted', 'succeeded', 'skipped', 'failed', 'total',
    'action_name', and 'duration_ms' values.
    """
    def __init__(self, action_name, total, start_time):
        self.action_name = action_name
        self.total = total
        self.start_time = start_time
        self.attempted = 0
        self.succeeded = 0
        self.skipped = 0
        self.failed = 0

    def attempt(self):
        self.attempted += 1

    def success(self):
        self.succeeded += 1

    def skip(self):
        self.skipped += 1

    def fail(self):
        self.failed += 1

    def update_task_state(self, extra_meta=None):
        """
        Update the current celery task's state to the progress state specified by the current object.
        Returns the progress dictionary for use by `run_main_task` and `BaseTask.on_success`.

        Arguments:
            extra_meta (dict): Extra metadata to pass to `update_state`

        Returns:
            dict: The current task's progress dict
        """
        progress_dict = {
            'action_name': self.action_name,
            'attempted': self.attempted,
            'succeeded': self.succeeded,
            'skipped': self.skipped,
            'failed': self.failed,
            'total': self.total,
            'duration_ms': int((time.time() - self.start_time) * 1000),
        }
        if extra_meta is not None:
            progress_dict.update(extra_meta)
        _get_current_task().update_state(state=PROGRESS, meta=progress_dict)
        return progress_dict


def run_main_task(entry_id, task_fcn, action_name):
    """
    Applies the `task_fcn` to the arguments defined in `entry_id` of Task.
    """
    entry = Task.objects.get(pk=entry_id)
    entry.task_state = PROGRESS
    entry.save_now()

    # Get inputs to use in this task from the entry
    task_id = entry.task_id
    task_input = json.loads(entry.task_input)

    # Construct log message for logging to logging before and after execution
    task_info_string = u"Task: {task_id}, Task ID: {entry_id}, Input: {task_input}".format(
        task_id=task_id, entry_id=entry_id, task_input=task_input
    )
    log.info(u'{task_info}, Starting update (nothing {action_name} yet)'.format(
        task_info=task_info_string, action_name=action_name
    ))

    # Check that the task_id submitted in the Task matches the current task that is running.
    request_task_id = _get_current_task().request.id
    if task_id != request_task_id:
        message = u"{task_info}, Requested task did not match actual task({actual_id})".format(
            task_info=task_info_string, actual_id=request_task_id
        )
        log.error(message)
        raise ValueError(message)

    # Now do the work
    task_progress = task_fcn(entry_id, task_input, action_name)

    # Release any queries that the connection has been hanging onto
    reset_queries()

    # Log and exit, returning task_progress info as task result
    log.info(u"{task_info}, Task type: {action_name}, Finishing task: {task_progress}".format(
        task_info=task_info_string, action_name=action_name, task_progress=task_progress
    ))
    return task_progress

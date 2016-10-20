
import logging

from celery.states import READY_STATES, SUCCESS, FAILURE, REVOKED

from openedx.core.djangoapps.ga_task.models import Task

log = logging.getLogger(__name__)


class AlreadyRunningError(Exception):
    """Exception indicating that a background task is already running"""
    pass


def _task_is_running(task_type, task_key):
    """Checks if a particular task is already running"""
    running_tasks = Task.objects.filter(
        task_type=task_type, task_key=task_key
    )
    # exclude states that are "ready" (i.e. not "running", e.g. failure, success, revoked):
    for state in READY_STATES:
        running_tasks = running_tasks.exclude(task_state=state)
    return running_tasks.exists()


def _reserve_task(task_type, task_key, task_input, requester):
    """
    Creates a database entry to indicate that a task is in progress.
    """
    if _task_is_running(task_type, task_key):
        log.warning("Duplicate task found for task_type %s and task_key %s", task_type, task_key)
        raise AlreadyRunningError("requested task is already running")

    try:
        most_recent_id = Task.objects.latest('id').id
    except Task.DoesNotExist:
        most_recent_id = "Not found"
    finally:
        log.info(
            "No duplicate tasks found: task_type %s, task_key %s, and most recent task_id = %s",
            task_type,
            task_key,
            most_recent_id
        )

    # Create log entry now, so that future requests will know it's running.
    return Task.create(task_type, task_key, task_input, requester)


def submit_task(request, task_type, task_class, task_input, task_key, queue=None):
    """
    Helper method to submit a task.
    """
    # check to see if task is already running, and reserve it otherwise:
    task = _reserve_task(task_type, task_key, task_input, request.user)

    task_args = [task.id]
    # FIXME need xmodule instanciate?
    task_class.apply_async(task_args, task_id=task.task_id, queue=queue)
    return task

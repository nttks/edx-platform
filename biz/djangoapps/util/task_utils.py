from celery.states import READY_STATES
import hashlib
import logging

from django.conf import settings
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.ga_contract_operation.tasks import TASKS as CONTRACT_OPERATION_TASKS, REMINDER_BULK_EMAIL
from biz.djangoapps.gx_member.tasks import TASKS as ORGANIZATION_TASKS
from openedx.core.djangoapps.ga_task import api as task_api
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.api import AlreadyRunningError
from util.json_request import JsonResponse, JsonResponseBadRequest

log = logging.getLogger(__name__)


def submit_org_task(request, org, task_input, task_type, task_class, history_cls, history):
    try:
        # Check the task running within the same current_organization.
        validate_task_message = validate_task(org)
        if validate_task_message:
            return JsonResponseBadRequest({
                'error': validate_task_message,
            })

        # task prevents duplicate execution by current_organization_id
        task = submit_task(request, task_type, task_class, task_input, get_org_task_key(org))
        history = history_cls.objects.get(pk=history.id)
        history.link_to_task(task)

    except AlreadyRunningError:
        return JsonResponseBadRequest({
            'error': _("Processing of {task_type} is running.").format(task_type=ORGANIZATION_TASKS[task_type]) +
            _("Execution status, please check from the task history."),
        })

    return JsonResponse({
        'info': _("Began the processing of {task_type}.")
                    .format(task_type=ORGANIZATION_TASKS[task_type]) + _("Execution status, please check from the task history."),
    })


def submit_task(request, task_type, task_class, task_input, task_key, queue=None):
    if queue is None:
        queue = settings.BIZ_CELERY_DEFAULT_QUEUE
    return task_api.submit_task(request, task_type, task_class, task_input, task_key, queue)


def validate_task(key_model):
    """
    Check specific task is already running.
    :param key_model is instance of Contract or Organization
    :return:
    """
    if isinstance(key_model, Organization):
        # Note: Task key of organization was add later.
        running_tasks = Task.objects.filter(task_key=get_org_task_key(key_model)).exclude(task_state__in=READY_STATES).exclude(task_type=REMINDER_BULK_EMAIL)
    else:
        running_tasks = Task.objects.filter(task_key=get_task_key(key_model)).exclude(task_state__in=READY_STATES).exclude(task_type=REMINDER_BULK_EMAIL)

    if not running_tasks:
        return None

    if len(running_tasks) == 1:
        log.warning("Running of {task_type} is running id({task_id}).".format(task_type=running_tasks[0].task_type,
                                                                              task_id=running_tasks[0].task_id))
    else:
        log.warning("Running task is too many({task_ids}).".format(task_ids=[r.task_id for r in running_tasks]))

    return _(
        "{task_type_name} is being executed. Please check task history, leave time and try again."
    ).format(task_type_name=_get_task_type_name_by_task_type(running_tasks[0].task_type))


def _get_task_type_name_by_task_type(task_type):
    tasks = {}
    tasks.update(CONTRACT_OPERATION_TASKS)
    tasks.update(ORGANIZATION_TASKS)
    return tasks[task_type]


def get_task_key(contract):
    return hashlib.md5(str(contract.id)).hexdigest()


def get_org_task_key(org):
    return hashlib.md5(str(org.org_code)).hexdigest()


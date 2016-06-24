
from django.conf import settings

from openedx.core.djangoapps.ga_task import api as task_api


def submit_task(request, task_type, task_class, task_input, task_key, queue=None):
    if queue is None:
        queue = settings.BIZ_CELERY_DEFAULT_QUEUE
    return task_api.submit_task(request, task_type, task_class, task_input, task_key, queue)

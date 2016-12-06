import logging

from celery import task

from openedx.core.djangoapps.ga_task.task import run_main_task, BaseTask
from .tasks_helper import perform_delegate_create_and_publish_certificates

log = logging.getLogger(__name__)


@task(base=BaseTask)
def self_generate_certificate(entry_id):
    visit_func = perform_delegate_create_and_publish_certificates
    action_name = 'self_generate_certificate'
    return run_main_task(entry_id, visit_func, action_name)

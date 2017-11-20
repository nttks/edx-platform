# -*- coding: utf-8 -*-
"""
This file contains tasks that are designed to perform background operations on the
running state of a course.
cf. instructor_task/tasks.py
"""
from functools import partial
import logging

from celery import task
from django.utils.translation import ugettext_noop
from ga_instructor_task.tasks_helper import (
    generate_score_detail_report_helper,
    generate_playback_status_report_helper,
)
from instructor_task.tasks_helper import (
    run_main_task,
    BaseInstructorTask,
)

TASK_LOG = logging.getLogger('edx.celery.task')


@task(base=BaseInstructorTask)
def generate_score_detail_report(entry_id, xmodule_instance_args):
    """
    Generate score detail report in a course.
    """
    # Translators: This is a past-tense verb that is inserted into task progress messages as {action}.
    action_name = ugettext_noop('generate_score_detail_report')
    TASK_LOG.info(
        u"Task: {}, InstructorTask ID: {}, Task type: {}, Preparing for task execution".format(
            xmodule_instance_args.get('task_id'), entry_id, action_name)
    )

    task_fn = partial(generate_score_detail_report_helper, xmodule_instance_args)
    return run_main_task(entry_id, task_fn, action_name)


@task(base=BaseInstructorTask)
def generate_playback_status_report(entry_id, xmodule_instance_args):
    """
    Generate playback status report in a course.
    """
    # Translators: This is a past-tense verb that is inserted into task progress messages as {action}.
    action_name = ugettext_noop('generate_playback_status_report')
    TASK_LOG.info(
        u"Task: {}, InstructorTask ID: {}, Task type: {}, Preparing for task execution".format(
            xmodule_instance_args.get('task_id'), entry_id, action_name)
    )

    task_fn = partial(generate_playback_status_report_helper, xmodule_instance_args)
    return run_main_task(entry_id, task_fn, action_name)

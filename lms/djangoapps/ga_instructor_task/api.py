# -*- coding: utf-8 -*-
"""
API for submitting background tasks by an instructor for a course.

Also includes methods for getting information about tasks that have
already been submitted, filtered either by running state or input
arguments.
"""
from ga_instructor_task.tasks import (
    generate_score_detail_report,
    generate_playback_status_report,
)
from instructor_task.api_helper import submit_task


def submit_generate_score_detail_report(request, course_key):
    """
    Submits a task to generate a CSV score detail report.
    """
    task_type = 'generate_score_detail_report'
    task_class = generate_score_detail_report
    task_input = {}
    task_key = ""
    return submit_task(request, task_type, task_class, course_key, task_input, task_key)


def submit_generate_playback_status_report(request, course_key):
    """
    Submits a task to generate a CSV playback status report.
    """
    task_type = 'generate_playback_status_report'
    task_class = generate_playback_status_report
    task_input = {}
    task_key = ""
    return submit_task(request, task_type, task_class, course_key, task_input, task_key)

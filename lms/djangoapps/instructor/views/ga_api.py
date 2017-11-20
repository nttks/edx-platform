# -*- coding: utf-8 -*-
"""
Instructor Dashboard API views

JSON views which the instructor dashboard requests.

Many of these GETs may become PUTs in the future.
"""
import logging

from django.db import transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.decorators.cache import cache_control
from django.utils.translation import ugettext as _
import ga_instructor_task.api
from instructor.views.api import require_level
from instructor_task.api_helper import AlreadyRunningError
from opaque_keys.edx.keys import CourseKey
from util.json_request import JsonResponse, JsonResponseBadRequest

log = logging.getLogger(__name__)


@transaction.non_atomic_requests
@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_level('staff')
def generate_score_detail_report(request, course_id):  # pylint: disable=redefined-outer-name
    """
    Request a CSV showing students' score in the course.
    """
    course_key = CourseKey.from_string(course_id)
    try:
        ga_instructor_task.api.submit_generate_score_detail_report(request, course_key)
        success_status = _("The score detail report is being created."
                           " To view the status of the report, see Pending Instructor Tasks below.")
        return JsonResponse({"status": success_status})
    except AlreadyRunningError:
        already_running_status = _("A score detail report is already being generated."
                                   " To view the status of the report, see Pending Instructor Tasks below."
                                   " You will be able to download the report when it is complete.")
        return JsonResponse({
            "status": already_running_status
        })


@transaction.non_atomic_requests
@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_level('staff')
def generate_playback_status_report(request, course_id):  # pylint: disable=redefined-outer-name
    """
    Request a CSV showing students' playback status report in the course.
    """
    course_key = CourseKey.from_string(course_id)
    try:
        ga_instructor_task.api.submit_generate_playback_status_report(request, course_key)
        success_status = _("The playback status report is being created."
                           " To view the status of the report, see Pending Instructor Tasks below.")
        return JsonResponse({"status": success_status})
    except AlreadyRunningError:
        already_running_status = _("A playback status report is already being generated."
                                   " To view the status of the report, see Pending Instructor Tasks below."
                                   " You will be able to download the report when it is complete.")
        return JsonResponse({
            "status": already_running_status
        })

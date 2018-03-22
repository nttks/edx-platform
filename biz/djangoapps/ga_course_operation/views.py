"""
This module is view of course_operation.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST

from edxmako.shortcuts import render_to_response

from lms.djangoapps.instructor.views.api import create_survey_response

from biz.djangoapps.util.decorators import check_course_selection, require_survey

log = logging.getLogger(__name__)


@require_GET
@login_required
@check_course_selection
@require_survey
def survey(request):
    return render_to_response('ga_course_operation/survey.html')


@require_POST
@login_required
@check_course_selection
@require_survey
def survey_download(request):
    return create_survey_response(request, unicode(request.current_course.id), 'utf-16')


@require_POST
@login_required
@check_course_selection
@require_survey
def survey_download_utf8(request):
    return create_survey_response(request, unicode(request.current_course.id), 'utf-8')

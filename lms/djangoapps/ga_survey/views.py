"""
Views for Survey
"""
import json
import logging
from urlparse import parse_qsl

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from ga_survey.models import SurveySubmission
from opaque_keys.edx.locator import CourseLocator
from util.json_request import JsonResponse


log = logging.getLogger(__name__)


@require_POST
@login_required
@ensure_csrf_cookie
def survey_init(request):
    """Returns whether the survey has already submitted."""
    qs = dict(parse_qsl(request.body))
    course_id = qs.get('course_id')
    unit_id = qs.get('unit_id')

    if not course_id or not unit_id:
        log.warning("Illegal parameter. course_id=%s, unit_id=%s" % (course_id, unit_id))
        raise Http404

    try:
        submission = SurveySubmission.objects.filter(
            course_id=CourseLocator.from_string(course_id),
            unit_id=unit_id,
            user=request.user
        ).order_by('created')[0:1].get()
    except SurveySubmission.DoesNotExist:
        pass
    else:
        return JsonResponse({
            'success': False,
            'survey_answer': submission.get_survey_answer(),
        })

    return JsonResponse({'success': True})


@require_POST
@login_required
@ensure_csrf_cookie
def survey_ajax(request):
    """Ajax call to submit a survey."""
    qs = dict(parse_qsl(request.body))
    course_id = qs.get('course_id')
    unit_id = qs.get('unit_id')
    survey_name = qs.get('survey_name')
    survey_answer = qs.get('survey_answer')

    if not course_id or not unit_id:
        log.warning("Illegal parameter. course_id=%s, unit_id=%s" % (course_id, unit_id))
        raise Http404
    if not survey_name:
        log.warning("Illegal parameter. survey_name=%s" % survey_name)
        raise Http404
    if not survey_answer:
        log.warning("Illegal parameter. survey_answer=%s" % survey_answer)
        raise Http404
    try:
        # Unicode escape the survey answer.
        survey_answer = json.dumps(json.loads(survey_answer))
    except:
        log.warning("Illegal parameter. survey_answer=%s" % survey_answer)
        raise Http404

    try:
        submission = SurveySubmission.objects.filter(
            course_id=CourseLocator.from_string(course_id),
            unit_id=unit_id,
            user=request.user
        ).order_by('created')[0:1].get()
    except SurveySubmission.DoesNotExist:
        pass
    else:
        return JsonResponse({
            'success': False,
            'survey_answer': submission.get_survey_answer(),
        })

    submission = SurveySubmission(
        course_id=CourseLocator.from_string(course_id),
        unit_id=unit_id,
        user=request.user,
        survey_name=survey_name,
        survey_answer=survey_answer,
    )
    submission.save()
    return JsonResponse({'success': True})

"""
This module is view of course_operation.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST

from lms.djangoapps.instructor.views.api import create_survey_response
from edxmako.shortcuts import render_to_response

from biz.djangoapps.util.decorators import check_course_selection, require_survey, check_organization_group
import biz.djangoapps.ga_course_anslist.views as anslistview

log = logging.getLogger(__name__)


@require_GET
@login_required
@check_course_selection
@require_survey
@check_organization_group
def survey(request):
    log.info('/survey')

    ## set variables of requests
    org = request.current_organization
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    manager = request.current_manager
    ## groups of members under login manager
    child_group_ids = request.current_organization_visible_group_ids

    log.debug('org={},contract_id={},course_id="{}",manager={}'.format(org.id, contract_id, course_id, manager.user))
    log.debug('child_group_ids={}'.format(child_group_ids))

    ## generate select list
    resp_group_list = anslistview._get_group_choice_list(manager, org, child_group_ids)
    resp_org_item_list = anslistview._get_org_item_list()
    resp_survey_names_list =anslistview._get_survey_names_list_merged(course_id)

    resp_columns = anslistview._get_grid_columns(resp_survey_names_list)
    resp_records = []
    resp_total_rec_num = 0
    context = {
        'resp_columns': json.dumps(resp_columns),
        'resp_records': json.dumps(resp_records, ),
        'resp_total_records': resp_total_rec_num,
        'group_list': resp_group_list,
        'member_org_item_list': resp_org_item_list,
        'survey_names_list': resp_survey_names_list,
    }
    return render_to_response('ga_course_operation/survey.html', context)


@require_POST
@login_required
@check_course_selection
@check_organization_group
@require_survey
def survey_download(request):
    ## set variables of requests
    org_id = request.current_organization.id if hasattr(request, 'current_organization') else ""
    course_id = unicode(request.current_course.id)
    manager = request.current_manager if hasattr(request, 'current_manager') else ""
    ## groups of members under login manager
    child_group_ids = request.current_organization_visible_group_ids if hasattr(request, 'current_organization_visible_group_ids') else []

    ## manager check
    is_manager = False
    if manager:
        if manager.is_manager():
            is_manager = True

    return create_survey_response(request, course_id, 'utf-16', is_manager, org_id, child_group_ids)


@require_POST
@login_required
@check_course_selection
@check_organization_group
@require_survey
def survey_download_utf8(request):
    ## set variables of requests
    org_id = request.current_organization.id if hasattr(request, 'current_organization') else ""
    course_id = unicode(request.current_course.id)
    manager = request.current_manager if hasattr(request, 'current_manager') else ""
    ## groups of members under login manager
    child_group_ids = request.current_organization_visible_group_ids if hasattr(request, 'current_organization_visible_group_ids') else []

    ## manager check
    is_manager = False
    if manager:
        if manager.is_manager():
            is_manager = True

    return create_survey_response(request, course_id, 'utf-8', is_manager, org_id, child_group_ids)

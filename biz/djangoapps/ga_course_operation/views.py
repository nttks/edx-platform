"""
This module is view of course_operation.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST

from lms.djangoapps.instructor.views.api import format_survey_response
from student.models import UserStanding
from edxmako.shortcuts import render_to_response
from openedx.core.lib.ga_datetime_utils import format_for_csv
from opaque_keys.edx.locations import SlashSeparatedCourseKey

import biz.djangoapps.ga_course_anslist.views as anslistview
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.util.decorators import check_course_selection, require_survey, check_organization_group
from biz.djangoapps.util.unicodetsv_utils import create_tsv_response, create_csv_response_double_quote

from ga_survey.models import SurveySubmission

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
    """
    File download for utf16
    """
    return _survey_download(request, 'utf-16')


@require_POST
@login_required
@check_course_selection
@check_organization_group
@require_survey
def survey_download_cp932(request):
    """
    File download for cp932
    """
    return _survey_download(request, 'cp932')


def _survey_download(request, encoding):
    manager = request.current_manager
    org = request.current_organization
    course_id = unicode(request.current_course.id)

    sql = '''SELECT s.*, u.*, p.*, t.account_status, e.is_active, b.login_code
               FROM ga_survey_surveysubmission s 
               LEFT OUTER JOIN auth_user u 
               ON s.user_id = u.id 
               LEFT OUTER JOIN auth_userprofile p 
               ON s.user_id = p.user_id 
               LEFT OUTER JOIN student_userstanding t 
               ON s.user_id = t.user_id 
               LEFT OUTER JOIN student_courseenrollment e 
               ON s.user_id = e.user_id 
               and s.course_id = e.course_id 
               LEFT OUTER JOIN ga_login_bizuser b 
               ON s.user_id = b.user_id 
               LEFT OUTER JOIN ga_contract_contractdetail as d 
               ON s.course_id = d.course_id 
               LEFT OUTER JOIN ga_contract_contract as c 
               ON d.contract_id = c.id 
               LEFT OUTER JOIN ga_organization_organization as o 
               ON c.contractor_organization_id = o.id 
               INNER JOIN ga_invitation_contractregister as r 
               ON s.user_id = r.user_id 
               AND c.id = r.contract_id 
               WHERE s.course_id = %s
               AND o.id = %s
               '''

    if not manager.is_director() and manager.is_manager() and Group.objects.filter(org=org).exists():
        # add condition when manager
        child_group_ids = request.current_organization_visible_group_ids
        user_ids = Member.find_active_by_org(org=org.id).filter(
            group__id__in=child_group_ids).values_list('user__id', flat=True) or [0]
        sql += 'AND u.id IN (' + ','.join(map(str, user_ids)) + ')'

    submissions = list(SurveySubmission.objects.raw(sql + 'ORDER BY s.unit_id, s.created', [course_id, str(org.id)]))

    return csv_format_survey_response(request, course_id, encoding, submissions)


def csv_format_survey_response(request, course_id, encoding, submissions):
    header = ['Unit ID', 'Survey Name', 'Created', 'User Name', 'Full Name', 'Email', 'Resigned', 'Unenrolled']
    rows = []

    HEADER_LOGIN_CODE = 'Login Code'
    # NOTE: Try to add login code when called from biz and contract has auth info
    if hasattr(request, 'current_contract') and request.current_contract.has_auth:
        header.append(HEADER_LOGIN_CODE)

    if len(submissions) > 0:
        # NOTE: eliminate duplication of question names
        keyset = set()
        for s in submissions:
            try:
                ans_dict = s.get_survey_answer()
            except ValueError:
                continue
            keyset.update(ans_dict.keys())
        keys = sorted(keyset)
        header.extend(keys)

        for s in submissions:
            try:
                ans_dict = s.get_survey_answer()
            except ValueError:
                ans_dict = {}
                msg = "Couldn't parse JSON in survey_answer, so treat each item as 'N/A'. course_id={0}, unit_id={1}, username={2}".format(
                    course_id, s.unit_id, s.username)
                log.warning(msg)
            row = [s.unit_id, s.survey_name, format_for_csv(s.created), s.username, s.name, s.email]
            row.append('1' if s.account_status == UserStanding.ACCOUNT_DISABLED else '')
            row.append('1' if not s.is_active else '')
            if HEADER_LOGIN_CODE in header:
                row.append(s.login_code or '')
            for key in keys:
                value = ans_dict.get(key, 'N/A')
                # NOTE: replace list into commified str
                if isinstance(value, list):
                    value = ','.join(value)
                row.append(value)
            rows.append(row)
    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    # To open this file by Excel by default, will set the extension to csv.
    file_name = '{org}-{course}-{run}-survey.csv'.format(org=course_key.org, course=course_key.course, run=course_key.run)
    if encoding == 'utf-16':
        return create_tsv_response(file_name, header, rows, encoding)
    else:
        return create_csv_response_double_quote(file_name, header, rows, encoding)





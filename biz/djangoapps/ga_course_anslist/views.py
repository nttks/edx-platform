# -*- coding: utf-8 -*-
"""
Views for answer status listing feature
"""
import copy
import json
import logging
from collections import OrderedDict
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST

import biz.djangoapps.ga_course_anslist.helpers as helper
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder
from biz.djangoapps.util.decorators import check_course_selection, check_organization_group
from biz.djangoapps.util.unicodetsv_utils import create_tsv_response

from util.file import course_filename_prefix_generator
from util.json_request import JsonResponse
from ga_survey.models import SurveySubmission
from student.models import CourseEnrollment

log = logging.getLogger(__name__)


def _get_org_item_list():
    member_org_item_list = OrderedDict()
    member_org_item_list.update([('org' + str(i), _("Organization") + str(i)) for i in range(1, 11)])
    member_org_item_list.update([('item' + str(i), _("Item") + str(i)) for i in range(1, 11)])
    return member_org_item_list


def _get_survey_names_list(course_id, flg_get_updated_survey_name=False):
    ## add for answer list on survey
    sql_statement = helper._create_survey_name_list_statement(course_id, flg_get_updated_survey_name)
    records = SurveySubmission.objects.raw(sql_statement)
    ret = []
    for record in records:
        ret.append((record.unit_id, record.survey_name))

    return ret


def _get_survey_names_list_merged(course_id):
    temp_survey_names_list = _get_survey_names_list(course_id)
    temp_survey_names_list_update_survey_name = _get_survey_names_list(course_id, flg_get_updated_survey_name=True)
    dct = dict(temp_survey_names_list_update_survey_name)
    ret_tpl = [(itm[0], dct[itm[0]]) for itm in temp_survey_names_list]
    return ret_tpl

def _get_grid_columns(survey_names_list):
    columns = []
    columns_list = helper._get_grid_columns_base(survey_names_list)
    columns_list_hidden = helper._get_grid_columns_hidden()
    columns.extend([(_(item[0]), item[1]) for item in columns_list])
    columns.extend([(_("Organization") + str(i), 'text') for i in range(1, 4)])
    columns.extend([(_("Item") + str(i), 'text') for i in range(1, 4)])
    columns.extend([(_(item[0]), item[1]) for item in columns_list_hidden])
    columns.extend([(_("Organization") + str(i), 'hidden') for i in range(4, 11)])
    columns.extend([(_("Item") + str(i), 'hidden') for i in range(4, 11)])
    return columns


def _populate_members(results):
    return {
        result['user__id']: {
            'obj': result,
            'id': result['user__id'],
            _('Username'): result['user__username'],
            _('Email'): result['user__email'],
            _('Full Name'): result['user__profile__name'],
            _('Login Code'): result['user__bizuser__login_code'],
            _('Member Code'): result['code'],
            _('Organization') + '1': result['org1'],
            _('Organization') + '2': result['org2'],
            _('Organization') + '3': result['org3'],
            _('Organization') + '4': result['org4'],
            _('Organization') + '5': result['org5'],
            _('Organization') + '6': result['org6'],
            _('Organization') + '7': result['org7'],
            _('Organization') + '8': result['org8'],
            _('Organization') + '9': result['org9'],
            _('Organization') + '10': result['org10'],
            _('Item') + '1': result['item1'],
            _('Item') + '2': result['item2'],
            _('Item') + '3': result['item3'],
            _('Item') + '4': result['item4'],
            _('Item') + '5': result['item5'],
            _('Item') + '6': result['item6'],
            _('Item') + '7': result['item7'],
            _('Item') + '8': result['item8'],
            _('Item') + '9': result['item9'],
            _('Item') + '10': result['item10'],
            _('Organization Name'): result['group__group_name'],
            _('Group Code'): result['group__group_code']
        } for result in results
    }


def _get_members(org_id, child_group_ids, conditions=None):
    filters = {}

    if child_group_ids:
        filters['group__id__in'] = child_group_ids

    if conditions:
        org_item_list = [u'org' + str(i) for i in range(1, 11)] + [u'item' + str(i) for i in range(1, 11)]
        for condition in conditions:
            if condition['field'][0] == u'group_id' and condition['value'][0]:
                filters['group__id'] = condition['value'][0]
            elif condition['field'][0] in org_item_list:
                filters[condition['field'][0] + '__contains'] = condition['value']

    return _populate_members(
        Member.find_active_by_org(org=org_id).filter(**filters).select_related(
            'group', 'user', 'user__bizuser', 'user__profile').values(*[
            'code', 'org1', 'org2', 'org3', 'org4', 'org5', 'org6', 'org7', 'org8', 'org9', 'org10',
            'item1', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7', 'item8', 'item9', 'item10',
            'user__id', 'user__username', 'user__email', 'user__profile__name', 'user__bizuser__login_code',
            'group__group_name', 'group__group_code'
        ])
    )


def _populate_users_not_members(results):
    return {
        result.user_id: {
            'obj': result,
            'id': result.user_id,
            _('Username'): result.username,
            _('Email'): result.email,
            _('Full Name'): result.name,
            _('Login Code'): result.login_code,
            _('Enroll Date'): datetime_utils.to_jst(result.created).strftime('%Y/%m/%d'),
            _('Group Code'): '',
            _('Member Code'): "",
        } for result in results
    }


def _get_users_not_member(org_id, contract_id, course_id, user_ids_of_members):
    sql_statement = helper._create_users_not_members_statement(org_id, contract_id, course_id, user_ids_of_members)
    records = SurveySubmission.objects.raw(sql_statement)
    log.debug('contract_id={}'.format(contract_id))
    log.debug(sql_statement)
    log.debug(records)
    return _populate_users_not_members(records)


def _get_surveysubmission(ids, course_id):
    results = []
    if ids:
        results = SurveySubmission.objects.filter(user_id__in=ids, course_id=course_id)
    return results


def _get_course_members(ids, course_id):
    results = []
    if ids:
        results = CourseEnrollment.objects.filter(
            user_id__in=ids, course_id=course_id).values('user_id', 'created')
    return results


def _get_group_choice_list(manager, org, visible_group_ids):
    """
    :param manager: request.current_manager
    :param org: request.current_organization
    :param visible_group_ids: request.current_organization_visible_group_ids
    :return: [(group.group_code, group.id, group..group_name),...]
    """
    if not manager.is_director() and manager.is_manager() and Group.objects.filter(org=org).exists():
        group_list = [(grp.group_code, grp.id, grp.group_name) for grp in
                      Group.objects.filter(org=org.id, id__in=visible_group_ids).order_by('group_code')]
    else:
        group_list = [(grp.group_code, grp.id, grp.group_name) for grp in
                      Group.objects.filter(org=org.id).order_by('group_code')]

    return group_list


def _retrieve_grid_data(org_id, child_group_ids, contract_id, course_id, is_filter, members_condition=None, is_manager=False):
    result_members = {}

    ## judge can_retrieve_data
    can_retrieve_data = True
    if child_group_ids:
        pass
    else:
        if is_manager:
            can_retrieve_data = False

    if not can_retrieve_data:
        return result_members
    else:
        ## process is continued
        pass

    ## get members' rows in groups
    members_dcts = _get_members(org_id, child_group_ids, members_condition)

    course_members_rows = _get_course_members(members_dcts.keys(), course_id)

    ## add course enrolled date into dict
    for course_member in course_members_rows:
        user_id = course_member['user_id']
        member_dct = members_dcts[user_id]
        member_dct.update({
            _('Enroll Date') : datetime_utils.to_jst(course_member['created']).strftime('%Y/%m/%d')})
        result_members.update({user_id: copy.deepcopy(member_dct)})

    members_ids = result_members.keys()

    if is_filter == 'off':
        ## get users' rows not in groups
        results_users_not_member = {}
        results_users_not_member = _get_users_not_member(org_id, contract_id, course_id, members_ids)
        ## merge
        if results_users_not_member:
            result_members.update(results_users_not_member)

    log.debug(result_members)

    ## get survey submission
    users_submissions = _get_surveysubmission(result_members.keys(), course_id)

    ## set survey answered date into dict
    survey_name_tpl = _get_survey_names_list(course_id, flg_get_updated_survey_name=True)
    survey_name_dct = dict(survey_name_tpl)
    for submission in users_submissions:
        result_members[submission.user_id].update({
            survey_name_dct[submission.unit_id] : datetime_utils.to_jst(submission.created).strftime('%Y/%m/%d %H:%M')})

    return result_members


@require_POST
@login_required
@check_course_selection
@check_organization_group
def search_ajax(request):
    """
    Returns response for anslist search api

    :param request: HttpRequest
    :return: JsonResponse
    """
    ## set variables of requests
    org = request.current_organization
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    manager = request.current_manager
    ## groups of members under login manager
    child_group_ids = request.current_organization_visible_group_ids
    ## set conditions of request
    member_conditions, survey_name_conditions = helper._set_conditions(request.POST)
    ## judge filter
    is_filter = 'off'
    if 'is_filter' in request.POST:
        is_filter = request.POST['is_filter']

    ## judge is_manager_no_exist_group_group
    ## if no_exist group_group is_manager = False
    ## if exist group_group is_manager = True
    is_manager = not manager.is_director() and manager.is_manager() and Group.objects.filter(org=org,).exists()

    log.debug('is_filter={}'.format(is_filter))
    log.debug('is_manager={}'.format(is_manager))
    log.debug('org={},contract_id={},course_id="{}",manager={}'.format(org.id, contract_id, course_id, manager.user))
    log.debug('child_group_ids={}'.format(child_group_ids))
    log.debug('request.POST={}'.format(request.POST))
    log.debug('member_conditions={}'.format(member_conditions))
    log.debug('survey_name_conditions={}'.format(survey_name_conditions))

    ## get grid data
    members_grid_dct = _retrieve_grid_data(org.id, child_group_ids, contract_id, course_id, is_filter, member_conditions, is_manager)

    ## generate grid
    resp_records = sorted(
        helper._transform_grid_records(members_grid_dct, survey_name_conditions),
        key=lambda x: (x[_('Group Code')], x[_('Member Code')], x[_('Username')])
    )
    resp_total_rec_num = len(resp_records)

    content = {
        'status': 'success',
        'resp_records_json': json.dumps(resp_records, cls=EscapedEdxJSONEncoder),
        'resp_total_records': resp_total_rec_num,
    }
    return JsonResponse(content)


@require_POST
@login_required
@check_course_selection
@check_organization_group
def download_csv(request):
    """
    Returns response for download of answer status csv

    :param request: HttpRequest
    :return: HttpResponse (a csv file)
    """
    CSV_NAME = 'answer_status'
    dtm = datetime.now()
    timestamp_str = dtm.strftime('%Y-%m-%d-%H%M')
    ## set variables of requests
    org = request.current_organization
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    manager = request.current_manager
    ## groups of members under login manager
    child_group_ids = request.current_organization_visible_group_ids
    ## set conditions of request
    member_conditions, survey_name_conditions = helper._set_conditions(request.POST)
    ## judge filter
    is_filter = 'off'
    if 'is_filter' in request.POST:
        is_filter = request.POST['is_filter']

    ## judge is_manager_no_exist_group_group
    ## if no_exist group_group is_manager = False
    ## if exist group_group is_manager = True
    is_manager = not manager.is_director() and manager.is_manager() and Group.objects.filter(org=org,).exists()

    log.debug('is_filter={}'.format(is_filter))
    log.debug('is_manager={}'.format(is_manager))
    log.debug('org={},contract_id={},course_id="{}",manager={}'.format(org.id, contract_id, course_id, manager.user))
    log.debug('org={}'.format(org))
    log.debug('child_group_ids={}'.format(child_group_ids))
    log.debug('member_conditions={}'.format(member_conditions))
    log.debug('survey_name_conditions={}'.format(survey_name_conditions))

    ## generate select list
    resp_survey_names_list = _get_survey_names_list_merged(course_id)

    ## get grid data
    members_grid_dct = _retrieve_grid_data(org.id, child_group_ids, contract_id, course_id, is_filter, member_conditions, is_manager)

    ## generate grid
    resp_columns = _get_grid_columns(resp_survey_names_list)
    resp_records = sorted(
        helper._transform_grid_records(members_grid_dct, survey_name_conditions),
        key=lambda x: (x[_('Group Code')], x[_('Member Code')], x[_('Username')])
    )

    header, datarows = helper._populate_for_tsv(resp_columns, resp_records)

    filename = u'{course_prefix}_{csv_name}_{timestamp_str}.csv'.format(
        course_prefix=course_filename_prefix_generator(course_id),
        csv_name=CSV_NAME,
        timestamp_str=timestamp_str,
    )
    response = create_tsv_response(filename, header, datarows)
    response['Set-Cookie'] = 'fileDownload=true; path=/'
    return response


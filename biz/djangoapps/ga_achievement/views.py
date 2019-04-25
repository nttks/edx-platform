# -*- coding: utf-8 -*-
"""
Views for achievement feature
"""
import json
import logging
import numbers
from collections import OrderedDict
from datetime import datetime
from string import Template

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore, ScoreStore
from biz.djangoapps.ga_achievement.models import PlaybackBatchStatus, ScoreBatchStatus
from biz.djangoapps.ga_invitation.models import STATUS as CONTRACT_REGISTER_STATUS
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder
from biz.djangoapps.util.decorators import check_course_selection, check_organization_group
from biz.djangoapps.util.unicodetsv_utils import create_tsv_response, create_csv_response_double_quote

from lms.djangoapps.courseware.courses import get_course
from courseware.models import StudentModule
from edxmako.shortcuts import render_to_response
from student.models import CourseEnrollment
from util.file import course_filename_prefix_generator
from util.json_request import JsonResponse, JsonResponseBadRequest
from util.ga_attendance_status import AttendanceStatusExecutor

log = logging.getLogger(__name__)

# Note: Max number of score and playback data to display.
MAX_RECORDS_SEARCH_BY_PLAYBACK = 10000


@require_GET
@login_required
@check_course_selection
@check_organization_group
def score(request):
    """
    Returns response for score status

    :param request: HttpRequest
    :return: HttpResponse
    """
    org = request.current_organization
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    manager = request.current_manager
    course = get_course(course_id)

    status = {k: unicode(v) for k, v in dict(CONTRACT_REGISTER_STATUS).items()}

    student_status = [
        "Not Enrolled",
        "Enrolled",
        "Finish Enrolled",
    ]
    certificate_status = [
        ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE,
        ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED,
    ]

    score_batch_status = ScoreBatchStatus.get_last_status(contract_id, course_id)
    if score_batch_status:
        update_datetime = datetime_utils.to_jst(score_batch_status.created).strftime('%Y/%m/%d %H:%M')
        update_status = _(score_batch_status.status)
    else:
        update_datetime = ''
        update_status = ''

    score_store = ScoreStore(contract_id, unicode(course_id))
    score_columns, score_records = score_store.get_data_for_w2ui(limit=settings.BIZ_MONGO_LIMIT_RECORDS)

    hidden_score_columns = score_store.get_section_names()
    score_section_names = [column[0] for column in hidden_score_columns]

    score_columns = _change_column(request, score_columns)
    score_columns.insert(1, (_("Organization Groups"), 'text'))
    score_columns.extend([(_("Organization") + str(i), 'text') for i in range(1, 4)])
    score_columns.extend([(_("Item") + str(i), 'text') for i in range(1, 4)])
    score_columns.extend([(_("Organization") + str(i), 'hidden') for i in range(4, 11)])
    score_columns.extend([(_("Item") + str(i), 'hidden') for i in range(4, 11)])

    # Member
    child_group_ids = request.current_organization_visible_group_ids

    new_score_records = _merge_to_store_by_member_for_search(
        request, org, child_group_ids, manager, _(ScoreStore.FIELD_USERNAME), score_records)

    context = {
        'update_datetime': update_datetime,
        'update_status': update_status,
        'score_columns': json.dumps(score_columns),
        'score_records': json.dumps(new_score_records),
        'status_list': status,
        'member_org_item_list': _get_member_org_item_list(),
        'group_list': _create_group_choice_list(manager, org, child_group_ids),
        'student_status': student_status,
        'certificate_status': certificate_status,
        'score_section_names': score_section_names,
        'is_status_managed': course.is_status_managed,
    }
    return render_to_response('ga_achievement/score.html', context)


def _create_group_choice_list(manager, org, visible_group_ids):
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


@require_GET
@login_required
@check_course_selection
@check_organization_group
def playback(request):
    """
    Returns response for playback status

    :param request: HttpRequest
    :return: HttpResponse
    """
    org = request.current_organization
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    manager = request.current_manager
    batch_status = PlaybackBatchStatus.get_last_status(contract_id, course_id)
    course = get_course(course_id)

    status = {k: unicode(v) for k, v in dict(CONTRACT_REGISTER_STATUS).items()}

    student_status = [
        "Finish Enrolled",
        "Enrolled",
        "Not Enrolled",
    ]

    if batch_status:
        update_datetime = datetime_utils.to_jst(batch_status.created).strftime('%Y/%m/%d %H:%M')
        update_status = _(batch_status.status)
    else:
        update_datetime = ''
        update_status = ''

    playback_store = PlaybackStore(contract_id, unicode(course_id))
    playback_columns, playback_records = playback_store.get_data_for_w2ui(limit=MAX_RECORDS_SEARCH_BY_PLAYBACK)

    hidden_playback_columns = playback_store.get_section_names()
    playback_section_names = [column[0] for column in hidden_playback_columns]

    playback_columns = _change_column(request, playback_columns)
    playback_columns.insert(1, (_("Organization Groups"), 'text'))
    playback_columns.extend([(_("Organization") + str(i), 'text') for i in range(1, 4)])
    playback_columns.extend([(_("Item") + str(i), 'text') for i in range(1, 4)])
    playback_columns.extend([(_("Organization") + str(i), 'hidden') for i in range(4, 11)])
    playback_columns.extend([(_("Item") + str(i), 'hidden') for i in range(4, 11)])

    # Member
    child_group_ids = request.current_organization_visible_group_ids

    new_playback_records = _merge_to_store_by_member_for_search(
        request, org, child_group_ids, manager, _(PlaybackStore.FIELD_USERNAME), playback_records)

    context = {
        'update_datetime': update_datetime,
        'update_status': update_status,
        'playback_columns': json.dumps(playback_columns),
        'playback_records': json.dumps(new_playback_records),
        'status_list': status,
        'member_org_item_list': _get_member_org_item_list(),
        'group_list': _create_group_choice_list(manager, org, child_group_ids),
        'student_status': student_status,
        'playback_section_names': playback_section_names,
        'is_status_managed': course.is_status_managed,
    }
    return render_to_response('ga_achievement/playback.html', context)


@require_POST
@login_required
@check_course_selection
@check_organization_group
def score_search_ajax(request):
    org = request.current_organization
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    manager = request.current_manager

    try:
        __, __, total_records, new_score_records = score_search_filter(request, org, contract_id, course_id, manager)
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponseBadRequest(_("An error has occurred while loading. Please wait a moment and try again."))

    content = {
        'status': 'success',
        'total_records': total_records,
        'score_records_json': json.dumps(new_score_records, cls=EscapedEdxJSONEncoder),
    }
    return JsonResponse(content)


@require_POST
@login_required
@check_course_selection
@check_organization_group
def playback_search_ajax(request):
    org = request.current_organization
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    manager = request.current_manager

    try:
        __, __, total_records, new_playback_records = playback_search_filter(request, org, contract_id, course_id, manager)
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponseBadRequest(_("An error has occurred while loading. Please wait a moment and try again."))

    content = {
        'status': 'success',
        'total_records': total_records,
        'playback_records_json': json.dumps(new_playback_records, cls=EscapedEdxJSONEncoder),
    }
    return JsonResponse(content)


@require_POST
@login_required
@check_course_selection
@check_organization_group
def score_download_csv(request):
    """
    Returns response for download of score status csv

    :param request: HttpRequest
    :return: HttpResponse
    """
    org = request.current_organization
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    manager = request.current_manager

    batch_status = ScoreBatchStatus.get_last_status(contract_id, course_id)
    if batch_status:
        update_datetime = datetime_utils.to_jst(batch_status.created).strftime('%Y-%m-%d-%H%M')
    else:
        update_datetime = 'no-timestamp'

    score_store = ScoreStore(contract_id, unicode(course_id))

    if "search-download" in request.POST:
        score_columns, score_records, __, new_score_records = score_search_filter(request, org, contract_id, course_id,
                                                                                  manager)
        score_columns = _change_column(request, score_columns)
    else:
        score_columns, score_records = score_store.get_data_for_w2ui(limit=settings.BIZ_MONGO_LIMIT_RECORDS)
        score_columns = _change_column(request, score_columns)
        new_score_records = []

    # Member
    username_key = _(ScoreStore.FIELD_USERNAME)
    members = Member.find_active_by_org(org=org.id).select_related('user', 'group').filter(
        user__username__in=[s[username_key] for s in score_records])

    is_manager = not manager.is_director() and manager.is_manager() and Group.objects.filter(org=org).exists()
    child_group_ids = request.current_organization_visible_group_ids

    members_dict = {member.user.username: member for member in members}

    enrollment_attribute_dict = {}
    course = get_course(request.current_course.id)
    if course.is_status_managed:
        enrollment_attribute_dict = _set_attribute_value(course)

    for score_record in score_records:
        current_user_name = score_record[username_key]
        score_record = _change_of_value_name(score_record)
        score_record = _change_of_value_name(score_record)
        if course.is_status_managed:
            score_record = _set_student_status_record(score_record, enrollment_attribute_dict, current_user_name)

        member_record = {_("Organization Groups"): ''}
        if current_user_name in members_dict:
            m = members_dict[current_user_name]
            if is_manager and m.group and m.group.id not in child_group_ids:
                continue

            if m.group:
                member_record[_("Organization Groups")] = m.group.group_name
            for i in range(1, 11):
                member_record[_("Organization") + str(i)] = getattr(m, 'org' + str(i))
                member_record[_("Item") + str(i)] = getattr(m, 'item' + str(i))

        elif is_manager:
            continue

        if "search-download" not in request.POST:
            score_record.update(member_record)
            new_score_records.append(score_record)

    header, types = [], []
    score_columns.insert(1, (_("Organization Groups"), 'text'))
    for num in range(1, 11):
        score_columns.append([_("Organization") + str(num), 'text'])
    for num in range(1, 11):
        score_columns.append([_("Item") + str(num), 'text'])
    for column in score_columns:
        header.append(column[0])

    datarows = []
    for record in new_score_records:
        data = []
        for head, column_type in score_columns:
            if head in record:
                value = record[head]

                if column_type == ScoreStore.COLUMN_TYPE__TEXT:
                    if isinstance(value, basestring):
                        data.append(value)
                    else:
                        data.append('')
                elif column_type == ScoreStore.COLUMN_TYPE__DATE:
                    try:
                        value = datetime.strptime(value, '%Y/%m/%d %H:%M:%S %Z')
                        data.append(datetime_utils.to_jst(value).strftime('%Y/%m/%d'))
                    except:
                        data.append('')
                elif column_type == ScoreStore.COLUMN_TYPE__TIME:
                    if isinstance(value, numbers.Number):
                        # Convert seconds to 'h:mm' format
                        data.append(datetime_utils.seconds_to_time_format(value))
                    else:
                        data.append('0:00')
                elif column_type == ScoreStore.COLUMN_TYPE__PERCENT:
                    if value == ScoreStore.VALUE__NOT_ATTEMPTED:
                        # Note: '―'(U+2015) means 'Not Attempted' (#1816)
                        data.append(value)
                    elif isinstance(value, float):
                        data.append('{:.01%}'.format(value))
                    else:
                        data.append('')
                else:
                    data.append(value)
            else:
                data.append('')

        datarows.append(data)

    filename = u'{course_prefix}_{csv_name}_{timestamp_str}.csv'.format(
        course_prefix=course_filename_prefix_generator(request.current_course.id),
        csv_name='score_status',
        timestamp_str=update_datetime,
    )
    if 'encode' not in request.POST:
        request.POST['encode'] = 'false'
    if request.POST['encode'] == 'false':
        response = create_csv_response_double_quote(filename, header, datarows)
        response['Set-Cookie'] = 'fileDownload=true; path=/'
        return response
    elif request.POST['encode'] == 'true':
        response = create_tsv_response(filename, header, datarows)
        response['Set-Cookie'] = 'fileDownload=true; path=/'
        return response


@require_POST
@login_required
@check_course_selection
@check_organization_group
def playback_download_csv(request):
    """
    Returns response for download of score status csv

    :param request: HttpRequest
    :return: HttpResponse
    """
    org = request.current_organization
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    manager = request.current_manager

    batch_status = PlaybackBatchStatus.get_last_status(contract_id, course_id)
    if batch_status:
        update_datetime = datetime_utils.to_jst(batch_status.created).strftime('%Y-%m-%d-%H%M')
    else:
        update_datetime = 'no-timestamp'

    playback_store = PlaybackStore(contract_id, unicode(course_id))

    if "search-download" in request.POST:
        playback_columns, playback_records, __, new_playback_records = playback_search_filter(request, org, contract_id,
                                                                                              course_id, manager)
        playback_columns = _change_column(request, playback_columns)
    else:
        playback_columns, playback_records = playback_store.get_data_for_w2ui(limit=settings.BIZ_MONGO_LIMIT_RECORDS)
        playback_columns = _change_column(request, playback_columns)
        new_playback_records = []

    # Member
    username_key = _(PlaybackStore.FIELD_USERNAME)
    members = Member.find_active_by_org(org=org.id).select_related('user', 'group').filter(
        user__username__in=[s[username_key] for s in playback_records])

    is_manager = not manager.is_director() and manager.is_manager() and Group.objects.filter(org=org).exists()
    child_group_ids = request.current_organization_visible_group_ids
    members_dict = {member.user.username: member for member in members}

    enrollment_attribute_dict = {}
    course = get_course(request.current_course.id)
    if course.is_status_managed:
        enrollment_attribute_dict = _set_attribute_value(course)

    for playback_record in playback_records:
        current_username = playback_record[username_key]
        playback_record = _change_of_value_name(playback_record)
        if course.is_status_managed:
            playback_record = _set_student_status_record(playback_record, enrollment_attribute_dict, current_username)

        member_record = {_("Organization Groups"): ''}
        if current_username in members_dict:
            m = members_dict[current_username]
            if is_manager and m.group and m.group.id not in child_group_ids:
                continue

            if m.group:
                member_record[_("Organization Groups")] = m.group.group_name
            for i in range(1, 11):
                member_record[_("Organization") + str(i)] = getattr(m, 'org' + str(i))
                member_record[_("Item") + str(i)] = getattr(m, 'item' + str(i))

        elif is_manager:
            continue

        if "search-download" not in request.POST:
            playback_record.update(member_record)
            new_playback_records.append(playback_record)

    header, types = [], []
    playback_columns.insert(1, (_("Organization Groups"), 'text'))
    for num in range(1, 11):
        playback_columns.append([_("Organization") + str(num), 'text'])
    for num in range(1, 11):
        playback_columns.append([_("Item") + str(num), 'text'])
    for column in playback_columns:
        header.append(column[0])

    datarows = []
    for record in new_playback_records:
        data = []
        for head, column_type in playback_columns:
            if head in record:
                value = record[head]

                if column_type == PlaybackStore.COLUMN_TYPE__TEXT:
                    if isinstance(value, basestring):
                        data.append(value)
                    else:
                        data.append('')
                elif column_type == PlaybackStore.COLUMN_TYPE__DATE:
                    try:
                        value = datetime.strptime(value, '%Y/%m/%d %H:%M:%S %Z')
                        data.append(datetime_utils.to_jst(value).strftime('%Y/%m/%d'))
                    except:
                        data.append('')
                elif column_type == PlaybackStore.COLUMN_TYPE__TIME:
                    if isinstance(value, numbers.Number):
                        # Convert seconds to 'h:mm' format
                        data.append(datetime_utils.seconds_to_time_format(value))
                    else:
                        data.append('0:00')
                elif column_type == PlaybackStore.COLUMN_TYPE__PERCENT:
                    if value == PlaybackStore.VALUE__NOT_ATTEMPTED:
                        # Note: '―'(U+2015) means 'Not Attempted' (#1816)
                        data.append(value)
                    elif isinstance(value, float):
                        data.append('{:.01%}'.format(value))
                    else:
                        data.append('')
                else:
                    data.append(value)
            else:
                data.append('')
        datarows.append(data)

    filename = u'{course_prefix}_{csv_name}_{timestamp_str}.csv'.format(
        course_prefix=course_filename_prefix_generator(request.current_course.id),
        csv_name='playback_status',
        timestamp_str=update_datetime,
    )
    if 'encode' not in request.POST:
        request.POST['encode'] = 'false'
    if request.POST['encode'] == 'false':
        response = create_csv_response_double_quote(filename, header, datarows)
        response['Set-Cookie'] = 'fileDownload=true; path=/'
        return response
    elif request.POST['encode'] == 'true':
        response = create_tsv_response(filename, header, datarows)
        response['Set-Cookie'] = 'fileDownload=true; path=/'
        return response


def _get_member_org_item_list():
    member_org_item_list = OrderedDict()
    member_org_item_list.update([('org' + str(i), _("Organization") + str(i)) for i in range(1, 11)])
    member_org_item_list.update([('item' + str(i), _("Item") + str(i)) for i in range(1, 11)])
    return member_org_item_list


def score_search_filter(request, org, contract_id, course_id, manager):
    total_score_no = 'total_score_no' in request.POST
    total_score_from = request.POST['total_score_from']
    total_score_to = request.POST['total_score_to']
    total_condition = {
        'no': total_score_no,
        'from': total_score_from if len(total_score_from) else None,
        'to': total_score_to if len(total_score_to) else None,
    }
    certificate_status = request.POST['certificate_status']

    section_score_conditions = []
    score_counter = 1
    while 'detail_condition_score_name_' + str(score_counter) in request.POST:
        count = str(score_counter)
        score_counter += 1
        condition = {}
        name = request.POST['detail_condition_score_name_' + count]
        from_val = request.POST['detail_condition_score_from_' + count]
        to_val = request.POST['detail_condition_score_to_' + count]
        if name:
            condition['name'] = name
            condition['from'] = from_val if len(from_val) else None
            condition['to'] = to_val if len(to_val) else None
            condition['no'] = 'detail_condition_score_no_' + count in request.POST
            section_score_conditions.append(condition)

    record_offset = int(request.POST['offset'])
    score_store = ScoreStore(contract_id, unicode(course_id))
    score_columns, score_records = score_store.get_data_for_w2ui(total_condition=total_condition,
                                                                 section_conditions=section_score_conditions,
                                                                 certificate_status=certificate_status,
                                                                 limit=settings.BIZ_MONGO_LIMIT_RECORDS)
    total_records = len(score_records)

    # Member
    new_score_records = _merge_to_store_by_member_for_search(
        request, org, request.current_organization_visible_group_ids, manager, _(ScoreStore.FIELD_USERNAME),
        score_records, True)

    return score_columns, score_records, total_records, new_score_records


def playback_search_filter(request, org, contract_id, course_id, manager):
    total_playback_no = 'total_playback_no' in request.POST
    total_playback_from = request.POST['total_playback_time_from']
    total_playback_to = request.POST['total_playback_time_to']

    total_condition = {
        'no': total_playback_no,
        'from': (int(total_playback_from) * 60) - 60 if len(total_playback_from) else None,
        'to': int(total_playback_to) * 60 if len(total_playback_to) else None,
    }

    section_playback_conditions = []
    playback_counter = 1
    while 'detail_condition_playback_name_' + str(playback_counter) in request.POST:
        count = str(playback_counter)
        playback_counter += 1
        condition = {}
        name = request.POST['detail_condition_playback_name_' + count]
        from_val = request.POST['detail_condition_playback_from_' + count]
        to_val = request.POST['detail_condition_playback_to_' + count]
        if name:
            condition['name'] = name
            condition['from'] = (int(from_val) * 60) - 60 if len(from_val) else None
            condition['to'] = int(to_val) * 60 if len(to_val) else None
            condition['no'] = 'detail_condition_playback_no_' + count in request.POST
            section_playback_conditions.append(condition)

    record_offset = int(request.POST['offset'])
    playback_store = PlaybackStore(contract_id, unicode(course_id))
    playback_columns, playback_records = playback_store.get_data_for_w2ui(total_condition=total_condition,
                                                         section_conditions=section_playback_conditions,
                                                         limit=MAX_RECORDS_SEARCH_BY_PLAYBACK)
    total_records = len(playback_records)

    # Member
    new_playback_records = _merge_to_store_by_member_for_search(
        request, org, request.current_organization_visible_group_ids, manager, _(PlaybackStore.FIELD_USERNAME),
        playback_records, True)

    return playback_columns, playback_records, total_records, new_playback_records


def _merge_to_store_by_member_for_search(
        request, org, child_group_ids, manager, merge_key, store_list, search_flg=False):
    """
    Member data merge to Store data.
    :param request:
    :param org: request.current_organization
    :param child_group_ids: request.current_organization_visible_group_ids
    :param manager: request.current_manager
    :param merge_key: _('Username') (ScoreStore.FIELD_USERNAME or PlayBackStore.FIELD_USERNAME)
    :param store_list: [{},..] playback or score
    :param search_flg bool
    :return: result list
    """
    result = []
    is_manager = not manager.is_director() and manager.is_manager() and Group.objects.filter(org=org).exists()

    select_columns = dict({
        'user_name': 'user__username',
        'group_id': 'group__id',
        'group_name': 'group__group_name'
    })
    select_columns.update({'org' + str(i): 'org' + str(i) for i in range(1, 11)})
    select_columns.update({'item' + str(i): 'item' + str(i) for i in range(1, 11)})

    members = Member.find_active_by_org(org=org.id).select_related('user', 'group').filter(
        user__username__in=[s[merge_key] for s in store_list]).values(*select_columns.values())
    members_dict = {member[select_columns.get('user_name')]: member for member in members}

    enrollment_attribute_dict = {}
    course = get_course(request.current_course.id)
    if course.is_status_managed:
        enrollment_attribute_dict = _set_attribute_value(course)

    for store_record in store_list:
        insert_flag = True
        current_user_name = store_record[merge_key]
        store_record = _change_of_value_name(store_record)
        if course.is_status_managed:
            store_record = _set_student_status_record(store_record, enrollment_attribute_dict, current_user_name)

        if current_user_name in members_dict:
            member = members_dict[current_user_name]

            if search_flg:
                counter = 1
                while 'detail_condition_member_name_' + str(counter) in request.POST:
                    count = str(counter)
                    counter += 1
                    key = request.POST['detail_condition_member_name_' + count]
                    value = request.POST['detail_condition_member_' + count]
                    if key != '' and value not in member[select_columns.get(key)]:
                        insert_flag = False
                        break

                if request.POST['group_code'] and request.POST['group_code'] != str(
                        member[select_columns.get('group_id')]):
                    continue

            if is_manager and member[select_columns.get('group_id')] not in child_group_ids:
                continue

            member_record = {
                _("Organization Groups"): member[
                    select_columns.get('group_name')] if member[select_columns.get('group_id')] else ''
            }
            for i in range(1, 11):
                member_record[_("Organization") + str(i)] = member[select_columns.get('org' + str(i))]
                member_record[_("Item") + str(i)] = member[select_columns.get('item' + str(i))]

            store_record.update(member_record)
        else:
            if is_manager:
                continue

            if search_flg:
                counter = 1
                while 'detail_condition_member_name_' + str(counter) in request.POST:
                    if request.POST['detail_condition_member_name_' + str(counter)] != '':
                        insert_flag = False
                        break
                    counter += 1
                if request.POST['group_code'] != '':
                    continue

        if search_flg:
            student_status = request.POST['student_status']
            if student_status:
                if student_status != store_record[_("Student Status")]:
                    insert_flag = False

        if insert_flag:
            result.append(store_record)

    return result


def _change_column(request, columns):
    course = get_course(request.current_course.id)
    for i, column in enumerate(columns):
        if column[0] == _("Student Status"):
            columns.insert(i, (_("Register Status"), 'text'))
            break

    if not course.is_status_managed:
        for i, column in enumerate(columns):
            if column[0] == _("Student Status"):
                columns.pop(i)
                break

    return columns


def _set_attribute_value(course):
    enrollment_ids = []
    enroll_dict = {}
    enrollment_attribute_dict = {}
    for enrollment in CourseEnrollment.objects.filter(course_id=course.id).values('id', 'user__username'):
        if enrollment_ids.count(enrollment['id']) is 0:
            enrollment_ids.append(enrollment['id'])
            enroll_dict[enrollment['id']] = enrollment['user__username']
    if enrollment_ids:
        enrollment_attribute = AttendanceStatusExecutor.get_attendance_values(enrollment_ids)
        for enrollment_id, enrollment_username in enroll_dict.items():
            if enrollment_id in enrollment_attribute:
                enrollment_attribute_dict[enrollment_username] = enrollment_attribute[enrollment_id]

    return enrollment_attribute_dict


def _set_student_status_record(record, attr_dict, username):
    if username in attr_dict:
        if AttendanceStatusExecutor.attendance_status_is_completed(attr_dict[username]):
            record[_("Student Status")] = _("Finish Enrolled")
        elif AttendanceStatusExecutor.attendance_status_is_attended(attr_dict[username]):
            record[_("Student Status")] = _("Enrolled")
        else:
            record[_("Student Status")] = _("Not Enrolled")

    else:
        record[_("Student Status")] = _("Not Enrolled")

    return record


def _change_of_value_name(record):
    if record[_("Student Status")] == _('Not Enrolled'):
        record[_("Register Status")] = _("Unregistered")

    elif record[_("Student Status")] == _('Enrolled'):
        record[_("Register Status")] = _("During registration")

    elif record[_("Student Status")] == _('Unenrolled'):
        record[_("Register Status")] = _("Registration cancellation")

    else:
        record[_("Register Status")] = record[_("Student Status")]

    return record

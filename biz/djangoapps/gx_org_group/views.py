# -*- coding:UTF-8 -*-
"""
Views for org group feature
"""
import json
import logging
import re
from datetime import datetime
from util.json_request import JsonResponse, JsonResponseBadRequest

from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import cache_control
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from edxmako.shortcuts import render_to_response

from biz.djangoapps.ga_manager.models import Manager
from biz.djangoapps.gx_org_group.builders import OrgTsv
from biz.djangoapps.gx_org_group.models import Group, Right, Parent, Child
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.util.decorators import check_course_selection
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder, LazyEncoder
from biz.djangoapps.util.unicodetsv_utils import get_utf8_csv, create_tsv_response

_exception_001 = _('specified email could not found: ')               # grant error case 'a'
_exception_002 = _('specified username could not found: ')            # grant error case 'b'
_exception_003 = _('specified user is not in a manager group: ')      # grant error case 'c'
_exception_004 = _("specified user doesn't have manager right: ")     # grant error case 'd'
_exception_007 = _('specified user is already existed: ')             # grant error case 'e'
_exception_005 = _('specified user has right in parent group: ')      # grant error case 'f'
_exception_006 = _('specified user has right in child group: ')       # grant error case 'g'
_exception_011 = _('specified user does not exist')                   # revoke error case 'a'
_exception_012 = _('specified user does not exist in this group')     # revoke error case 'b'
_exception_021 = _('invalid header or file type')                     # file upload error case 'a'
_exception_999 = _('unknown error')                                   # revoke error case 'c'
_button_01 = _('detail settings')
_button_02 = _('Delete')

log = logging.getLogger(__name__)

from django.db import connection
class UploadEncoder(LazyEncoder, EscapedEdxJSONEncoder):
    pass


class GroupEncoder(LazyEncoder, EscapedEdxJSONEncoder):
    pass


class RightEncoder(LazyEncoder, EscapedEdxJSONEncoder):
    pass


def _get_group_list_view(org_id):
    """
    :param org_id:
    :return:
    """
    group_db_table = Group._meta.db_table
    groups = Group.objects.filter(org_id=org_id).extra(
        select={
            'parent_code': "select a.group_code from " + group_db_table
                           + " a where a.id = " + group_db_table + ".parent_id",
            'parent_name': "select a.group_name from " + group_db_table
                           + " a where a.id = " + group_db_table + ".parent_id",
        },
    ).values(
        'group_code', 'group_name', 'parent_code', 'parent_name', 'notes', 'created', 'modified', 'id'
    ).order_by('level_no', 'group_code')
    return groups


def _get_group_tree_list(org_id, parent_id, level_no):
    current_group = Group.objects.filter(org_id=org_id, parent_id=parent_id, level_no=level_no).order_by('level_no', 'group_code')
    records = []
    for grp in current_group:
        records_value = {}
        records_value['recid'] = grp.id
        records_value['group_code'] = grp.group_code
        records_value['group_name'] = grp.group_name
        records_value['edit'] = _(_button_01)
        records_value['delete'] = _(_button_02)
        records_value['notes'] = grp.notes
        records_value['created'] = grp.created
        records_value['modified'] = grp.modified
        records_value['id'] = grp.id
        records_value['detail_url'] = reverse('biz:group:detail', kwargs={'selected_group_id': records_value['id']})
        records_value['belong'] = 0
        right = _get_child(grp.id)
        right.append(grp.id)
        if Right.objects.only('group_id').filter(group_id__in=right):
            records_value['belong'] = 1
        if Member.objects.only('group_id').filter(group_id__in=right):
            records_value['belong'] = 1
        records_value['grouping'] = right
        childrens = {}
        childrens['children'] = _get_group_tree_list(org_id=org_id, parent_id=grp.id, level_no=level_no + 1)
        records_value['w2ui'] = childrens
        records.append(records_value)
    return records


def _error_response(message):
    return JsonResponseBadRequest({
        'error': message,
    })


@require_POST
@login_required
@check_course_selection
def delete_group(request):
    """
    Do Delete choice Organization tree
    :param request:
    :return:
    """
    log.info('delete_group function - start')
    org = request.current_organization
    org_tsv = OrgTsv(org, request.user)
    try:
        group = request.POST.dict()
        grouping = str(group['grouping']).split(',')
        grouping = [int(x) for x in grouping]

        member = Member.objects.filter(group_id__in=grouping).update(group_id=None)
        log.info('update member model to null - record count: ' + str(member) + ' - done')

        Group.objects.filter(id__in=grouping).delete()
        log.info('delete model related to group - id' + str(grouping) + ':' + group['group_name'] + ' - done')

        org_tsv.make_child_data()
        log.info('refresh child model - done')
        log.info('delete_group function - end')
        return JsonResponse({'info': _('Success! Current group and children deleted ')})
    except Exception:
        log.error('Critical error! Failed to delete group tree')
        return _error_response(_exception_999)


@require_GET
@login_required
@check_course_selection
def group_list(request):
    """
    Shows group list
    :param request:
    :return:
    """
    org_id = request.current_organization.pk
    return render_to_response('gx_org_group/group_list.html', {
        'groups': json.dumps(_get_group_tree_list(org_id, 0, 0), cls=GroupEncoder)
    })


@require_GET
@login_required
@check_course_selection
def detail(request, selected_group_id):
    """
    Shows group detail to show access right
    :param request:
    :param selected_group_id:
    :return:
    """
    # selected organization id
    current_org = request.current_organization
    # Check the existences of the selected group
    groups = _get_group_list_view(current_org.pk)
    selected_group = get_object_or_404(groups, pk=selected_group_id)
    # get rights from parent group
    rights = []
    parent_list = Parent.objects.filter(group_id=selected_group_id)
    if parent_list:
        for parent in parent_list:
            parent_path = []
            if parent.path != '':
                parent_path = [int(s) for s in parent.path.split(',')]
            for group_id in parent_path:
                for right in Right.objects.filter(org_id=current_org.pk).filter(group_id=group_id):
                    parent_group = Group.objects.get(id=group_id)
                    record = {
                        'username': right.user.username,
                        'email': right.user.email,
                        'op': parent_group.group_code + ":" + parent_group.group_name,
                        'group_code': parent_group.group_code,
                        'revoke_right_url': '',
                    }
                    rights.append(record)
    return render_to_response("gx_org_group/detail.html", {
        'group_id': selected_group_id,
        'group_code': selected_group['group_code'],
        'group_name': selected_group['group_name'],
        'notes': selected_group['notes'],
        'return_url': 'biz/group',
    })


def _revoke_right(revoke_right_id):
    """
    Revokes access right from organization group
    :param revoke_right_id:
    :return:
    """
    right1 = Right.objects.get(id=revoke_right_id)
    right1.delete()
    return


def _get_parent(group_id):
    parent = Parent.objects.get(group_id=group_id)
    if parent.path is None or parent.path == '':
        return []
    groups = [int(s) for s in parent.path.split(",")]
    return groups


def _get_child(group_id):
    children = Child.objects.get(group_id=group_id)
    if children.list is None or children.list == '':
        return []
    groups = [int(s) for s in children.list.split(',')]
    return groups


def _grant_right(user, current_org, group_id, grant_user_str):
    """
    Grants access right to specified user
    :param user:
    :param current_org:
    :param group_id:
    :param grant_user_str:
    :return:
    """
    log.info('grant right - ' + grant_user_str + ' - search')
    pat = re.compile('[^@]+@[^@]+')
    email_flag = pat.match(grant_user_str)
    if email_flag:   # email
        try:
            grant_user = User.objects.get(email=grant_user_str)
        except ObjectDoesNotExist:
            raise ValueError(_exception_001 + grant_user_str)
    if not email_flag:                          # username
        try:
            grant_user = User.objects.get(username=grant_user_str)
        except ObjectDoesNotExist:
            raise ValueError(_exception_002 + grant_user_str)
    log.info('grant right - ' + grant_user_str + ' - check manager or not')
    try:
        manager = Manager.objects.filter(org=current_org).get(user=grant_user)
    except ObjectDoesNotExist:
        raise ValueError(_exception_003)
    if not manager.is_manager():
        raise ValueError(_exception_004 + grant_user_str)
    log.info('grant right - ' + grant_user_str + ' - check current group')
    # check current group
    exists = Right.objects.filter(org=current_org).filter(group_id=group_id).filter(user_id=manager.user.id)
    if exists:
        raise ValueError(_exception_007 + grant_user_str)
    # check duplicate user in parent group
    log.info('grant right - ' + grant_user_str + ' - check parent group')
    parents = _get_parent(group_id)
    for parent in parents:
        exists = Right.objects.filter(org=current_org).filter(group_id=parent).filter(user_id=manager.user.id)
        if exists:
            raise ValueError( _exception_005 + grant_user_str)
    # check duplicate user in children group
    log.info('grant right - ' + grant_user_str + ' - check child group')
    children = _get_child(group_id)
    for child in children:
        exists = Right.objects.filter(org=current_org).filter(group_id=child).filter(user_id=manager.user.id)
        if exists:
            raise ValueError(_exception_006 + grant_user_str)
    Right.objects.create(creator_org=current_org, org=current_org, created_by=user, group_id=group_id,
                         user_id=manager.user.id)
    log.info('grant right - ' + grant_user_str + ' - done')
    return grant_user


@require_POST
@login_required
@check_course_selection
def grant_right(request):
    """
    grant access right to current group
    :param request:
    :return:
    """
    group_id = request.POST.get('group_id')
    grant_user_str = request.POST.get('grant_user_str')
    action = request.POST.get('action')
    current_org = request.current_organization
    if action == 'revoke':
        revoke_user = None
        try:
            log.info("revoke: get user=" + grant_user_str)
            revoke_user = User.objects.get(username=grant_user_str)
            log.info("revoke: get revoke_user=" + str(revoke_user))
            revoke_right = Right.objects.filter(group_id=group_id).get(user=revoke_user)
            _revoke_right(revoke_right.id)
        except ObjectDoesNotExist:
            if revoke_user is None:
                log.warn(_exception_011)
                return _ajax_fail_response(_exception_011)
            log.warn(_exception_012)
            return _ajax_fail_response(_exception_012)
        response_payload = {
            'name': revoke_user.username,
            'email': revoke_user.email,
            'success': True,
        }
    elif action == 'allow':
        try:
            user = request.user
            grant_user = _grant_right(user, current_org, group_id, grant_user_str)
        except ValueError as e:
            log.warning(e.message)
            return _ajax_fail_response(e.message)
        response_payload = {
            'name': grant_user.username,
            'email': grant_user.email,
            'success': True,
        }
    return JsonResponse(response_payload)


def _ajax_fail_response(message):
    response_payload = {
        'message': message,
        'success': False,
    }
    return JsonResponse(response_payload)


@require_POST
@login_required
@check_course_selection
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def accessible_parent_list(request):
    """
    Returns accessible user list in parent group
    :param request:
    :return:
    """
    current_org = request.current_organization
    selected_group_id = request.POST.get('group_id')
    show_list = []
    parents = _get_parent(selected_group_id)
    for parent in parents:
        parent_rights = Right.objects.filter(org=current_org).filter(group_id=parent)
        for parent_right in parent_rights:
            show_list.append({
                'parent_name': parent_right.user.username,
                'parent_email': parent_right.user.email,
                'parent_group': parent_right.group.group_name,
            })
    response_payload = {
        'show_list': show_list,
        'success': True,
    }
    return JsonResponse(response_payload)


@require_POST
@login_required
@check_course_selection
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def accessible_user_list(request):
    """
    Returns accessible user list in selected group
    :param request:
    :return:
    """
    current_org = request.current_organization
    selected_group_id = request.POST.get('group_id')

    # get rights from current group
    managers = Right.objects.filter(org_id=current_org.pk).filter(group_id=selected_group_id)
    show_list =[]
    for manager in managers:
        show_list.append({
            'name': manager.user.username,
            'email': manager.user.email,
        })
    response_payload = {
        'show_list': show_list,
        'success': True,
    }
    return JsonResponse(response_payload)


@require_POST
@login_required
@check_course_selection
def download_csv(request):
    """
    Download file
    :param request:
    :return:
    """
    org = request.current_organization
    org_tsv = OrgTsv(org, request.user)
    groups = _get_group_list_tsv(org.id, org_tsv.column_list.keys())
    current_datetime = datetime.now()
    date_str = current_datetime.strftime("%Y-%m-%d-%H%M")
    filename = org.org_code + '_' + date_str + '.csv'
    return create_tsv_response(filename, org_tsv.column_list.values(), groups)


@require_POST
@login_required
@check_course_selection
def upload_csv(request):
    """
    upload tsv file from browser
    :param request:
    :return:
    """
    user = request.user
    org = request.current_organization
    input_file = 'org_group_csv'
    if input_file not in request.FILES or 'organization' not in request.POST:
        return _upload_error_response(_("Unauthorized access."))
    error_messages = []
    ret = 0
    try:
        lines = get_utf8_csv(request, input_file)
    except UnicodeDecodeError:
        return _upload_error_response(_exception_021)
    try:
        org_tsv = OrgTsv(org, user)
        ret = org_tsv.import_data(lines)
    except ValueError as err:
        if isinstance(err.message, list):
            for message in err.message:
                error_messages.append(message)
        else:
            error_messages.append(err.message)

    if len(error_messages) == 0:
        return JsonResponse({'completed_records': str(ret)})
    else:
        return _upload_error_response(error_messages)


def _upload_error_response(messages):
    if isinstance(messages, list):
        message_list = sorted(messages)
    else:
        message_list = [messages]
    for line in message_list:
        log.warn(line)
    return JsonResponseBadRequest({
        'errors': message_list,
    }, 400, UploadEncoder)


def _sql_none_to_empty(str1):
    return "ifnull((" + str1 + "), '' )"


def _get_group_list_tsv(org_id, column_list):
    """
    get group list for tsv file
    :param org_id:
    :param column_list:
    :return:
    """
    order_by = 'group_code'
    group_db_table = Group._meta.db_table
    groups = Group.objects.filter(org_id=org_id).extra(
        select={
            'parent_code':
                _sql_none_to_empty("select a.group_code from " + group_db_table + " a "
                                  + "where a.id = " + group_db_table + ".parent_id"),
            'parent_name':
                _sql_none_to_empty("select a.group_name from " + group_db_table + " a "
                                  + "where a.id = " + group_db_table + ".parent_id"),
        },
    ).values_list(*column_list).order_by(order_by)
    return groups


# -*- coding: utf-8 -*-
import logging
import json
import math
from datetime import datetime
from celery.states import READY_STATES

from django.db import transaction
from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_organization.models import OrganizationOption
from biz.djangoapps.gx_member.models import Group
from biz.djangoapps.gx_member.models import MemberTaskHistory, MemberRegisterTaskTarget
from biz.djangoapps.gx_member.forms import MemberUserCreateForm
from biz.djangoapps.gx_member.builders import MemberTsv
from biz.djangoapps.gx_member.tasks import MEMBER_REGISTER, member_register, member_register_one
from biz.djangoapps.util.decorators import check_course_selection
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder
from biz.djangoapps.util.task_utils import submit_org_task
from biz.djangoapps.util.unicodetsv_utils import create_tsv_response, create_csv_response_double_quote, get_sjis_csv

from edxmako.shortcuts import render_to_response
from openedx.core.lib.ga_datetime_utils import to_timezone
from openedx.core.djangoapps.ga_task.models import Task
from util.json_request import JsonResponse, JsonResponseBadRequest

log = logging.getLogger(__name__)


def _get_or_create_organization_option(user, org):
    options = OrganizationOption.objects.filter(org=org)
    if len(options) == 0:
        return OrganizationOption.objects.create(org=org, modified_by=user)
    else:
        return options[0]


@require_GET
@login_required
@check_course_selection
def index(request):
    """
    Show member user form view

    :param request: HttpRequest
    :return: HttpResponse
    """
    current_org = request.current_organization
    auto_mask_flg = _get_or_create_organization_option(org=current_org, user=request.user).auto_mask_flg

    return render_to_response('gx_member/index.html', {
        'org_group_list': Group.objects.filter(org=current_org).order_by('group_code'),
        'auto_mask_flg': 1 if auto_mask_flg else 0
    })


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
def register_ajax(request):
    """
    Create/Update member user form view

    :param request: HttpRequest
    :return: HttpResponse
    """
    user = request.user
    current_org = request.current_organization
    errors = []
    members = []

    form = MemberUserCreateForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        # Set initial data of group
        data['group'] = None
        if data['group_code']:
            if Group.objects.filter(group_code=data['group_code'], org=current_org).exists():
                group = Group.objects.filter(group_code=data['group_code'], org=current_org).first()
                data['group'] = group.id
            else:
                errors.append(_("Organization Groups is not found by organization."))

        members.append(json.dumps(data, cls=EscapedEdxJSONEncoder))
    else:
        errors.extend(form.format_errors(False))

    if len(errors) != 0:
        return _error_response(errors)
    else:
        history = MemberTaskHistory.create(current_org, user)
        MemberRegisterTaskTarget.bulk_create(history, members)

        task_input = {
            'organization_id': current_org.id,
            'history_id': history.id,
        }
        return submit_org_task(
            request, current_org, task_input, MEMBER_REGISTER, member_register_one, MemberTaskHistory, history)


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
def register_csv_ajax(request):
    """
    Create/Update member user by file form view
    :param request: HttpRequest
    :return: HttpResponse
    """
    if 'member_csv' not in request.FILES or 'organization' not in request.POST:
        return _error_response(_("Unauthorized access."))

    user = request.user
    current_org = request.current_organization
    errors = []
    members = []

    # Read file
    try:
        lines = get_sjis_csv(request, 'member_csv')
        if len(lines) is 0:
            return _error_response(_("The file is empty."))
    except UnicodeDecodeError:
        return _error_response(_("invalid header or file type"))

    # Read row in file
    checks = {'emails': [], 'usernames': [], 'codes': []}
    group_info = {}
    tsv = MemberTsv(current_org)
    line_error_message = _("Line {line_number}:{message}")

    # Check header
    header_line = lines.pop(0)
    if header_line != tsv.headers_for_export:
        return _error_response(_("invalid header or file type"))

    for current_index, line in enumerate(lines, start=1):
        current_index_str = str(current_index)
        # Check column rows number
        if len(line) != len(tsv.headers_for_import):
            errors.append(line_error_message.format(
                line_number=current_index_str, message=_("The number of columns did not match.")))
            continue

        member = tsv.get_dic_by_import_row(line)
        form = MemberUserCreateForm(data=member)

        if form.is_valid():
            # Unique check
            if checks['emails'].count(member['email']) is 0:
                checks['emails'].append(member['email'])
            else:
                errors.append(line_error_message.format(
                    line_number=current_index_str, message=_("Email is already used in file.")))

            if checks['usernames'].count(member['username']) is 0:
                checks['usernames'].append(member['username'])
            else:
                errors.append(line_error_message.format(
                    line_number=current_index_str, message=_("Username is already used in file.")))

            if checks['codes'].count(member['code']) is 0:
                checks['codes'].append(member['code'])
            else:
                errors.append(line_error_message.format(
                    line_number=current_index_str, message=_("Member code is already used in file.")))

            # Group check and get group id
            member['group'] = None
            if member['group_code']:
                if member['group_code'] in group_info:
                    member['group'] = group_info[member['group_code']]
                else:
                    if Group.objects.filter(group_code=member['group_code'], org=current_org).exists():
                        group = Group.objects.filter(group_code=member['group_code'], org=current_org).first()
                        group_info[group.group_code] = group.id
                        member['group'] = group.id
                    else:
                        errors.append(line_error_message.format(
                            line_number=current_index_str,
                            message=_("Organization Groups is not found by organization."))
                        )

            # Add task target
            members.append(json.dumps(member, cls=EscapedEdxJSONEncoder))
        else:
            errors.extend(form.format_errors(line_number=current_index_str))

    if len(errors) != 0:
        return _error_response(errors)
    else:
        history = MemberTaskHistory.create(current_org, user)
        # Repeat register 1000, because timeout of mysql connection.
        task_target_max_num = 1000
        for i in range(1, int(math.ceil(float(len(members)) / task_target_max_num)) + 1):
            MemberRegisterTaskTarget.bulk_create(
                history, members[(i - 1) * task_target_max_num:i * task_target_max_num])

        task_input = {
            'organization_id': current_org.id,
            'history_id': history.id,
        }
        return submit_org_task(
            request, current_org, task_input, MEMBER_REGISTER, member_register, MemberTaskHistory, history)


@require_POST
@login_required
@check_course_selection
def task_history_ajax(request):
    """
    Get member task history.
    :param request:
    :return:
    """
    current_organization = request.current_organization
    limit = int(request.POST['limit']) if 'limit' in request.POST else 0

    def _task_result(task_output_str):
        task_output = json.loads(task_output_str)
        return _("Total: {total}, Success: {succeeded}, Skipped: {skipped}, Failed: {failed}").format(
            total=task_output.get('total', 0), succeeded=task_output.get('succeeded', 0),
            skipped=task_output.get('skipped', 0), failed=task_output.get('failed', 0)
        )

    if MemberTaskHistory.find_by_organization(organization=current_organization).exists():
        results = []
        if limit == 0:
            histories = MemberTaskHistory.find_by_organization(organization=current_organization)
        else:
            histories = MemberTaskHistory.find_by_organization(organization=current_organization)[:limit]

        for i, history in enumerate(histories, start=1):
            try:
                task = Task.objects.get(task_id=history.task_id)
            except Task.DoesNotExist:
                log.warning("Can not find Task by member task history")
                continue

            if task.task_state not in READY_STATES:
                result = _("Processing of {task_type} is running.").format(task_type=_("Member Register"))
                result_message = _("Task is being executed. Please wait a moment.")
                messages = []
            else:
                result = _("Success") if history.result == 1 else _("Failed")
                result_message = _task_result(task.task_output)
                messages = [{
                    'recid': j,
                    'message': message if message else '',
                } for j, message in enumerate(history.messages.split(',') if history.messages else [], start=1)]

            results.append({
                'recid': i,
                'result': result,
                'result_message': result_message,
                'messages': messages,
                'created': to_timezone(history.created).strftime('%Y/%m/%d %H:%M:%S') if history.created else '',
                'updated': to_timezone(history.updated).strftime('%Y/%m/%d %H:%M:%S') if history.updated else '',
                'requester': history.requester.username,
            })

        return JsonResponse({
            'status': 'success',
            'total': len(results),
            'records': results,
        })
    else:
        return JsonResponse({
            'info': _("Task is not found.")
        })


@require_POST
@login_required
@check_course_selection
def download_ajax(request):
    if 'organization' not in request.POST:
        return _error_response(_("Unauthorized access."))

    current_org = request.current_organization

    tsv = MemberTsv(current_org)
    headers = tsv.headers_for_export
    rows = tsv.get_rows_for_export()

    org_name = current_org.org_name
    current_datetime = datetime.now()
    date_str = current_datetime.strftime("%Y-%m-%d-%H%M")
    if 'encode' in request.POST:
        return create_tsv_response(org_name + '_member_' + date_str + '.csv', headers, rows)
    else:
        return create_csv_response_double_quote(org_name + '_member_' + date_str + '.csv', headers, rows)


@require_POST
@login_required
@check_course_selection
def update_auto_mask_flg_ajax(request):
    if any(i not in request.POST for i in ['organization', 'auto_mask_flg']):
        return _error_response(_("Unauthorized access."))

    param_flg = request.POST.get('auto_mask_flg')
    option = _get_or_create_organization_option(org=request.current_organization, user=request.user)

    option.auto_mask_flg = True if int(param_flg) == 1 else False
    option.modified_by = request.user
    option.save()

    return JsonResponse({
        'info': _('Success'),
    })


@require_POST
@login_required
@check_course_selection
def download_headers_ajax(request):
    if 'organization' not in request.POST:
        return _error_response(_("Unauthorized access."))

    current_org = request.current_organization

    tsv = MemberTsv(current_org)
    headers = tsv.headers_for_export

    org_name = current_org.org_name
    current_datetime = datetime.now()
    date_str = current_datetime.strftime("%Y-%m-%d-%H%M")
    return create_csv_response_double_quote(org_name + '_member_template_' + date_str + '.csv', headers, rows='')


def _error_response(message):
    return JsonResponseBadRequest({
        'error': message,
    })
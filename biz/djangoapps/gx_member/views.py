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

from biz.djangoapps.gx_member.models import Group
from biz.djangoapps.gx_member.models import MemberTaskHistory, MemberRegisterTaskTarget
from biz.djangoapps.gx_member.forms import MemberUserCreateForm
from biz.djangoapps.gx_member.builders import MemberTsv
from biz.djangoapps.gx_member.tasks import TASKS, MEMBER_REGISTER, member_register, member_register_one
from biz.djangoapps.util.decorators import check_course_selection
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder
from biz.djangoapps.util.task_utils import submit_task, validate_task, get_org_task_key
from biz.djangoapps.util.unicodetsv_utils import get_utf8_csv, create_tsv_response

from edxmako.shortcuts import render_to_response
from openedx.core.lib.ga_datetime_utils import to_timezone
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.api import AlreadyRunningError
from util.json_request import JsonResponse, JsonResponseBadRequest

log = logging.getLogger(__name__)


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

    return render_to_response('gx_member/index.html', {
        'org_group_list': Group.objects.filter(org=current_org).order_by('group_code'),
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
        return _submit_task(request, MEMBER_REGISTER, member_register_one, MemberTaskHistory, history)


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
        lines = get_utf8_csv(request, 'member_csv')
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

        return _submit_task(request, MEMBER_REGISTER, member_register, MemberTaskHistory, history)


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
    return create_tsv_response(org_name + '_member_' + date_str + '.csv', headers, rows)


def _error_response(message):
    return JsonResponseBadRequest({
        'error': message,
    })


def _submit_task(request, task_type, task_class, history_cls, history):
    try:
        task_input = {
            'organization_id': request.current_organization.id,
            'history_id': history.id,
        }

        # Check the task running within the same current_organization.
        validate_task_message = validate_task(request.current_organization)
        if validate_task_message:
            return _error_response(validate_task_message)

        # task prevents duplicate execution by current_organization_id
        task = submit_task(request, task_type, task_class, task_input, get_org_task_key(request.current_organization))
        history = history_cls.objects.get(pk=history.id)
        history.link_to_task(task)

    except AlreadyRunningError:
        return _error_response(
            _("Processing of {task_type} is running.").format(task_type=TASKS[task_type]) +
            _("Execution status, please check from the task history.")
        )

    return JsonResponse({
        'info': _("Began the processing of {task_type}.")
                    .format(task_type=TASKS[task_type]) + _("Execution status, please check from the task history."),
    })

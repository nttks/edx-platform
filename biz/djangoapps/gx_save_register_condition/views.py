"""
Views for save condition feature
"""
import json
import logging
from collections import OrderedDict
from celery.states import READY_STATES
from datetime import datetime, timedelta
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST
from biz.djangoapps.ga_contract.models import Contract, AdditionalInfo, ContractOption
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_member.tasks import TASKS, REFLECT_CONDITIONS_IMMEDIATE, reflect_conditions_immediate
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_save_register_condition.models import (
    ParentCondition, ChildCondition, ReflectConditionTaskHistory)
from biz.djangoapps.gx_save_register_condition.reflect_conditions import (
    TASK_PROGRESS_META_KEY_REGISTER, TASK_PROGRESS_META_KEY_UNREGISTER, TASK_PROGRESS_META_KEY_MASK)
from biz.djangoapps.gx_save_register_condition.utils import (
    get_members_by_child_conditions, get_members_by_all_parents_conditions, IMMEDIATE_REFLECT_MAX_SIZE)
from biz.djangoapps.util.decorators import check_course_selection, check_organization_group
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder
from biz.djangoapps.util.task_utils import submit_org_task
from edxmako.shortcuts import render_to_response
from openedx.core.lib.ga_datetime_utils import to_timezone
from openedx.core.djangoapps.ga_task.models import Task
from util.json_request import JsonResponse, JsonResponseBadRequest

log = logging.getLogger(__name__)


def _get_p_condition_list(contract):
    # Acquire current parent condition
    search_condition_list = ParentCondition.objects.filter(contract=contract)
    show_list = [{
        'id': condition.id,
        'parent_condition_name': condition.parent_condition_name,
    } for condition in search_condition_list]

    return show_list


def _get_c_condition_list(condition_id):
    # Acquire current child condition
    return [{
            'id': condition.id,
            'contract_id': condition.contract.id,
            'parent_condition_id': condition.parent_condition_id,
            'parent_condition_name': condition.parent_condition_name,
            'comparison_target': condition.comparison_target,
            'comparison_type': condition.comparison_type,
            'comparison_string': condition.comparison_string
    } for condition in ChildCondition.objects.filter(parent_condition=condition_id)]


def _delete_c_condition(parent_condition_id):
    ChildCondition.objects.filter(parent_condition_id=parent_condition_id).delete()


def _create_c_condition(param_conditions, condition_id, condition_name, contract_id):
    for param_condition in param_conditions:
        ChildCondition.objects.create(
            contract=contract_id,
            parent_condition_id=condition_id,
            parent_condition_name=condition_name,
            comparison_target=param_condition['target'],
            comparison_type=int(param_condition['type']),
            comparison_string=param_condition['string']
        ).save()


def _update_p_condition(condition_id, condition_name, setting_type, user_id):
    ParentCondition.objects.filter(id=condition_id).update(
        setting_type=setting_type,
        parent_condition_name=condition_name,
        modified=datetime.now(),
        modified_by_id=user_id
    )


def _get_or_create_contract_option(user, contract):
    options = ContractOption.objects.filter(contract=contract)
    if len(options) == 0:
        return ContractOption.objects.create(contract=contract, modified_by=user)
    else:
        return options[0]


def _error_response(message):
    return JsonResponseBadRequest({
        'error': message,
    })


@require_GET
@login_required
@check_course_selection
@check_organization_group
def index(request):
    # Initial display
    user = request.user
    contract = request.current_contract
    search_condition_list = ParentCondition.objects.filter(contract=contract)

    # If there is no parent condition, make first condition
    if not search_condition_list:
        # Add condition
        ParentCondition.objects.create(
            contract=contract, parent_condition_name=_("Unknown condition"),
            setting_type=1, created=datetime.now(), created_by=user, modified=None
        ).save()

    # Make other contract list
    search_other_condition_list = Contract.objects.filter(
        contractor_organization_id=request.current_organization.id).exclude(id=request.current_contract.id)

    return render_to_response("gx_save_register_condition/index.html", {
        "show_p_condition_list": json.dumps(_get_p_condition_list(contract), cls=EscapedEdxJSONEncoder),
        "search_other_condition_list": search_other_condition_list,
        "auto_register_students_flag": contract.can_auto_register_students,
        "auto_register_reservation_date": contract.auto_register_reservation_date if contract.auto_register_reservation_date else ''
    })


@require_GET
@login_required
@check_course_selection
@check_organization_group
def detail(request, condition_id):
    if not ParentCondition.objects.filter(id=condition_id).exists():
        return render_to_response("static_templates/404.html")

    org = request.current_organization

    # Advanced
    additional_info_list = [info.display_name for info in AdditionalInfo.objects.filter(
        contract=request.current_contract).order_by('id')]

    # Make org_selection_list
    org_selection_list = []
    for i in range(1, 11):
        tmp_org_list = Member.find_active_by_org(
            org=org).values_list('org'+str(i), flat=True).order_by('org'+str(i)).distinct()
        org_selection_list.append(sorted(filter(lambda x: x != '' and x is not None, tmp_org_list)))

    # Make item_selection_list
    item_selection_list = []
    for i in range(1, 11):
        tmp_item_list = Member.find_active_by_org(
            org=org).values_list('item' + str(i), flat=True).order_by('item' + str(i)).distinct()
        item_selection_list.append(sorted(filter(lambda x: x != '' and x is not None, tmp_item_list)))

    # Make comparison_type_name_list
    comparison_type_name_list = OrderedDict()
    for comparison_type in ChildCondition.COMPARISON_TYPES:
        comparison_type_name_list[comparison_type[0]] = comparison_type[1]

    return render_to_response("gx_save_register_condition/detail.html", {
        "condition_id": int(condition_id),
        "parent_condition_name": ParentCondition.objects.get(id=condition_id).parent_condition_name,
        "setting_type": ParentCondition.objects.get(id=condition_id).setting_type,
        "group_list": Group.objects.filter(org=request.current_organization).order_by('id'),
        "org_selection_list": org_selection_list,
        "item_selection_list": item_selection_list,
        "target_list": ChildCondition.COMPARISON_TARGET,
        "comparison_type_list": comparison_type_name_list,
        'additional_info_list': additional_info_list,
        'default_list': json.dumps(_get_c_condition_list(condition_id), cls=EscapedEdxJSONEncoder),
    })


@require_POST
@login_required
@check_course_selection
@check_organization_group
def search_target_ajax(request):
    # Unauthorized access denial
    if 'contract_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    if not ChildCondition.objects.filter(contract_id=request.POST.get('contract_id')):
        return _error_response(
            _("Condition does not exist. Please set at least one condition."))

    org = request.current_organization
    contract = request.current_contract

    searched_members = get_members_by_all_parents_conditions(org=org, contract=contract)

    return JsonResponse({
        'info': _('Success'),
        'show_list': json.dumps([{
            'recid': i,
            'full_name': member.user.profile.name if hasattr(member.user, 'profile') else '',
            'user_name': member.user.username,
            'user_email': member.user.email,
            'login_code': member.user.bizuser.login_code if hasattr(member.user, 'bizuser') else ''
        } for i, member in enumerate(searched_members, start=1)], cls=EscapedEdxJSONEncoder),
    })


@require_POST
@login_required
@check_course_selection
@check_organization_group
def add_condition_ajax(request):
    if 'contract_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    user = request.user
    contract = request.current_contract

    # Add condition
    add_obj = ParentCondition.objects.create(
        contract=contract, parent_condition_name=_("Unknown condition"),
        setting_type=1, created_by=user, modified=None
    )
    add_obj.save()

    return JsonResponse({
        'info': _('Success'),
        'condition_id': add_obj.pk
    })


@require_POST
@login_required
@check_course_selection
@check_organization_group
def delete_condition_ajax(request):
    if 'contract_id' not in request.POST or 'condition_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    contract = request.current_contract
    select_id = int(request.POST.get('condition_id'))

    # ChildCondition Delete
    _delete_c_condition(select_id)

    # ParentCondition Delete
    ParentCondition.objects.get(pk=select_id).delete()

    return JsonResponse({
        'info': _('Success'),
        'conditions': _get_p_condition_list(contract)
    })


@require_POST
@login_required
@check_course_selection
@check_organization_group
def copy_condition_ajax(request):
    if 'contract_id' not in request.POST or 'copy_contract_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    contract = request.current_contract
    copy_contract = int(request.POST.get('copy_contract_id'))
    user_id = request.user.id

    # Condition delete
    ChildCondition.objects.filter(contract=contract).delete()
    ParentCondition.objects.filter(contract=contract).delete()

    # Condition insert
    for p_condition in ParentCondition.objects.filter(contract=copy_contract):
        p_id = p_condition.pk
        p_condition.pk = None
        p_condition.contract = contract
        p_condition.created = datetime.now()
        p_condition.created_by_id = user_id
        p_condition.modified = None
        p_condition.modified_by_id = None
        p_condition.save()

        for c_condition in ChildCondition.objects.filter(parent_condition=p_id):
            c_condition.pk = None
            c_condition.contract = contract
            c_condition.parent_condition_id = p_condition.pk
            c_condition.save()

    # Update Condition (having additional item in child condition)
    no_copy_parent_name_list = []

    for p_condition in ParentCondition.objects.filter(contract=contract):
        p_id = p_condition.pk
        p_name = p_condition.parent_condition_name
        delete_flag = False

        for c_condition in ChildCondition.objects.filter(parent_condition=p_id):
            is_additional = True
            for element in ChildCondition.COMPARISON_TARGET:
                if c_condition.comparison_target == element[0]:
                    is_additional = False

            if is_additional:
                delete_flag = True

        if delete_flag:
            no_copy_parent_name_list.append(p_name)
            p_condition.parent_condition_name = _('Unknown condition')
            p_condition.setting_type = 1
            p_condition.save()
            ChildCondition.objects.filter(parent_condition=p_id).delete()

    return JsonResponse({
        'info': _('Success'),
        'conditions': _get_p_condition_list(contract),
        'no_copy_parents': no_copy_parent_name_list
    })


@require_POST
@login_required
@check_course_selection
@check_organization_group
def detail_simple_save_condition_ajax(request):
    try:
        with transaction.atomic():
            # Type set
            setting_type = ParentCondition.SETTING_TYPE_SIMPLE

            param_conditions = json.loads(request.POST.get('condition_data'))
            condition_id = request.POST.get('parent_condition_id')
            condition_name = request.POST.get('condition_name')
            contract_id = request.current_contract
            user_id = request.user.id

            # All delete child condition
            _delete_c_condition(condition_id)

            # Create child condition
            _create_c_condition(param_conditions, condition_id, condition_name, contract_id)

            # Update parent condition
            _update_p_condition(condition_id, condition_name, setting_type, user_id)

    except Exception as e:
        log.error(e)

    return JsonResponse({
        'info': _('Success'),
    })


@require_POST
@login_required
@check_course_selection
@check_organization_group
def detail_search_target_ajax(request):
    if any(i not in request.POST for i in ['org_id', 'contract_id', 'condition_data']):
        return _error_response(_("Unauthorized access."))

    org = request.current_organization
    contract = request.current_contract

    param_conditions = json.loads(request.POST.get('condition_data'))
    if len(param_conditions) is 0:
        return _error_response(_("Condition does not exist. Please set at least one condition."))

    searched_members = get_members_by_child_conditions(org, contract, [
        ChildCondition(
            comparison_target=param_condition['target'],
            comparison_type=int(param_condition['type']),
            comparison_string=param_condition['string']
        ) for param_condition in param_conditions
    ])

    return JsonResponse({
        'info': _('Success'),
        'show_list': json.dumps([{
            'recid': i,
            'full_name': member.user.profile.name if hasattr(member.user, 'profile') else '',
            'user_name': member.user.username,
            'user_email': member.user.email,
            'login_code': member.user.bizuser.login_code if hasattr(member.user, 'bizuser') else ''
        } for i, member in enumerate(searched_members, start=1)], cls=EscapedEdxJSONEncoder),
    })


@require_POST
@login_required
@check_course_selection
@check_organization_group
def detail_advanced_save_condition_ajax(request):
    try:
        with transaction.atomic():
            # Type set
            setting_type = ParentCondition.SETTING_TYPE_ADVANCED

            param_conditions = json.loads(request.POST.get('condition_data'))
            condition_id = request.POST.get('parent_condition_id')
            condition_name = request.POST.get('condition_name')
            contract_id = request.current_contract
            user_id = request.user.id

            # All delete child condition
            _delete_c_condition(condition_id)

            # Create child condition
            _create_c_condition(param_conditions, condition_id, condition_name, contract_id)

            # Update parent condition
            _update_p_condition(condition_id, condition_name, setting_type, user_id)

    except Exception as e:
        log.error(e)

    return JsonResponse({
        'info': _('Success'),
    })


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
@check_organization_group
def reflect_condition_ajax(request):
    if any(i not in request.POST for i in ['org_id', 'contract_id', 'send_mail_flg']):
        return _error_response(_("Unauthorized access."))

    org = request.current_organization
    contract = request.current_contract
    send_mail_flg = request.POST.get('send_mail_flg')

    if not ChildCondition.objects.filter(contract_id=request.POST.get('contract_id')):
        return _error_response(
            _("Condition does not exist. Please set at least one condition."))

    if len(get_members_by_all_parents_conditions(org=org, contract=contract)) >= IMMEDIATE_REFLECT_MAX_SIZE:
        return _error_response(
            _("Can't use immediate reflection, because Target is over 10000.<br/>Please use reservation reflection."))

    history = ReflectConditionTaskHistory.objects.create(
        organization=org,
        contract=contract,
        requester=request.user
    )

    task_input = {
        'organization_id': org.id,
        'contract_id': contract.id,
        'send_mail_flg': send_mail_flg,
        'history_id': history.id,
    }

    return submit_org_task(request, org, task_input, REFLECT_CONDITIONS_IMMEDIATE, reflect_conditions_immediate,
                           ReflectConditionTaskHistory, history)


@require_POST
@login_required
@check_course_selection
def task_history_ajax(request):
    """
    Get task history.
    :param request:
    :return:
    """
    org = request.current_organization
    contract = request.current_contract

    def _task_result(task_output_str):
        task_output = json.loads(task_output_str)
        _msg = _('Register: {register}, Unregister: {unregister}, Masked: {masked}, Failed: {failed}')
        return _msg.format(
            register=task_output.get(TASK_PROGRESS_META_KEY_REGISTER, 0),
            unregister=task_output.get(TASK_PROGRESS_META_KEY_UNREGISTER, 0),
            masked=task_output.get(TASK_PROGRESS_META_KEY_MASK, 0),
            failed=task_output.get('failed', 0)
        )

    if ReflectConditionTaskHistory.objects.filter(organization=org, contract=contract):
        results = []
        for i, history in enumerate(ReflectConditionTaskHistory.objects.filter(
                organization=org, contract=contract).order_by('id').reverse(), start=1):
            try:
                task = Task.objects.get(task_id=history.task_id)
            except Task.DoesNotExist:
                log.warning("Can not find Task by reflect condition task history")
                continue

            if task.task_state not in READY_STATES:
                result_message = _("Task is being executed. Please wait a moment.")
                messages = []
            else:
                result_message = _task_result(task.task_output)
                messages = [{
                    'recid': j,
                    'message': message if message else '',
                } for j, message in enumerate(history.messages.split(',') if history.messages else [], start=1)]

            task_type = task.task_type
            if task.task_type in TASKS:
                task_type = TASKS[task.task_type]

            results.append({
                'recid': i,
                'task_type': task_type,
                'result_message': result_message,
                'messages': messages,
                'created': to_timezone(history.created).strftime('%Y/%m/%d %H:%M:%S') if history.created else '',
                'updated': to_timezone(history.updated).strftime('%Y/%m/%d %H:%M:%S') if history.updated else '',
                'requester': history.requester.username if history.requester else 'SYSTEM',
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
def update_auto_register_students_flg(request):
    if 'contract_id' not in request.POST or 'auto_register_students_flag' not in request.POST:
        return _error_response(_("Unauthorized access."))

    param_flg = request.POST.get('auto_register_students_flag')
    option = _get_or_create_contract_option(request.user, request.current_contract)

    if option.auto_register_reservation_date:
        return _error_response(
            _("You can't switch if the reservation reflection date is set. Please cancel reservation."))

    option.auto_register_students_flg = True if int(param_flg) == 1 else False
    option.modified_by = request.user
    option.save()

    return JsonResponse({
        'info': _('Success'),
    })


@require_POST
@login_required
@check_course_selection
def reservation_date_ajax(request):
    if 'contract_id' not in request.POST or 'reservation_date' not in request.POST:
        return _error_response(_("Unauthorized access."))

    param_reservation_date_str = request.POST.get('reservation_date')
    param_reservation_date = datetime.strptime(param_reservation_date_str, '%Y/%m/%d')

    # Check date
    if not ChildCondition.objects.filter(contract_id=request.POST.get('contract_id')):
        return _error_response(
            _("Condition does not exist. Please set at least one condition."))

    now = datetime.now()
    if param_reservation_date.strftime('%Y%m%d') < now.strftime('%Y%m%d'):
        return _error_response(_("The past date is entered. Please enter a future date."))

    if datetime(now.year, now.month, now.day, 18, 0, 0) <= now:
        if now <= datetime(now.year, now.month, now.day, 9, 0, 0) + timedelta(days=1):
            return _error_response(_("Today 's reception is over. Please enter the date of the future from tomorrow."))

    # Update
    option = _get_or_create_contract_option(request.user, request.current_contract)
    option.auto_register_reservation_date = param_reservation_date
    option.modified_by = request.user
    option.save()

    return JsonResponse({
        'info': _('Success'),
        'reservation_date': option.auto_register_reservation_date.strftime('%Y/%m/%d')
    })


@require_POST
@login_required
@check_course_selection
def cancel_reservation_date_ajax(request):
    if 'contract_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    option = _get_or_create_contract_option(request.user, request.current_contract)
    option.auto_register_reservation_date = None
    option.modified_by = request.user
    option.save()

    return JsonResponse({
        'info': _('Success'),
    })


"""
Views for contract_operation feature
"""
import json
import logging
import math
from collections import OrderedDict
from datetime import datetime
from functools import wraps

from celery.states import READY_STATES
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import Http404
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore, ScoreStore
from biz.djangoapps.ga_achievement.management.commands.update_biz_score_status import get_grouped_target_sections
from biz.djangoapps.ga_achievement.models import PlaybackBatchStatus, ScoreBatchStatus
from biz.djangoapps.ga_contract.models import AdditionalInfo, Contract, ContractDetail
from biz.djangoapps.ga_contract_operation.models import (
    ContractMail, ContractReminderMail,
    ContractTaskHistory, ContractTaskTarget, StudentRegisterTaskTarget,
    StudentUnregisterTaskTarget, AdditionalInfoUpdateTaskTarget, StudentMemberRegisterTaskTarget
)
from biz.djangoapps.ga_contract_operation.tasks import (
    personalinfo_mask, student_register, student_unregister, additional_info_update, student_member_register,
    TASKS, STUDENT_REGISTER, STUDENT_UNREGISTER, PERSONALINFO_MASK, ADDITIONALINFO_UPDATE, STUDENT_MEMBER_REGISTER
)
from biz.djangoapps.ga_contract_operation.utils import get_additional_info_by_contract
from biz.djangoapps.ga_invitation.models import (
    AdditionalInfoSetting, ContractRegister,
    STATUS as CONTRACT_REGISTER_STATUS, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE
)
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.util.access_utils import has_staff_access
from biz.djangoapps.util.decorators import check_course_selection, check_organization_group
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder
from biz.djangoapps.util.task_utils import submit_task, validate_task, get_task_key
from biz.djangoapps.util.unicodetsv_utils import create_tsv_response, create_csv_response, get_sjis_csv

from edxmako.shortcuts import render_to_response
from openedx.core.djangoapps.ga_self_paced import api as self_paced_api
from openedx.core.djangoapps.ga_task.api import AlreadyRunningError
from openedx.core.djangoapps.ga_task.task import STATES as TASK_STATES
from openedx.core.lib.ga_datetime_utils import to_timezone
from openedx.core.lib.ga_mail_utils import send_mail
from student.models import CourseEnrollment, UserStanding, UserProfile
from util.json_request import JsonResponse, JsonResponseBadRequest
from xmodule.modulestore.django import modulestore


log = logging.getLogger(__name__)

CONTRACT_REGISTER_MAX_DISPLAY_NUM = 1000
BIZ_MAX_CHAR_LENGTH_REGISTER_LINE = 7000
BIZ_MAX_REGISTER_NUMBER = 9999


def _error_response(message):
    return JsonResponseBadRequest({
        'error': message,
    })


def check_contract_register_selection(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if 'target_list' not in request.POST or 'contract_id' not in request.POST:
            return _error_response(_("Unauthorized access."))
        if str(request.current_contract.id) != request.POST['contract_id']:
            return _error_response(_("Current contract is changed. Please reload this page."))

        target_list = request.POST.getlist('target_list')
        if not target_list:
            return _error_response(_("Please select a target."))
        registers = ContractRegister.find_by_ids(target_list)
        for register in registers:
            if register.contract != request.current_contract:
                log.warning(
                    'Not found register in contract_id({}) contract_register_id({}), user_id({})'.format(
                        request.current_contract.id,
                        register.id,
                        register.user_id
                    )
                )
                return _error_response(_('Unauthorized access.'))
        kwargs['registers'] = registers
        return func(request, *args, **kwargs)

    return wrapper


@require_GET
@login_required
@check_course_selection
@check_organization_group
def students(request):
    total_count, show_list, status, additional_columns = _students_initial_search(request)

    member_org_item_list = OrderedDict()
    for i in range(1, 11):
        member_org_item_list['org' + str(i)] = _("Organization") + str(i)
    for i in range(1, 11):
        member_org_item_list['item' + str(i)] = _("Item") + str(i)

    return render_to_response(
        'ga_contract_operation/students.html',
        {
            'total_count': total_count,
            'show_list': json.dumps(show_list, cls=EscapedEdxJSONEncoder),
            'additional_columns': json.dumps(additional_columns, cls=EscapedEdxJSONEncoder),
            'max_show_num_on_page': CONTRACT_REGISTER_MAX_DISPLAY_NUM,
            'member_org_item_list': member_org_item_list,
        }
    )


@require_POST
@login_required
@check_course_selection
@check_organization_group
def students_search_students_ajax(request):
    if 'contract_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    offset = request.POST['offset']
    limit = request.POST['limit']

    # query = _students_create_search_query(request, org, contract, manager, visible_group_ids)

    total_count, show_list, __, __ = _contract_register_list_on_page(request, int(offset), int(limit))

    if total_count == 0:
        return JsonResponse({
            'info': _('Success'),
            'total_count': 0,
            'show_list': json.dumps([], cls=EscapedEdxJSONEncoder),
        })
    else:
        return JsonResponse({
            'info': _('Success'),
            'total_count': total_count,
            'show_list': json.dumps(show_list, cls=EscapedEdxJSONEncoder),
        })


def _students_initial_search(request):
    return _contract_register_list_on_page(request)


def _contract_register_list_on_page(request, offset=0, limit=CONTRACT_REGISTER_MAX_DISPLAY_NUM):
    option_sql = [
        # set default arguments for sql
        request.current_organization.id,
        request.current_organization.id,
        request.current_contract.id
    ]
    where_sql = ""

    radio_operator_exclude = 'exclude'
    radio_operator_contains = 'contains'
    radio_operator_only = 'only'
    radio_operator = (radio_operator_exclude, radio_operator_contains, radio_operator_only)

    # Organization group
    if not request.current_manager.is_director() and request.current_manager.is_manager() and Group.objects.filter(org=request.current_organization).exists():
        if request.current_organization_visible_group_ids:
            where_sql += "AND group_id IN ("
            group_stock = []
            for group_id in map(str, request.current_organization_visible_group_ids):
                group_stock.append("%s")
                option_sql.append(group_id)
            where_sql += ','.join(group_stock)
            where_sql += ") "
        else:
            where_sql += "AND 0 "

    # Unregister: is_unregister is empty when students page initial display.
    is_unregister = request.POST.get('is_unregister')
    if is_unregister not in radio_operator or is_unregister == radio_operator_exclude:
        where_sql += "AND (status = %s OR status = %s) "
        option_sql.append(INPUT_INVITATION_CODE)
        option_sql.append(REGISTER_INVITATION_CODE)
    elif is_unregister == radio_operator_only:
        where_sql += "AND status = %s "
        option_sql.append(UNREGISTER_INVITATION_CODE)

    # Free word
    free_word = request.POST.get('free_word')
    if free_word and free_word.strip():
        where_sql += 'AND (username LIKE %s OR email LIKE %s OR name LIKE %s OR group_name LIKE %s OR org1 LIKE %s ' \
                     'OR org2 LIKE %s OR org3 LIKE %s OR org4 LIKE %s OR org5 LIKE %s OR org6 LIKE %s OR org7 LIKE %s ' \
                     'OR org8 LIKE %s OR org9 LIKE %s OR org10 LIKE %s OR item1 LIKE %s OR item2 LIKE %s ' \
                     'OR item3 LIKE %s OR item4 LIKE %s OR item5 LIKE %s OR item6 LIKE %s OR item7 LIKE %s ' \
                     'OR item8 LIKE %s OR item9 LIKE %s OR item10 LIKE %s OR login_code LIKE %s '
        for p in range(0, 25):
            option_sql.append('%' + free_word + '%')

        user_ids = AdditionalInfoSetting.objects.filter(contract=request.current_contract,
                                                        value__contains=free_word).values_list('user')
        if user_ids:
            where_sql += "OR IC.user_id IN ("
            user_stock = []
            for user_id in user_ids:
                user_stock.append("%s")
                option_sql.append(user_id[0])
            where_sql += ','.join(user_stock)
            where_sql += ") "
        where_sql += ") "

    # Detail search
    detail_search_counter = 1
    while 'org_item_field_select_' + str(detail_search_counter) in request.POST:
        count = str(detail_search_counter)
        detail_search_counter += 1
        key = request.POST.get('org_item_field_select_' + count)
        value = request.POST.get('org_item_field_text_' + count)
        if key and key.strip() and value and value.strip():
            if key in ['org' + str(i) for i in range(1, 11)] + ['item' + str(i) for i in range(1, 11)]:
                where_sql += "AND " + key + " LIKE %s "
                option_sql.append("%" + value + "%")

    # Target user of delete member
    member_is_delete = request.POST.get('member_is_delete')
    if member_is_delete == radio_operator_contains:
        where_sql += "AND ((MG.is_active=1 AND MG.is_delete=0) OR (MG.is_active=0 AND MG.is_delete=1) OR MG.is_active IS NULL) "
    elif member_is_delete == radio_operator_only:
        where_sql += "AND MG.is_delete=1 "
    else:
        # member_is_delete is empty when students page initial display.
        where_sql += "AND (MG.is_active=1 OR MG.is_active IS NULL) "

    # Mask: is_masked is empty when students page initial display.
    is_masked = request.POST.get('is_masked')
    if is_masked not in radio_operator or is_masked == radio_operator_exclude:
        where_sql += "AND email LIKE %s "
        option_sql.append('%@%')
    elif is_masked == radio_operator_only:
        where_sql += "AND NOT email LIKE %s "
        option_sql.append('%@%')

    sql = '''SELECT DISTINCT IC.id, IC.status, IC.user_id, user.username, user.email, profile.name as full_name, 
bizuser.login_code, MG.group_name, MG.code, MG.is_active, MG.is_delete, 
MG.org1, MG.org2, MG.org3, MG.org4, MG.org5, MG.org6, MG.org7, MG.org8, MG.org9, MG.org10, 
MG.item1, MG.item2, MG.item3, MG.item4, MG.item5, MG.item6, MG.item7, MG.item8, MG.item9, MG.item10, MG.org_id
FROM ga_invitation_contractregister as IC
INNER JOIN auth_user as user ON IC.user_id = user.id 
LEFT OUTER JOIN auth_userprofile as profile ON user.id = profile.user_id
LEFT OUTER JOIN ga_login_bizuser as bizuser ON user.id = bizuser.user_id 
LEFT OUTER JOIN (
  SELECT M.id, M.code, M.is_active, M.is_delete, M.group_id, M.org_id, M.user_id, G.group_code, G.group_name, 
         M.org1, M.org2, M.org3, M.org4, M.org5, M.org6, M.org7, M.org8, M.org9, M.org10, 
         M.item1, M.item2, M.item3, M.item4, M.item5, M.item6, M.item7, M.item8, M.item9, M.item10
  FROM gx_member_member as M LEFT OUTER JOIN gx_org_group_group as G 
  ON M.group_id = G.id  AND M.org_id = %s) MG ON IC.user_id = MG.user_id AND MG.org_id = %s 
WHERE IC.contract_id = %s ''' + where_sql + '''
ORDER BY IC.id'''
    count_sql = '''SELECT 1 as id, COUNT(*) as cnt FROM (''' + sql + ''') CNT'''

    status = {k: unicode(v) for k, v in dict(CONTRACT_REGISTER_STATUS).items()}
    user_additional_settings, display_names, __, additional_columns = get_additional_info_by_contract(contract=request.current_contract)

    total_count = ContractRegister.objects.raw(count_sql, option_sql)[0].cnt

    show_list = []
    for i, register in enumerate(ContractRegister.objects.raw(sql, option_sql)[offset:limit], start=1):

        row = {
            'recid': i,
            'contract_register_id': register.id,
            'contract_register_status': status[register.status],
            'user_name': register.username,
            'user_email': register.email,
            'full_name': register.full_name or '',
            'login_code': register.login_code or '',
            'is_delete': register.is_delete or '',
            'code': register.code or '',
            'group_name': register.group_name or '',
        }
        if not register.org_id or register.org_id == request.current_organization.id:
            for p in range(1, 11):
                row['org' + str(p)] = getattr(register, 'org' + str(p), '') or ''
                row['item' + str(p)] = getattr(register, 'item' + str(p), '') or ''

        # Set additional settings value of user.
        if register.user_id in user_additional_settings:
            row.update(user_additional_settings[register.user_id])

        show_list.append(row)

    return total_count, show_list, status, additional_columns


@require_POST
@login_required
@check_course_selection
@check_organization_group
def students_students_download(request):
    total_count, show_list, __, additional_columns = _contract_register_list_on_page(request, 0, None)

    headers = [_("Student Status"), _("Full Name"), _("Organization Groups"), _("Member Code"), _("Email Address"),
               _("Login Code"), _("Username"), _("Target user of delete member master")]
    for i in range(1, 11):
        headers.append(_("Organization") + str(i))
    for i in range(1, 11):
        headers.append(_("Item") + str(i))
    for additional_column in additional_columns:
        headers.append(additional_column['caption'])

    rows = []
    for show_row in show_list:
        row = [show_row.get('contract_register_status', ''), show_row.get('full_name', ''),
               show_row.get('group_name', ''), show_row.get('code', ''), show_row.get('user_email', ''),
               show_row.get('login_code', ''), show_row.get('user_name', ''), show_row.get('is_delete', ''),
               show_row.get('org1', ''), show_row.get('org2', ''), show_row.get('org3', ''), show_row.get('org4', ''),
               show_row.get('org5', ''), show_row.get('org6', ''), show_row.get('org7', ''), show_row.get('org8', ''),
               show_row.get('org9', ''), show_row.get('org10', ''), show_row.get('item1', ''),
               show_row.get('item2', ''), show_row.get('item3', ''), show_row.get('item4', ''),
               show_row.get('item5', ''), show_row.get('item6', ''), show_row.get('item7', ''),
               show_row.get('item8', ''), show_row.get('item9', ''), show_row.get('item10', '')]
        for additional_column in additional_columns:
            row.append(show_row.get(additional_column['caption'], ''))
        rows.append(row)

    org_name = request.current_organization.org_name
    current_datetime = datetime.now()
    date_str = current_datetime.strftime("%Y-%m-%d-%H%M")

    return create_tsv_response(org_name + '_students_list_' + date_str + '.csv', headers, rows)


@require_POST
@login_required
@check_course_selection
@check_organization_group
@check_contract_register_selection
def unregister_students_ajax(request, registers):
    manager = request.current_manager
    valid_register_list = []
    warning_register_list = []

    # Check the task running within the same contract.
    validate_task_message = validate_task(request.current_contract)
    if validate_task_message:
        return _error_response(validate_task_message)

    # validate
    for register in registers:
        # Validate status
        if register.status == UNREGISTER_INVITATION_CODE:
            warning_register_list.append(register)
            continue
        valid_register_list.append(register)

    # db access
    try:
        course_keys = [detail.course_id for detail in request.current_contract.details.all()]
        with transaction.atomic():
            for register in valid_register_list:
                # ContractRegister and ContractRegisterHistory for end-of-month
                register.status = UNREGISTER_INVITATION_CODE
                register.save()
                # CourseEnrollment only spoc TODO should do by celery
                if request.current_contract.is_spoc_available:
                    for course_key in course_keys:
                        if CourseEnrollment.is_enrolled(register.user, course_key) and not has_staff_access(
                                register.user, course_key):
                            CourseEnrollment.unenroll(register.user, course_key)
    except Exception:
        unregister_list = [register.id for register in registers]
        log.exception('Can not unregister. contract_id({}), unregister_list({})'.format(request.current_contract.id,
                                                                                        unregister_list))
        return _error_response(_('Failed to batch unregister. Please operation again after a time delay.'))

    total_count, show_list, __, __ = _students_initial_search(request)

    warning = _('Already unregisterd {user_count} users.').format(
        user_count=len(warning_register_list)) if warning_register_list else ''

    return JsonResponse({
        'info': _('Succeed to unregister {user_count} users.').format(user_count=len(valid_register_list)) + warning,
        'show_list': show_list,
    })


@require_GET
@login_required
@check_course_selection
@check_organization_group
def register_students(request):
    org = request.current_organization
    manager = request.current_manager

    org_items = {
        'org1': Member.find_active_by_org(org=org).exclude(org1='').values('org1').order_by('org1').distinct(),
        'org2': Member.find_active_by_org(org=org).exclude(org2='').values('org2').order_by('org2').distinct(),
        'org3': Member.find_active_by_org(org=org).exclude(org3='').values('org3').order_by('org3').distinct(),
        'org4': Member.find_active_by_org(org=org).exclude(org4='').values('org4').order_by('org4').distinct(),
        'org5': Member.find_active_by_org(org=org).exclude(org5='').values('org5').order_by('org5').distinct(),
        'org6': Member.find_active_by_org(org=org).exclude(org6='').values('org6').order_by('org6').distinct(),
        'org7': Member.find_active_by_org(org=org).exclude(org7='').values('org7').order_by('org7').distinct(),
        'org8': Member.find_active_by_org(org=org).exclude(org8='').values('org8').order_by('org8').distinct(),
        'org9': Member.find_active_by_org(org=org).exclude(org9='').values('org9').order_by('org9').distinct(),
        'org10': Member.find_active_by_org(org=org).exclude(org10='').values('org10').order_by('org10').distinct(),
        'item1': Member.find_active_by_org(org=org).exclude(item1='').values('item1').order_by('item1').distinct(),
        'item2': Member.find_active_by_org(org=org).exclude(item2='').values('item2').order_by('item2').distinct(),
        'item3': Member.find_active_by_org(org=org).exclude(item3='').values('item3').order_by('item3').distinct(),
        'item4': Member.find_active_by_org(org=org).exclude(item4='').values('item4').order_by('item4').distinct(),
        'item5': Member.find_active_by_org(org=org).exclude(item5='').values('item5').order_by('item5').distinct(),
        'item6': Member.find_active_by_org(org=org).exclude(item6='').values('item6').order_by('item6').distinct(),
        'item7': Member.find_active_by_org(org=org).exclude(item7='').values('item7').order_by('item7').distinct(),
        'item8': Member.find_active_by_org(org=org).exclude(item8='').values('item8').order_by('item8').distinct(),
        'item9': Member.find_active_by_org(org=org).exclude(item9='').values('item9').order_by('item9').distinct(),
        'item10': Member.find_active_by_org(org=org).exclude(item10='').values('item10').order_by('item10').distinct()
    }

    if not manager.is_director() and manager.is_manager() and Group.objects.filter(org=org).exists():
        group_list = [
            (grp.group_code, grp.id, grp.group_name) for grp in Group.objects.filter(
                org=org.id, id__in=request.current_organization_visible_group_ids).order_by('group_code')
        ]
    else:
        group_list = [
            (grp.group_code, grp.id, grp.group_name) for grp in Group.objects.filter(
                org=request.current_organization.id).order_by('group_code')
        ]

    listbox_contracts = Contract.find_all_by_user(request.user)

    return render_to_response(
        'ga_contract_operation/register_students.html',
        {
            'max_register_number': "{:,d}".format(int(settings.BIZ_MAX_REGISTER_NUMBER)),
            'additional_info_list': AdditionalInfo.objects.filter(contract=request.current_contract),
            'max_length_additional_info_display_name': AdditionalInfo._meta.get_field('display_name').max_length,
            'max_bulk_students_number': settings.BIZ_MAX_BULK_STUDENTS_NUMBER,
            'organization': request.current_organization,
            'org_items': org_items,
            'group_list': group_list,
            'listbox_contracts': listbox_contracts,
        }
    )


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
def register_students_ajax(request):
    """
    Create new accounts.
    Passing a list of students.
    Order in list should be the following email = 0; username = 1; name = 2.

    -If the email address already exists,
    do nothing (including no email gets sent out)

    -If the username already exists (but not the email), assume it is a different user and fail to create the new account.
     The failure will be messaged in a response in the browser.
    """
    log.info('register_students_start')
    if 'students_list' not in request.POST or 'contract_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    students = request.POST['students_list'].splitlines()
    if not students:
        log.info('Could not find student list.')
        return _error_response(_("Could not find student list."))

    if len(students) > settings.BIZ_MAX_REGISTER_NUMBER:
        log.info('max_register_number length over')
        return _error_response(_(
            "It has exceeded the number({max_register_number}) of cases that can be a time of registration."
        ).format(max_register_number=settings.BIZ_MAX_REGISTER_NUMBER))

    if any([len(s) > settings.BIZ_MAX_CHAR_LENGTH_REGISTER_LINE for s in students]):
        log.info('biz_max_char length over')
        return _error_response(_(
            "The number of lines per line has exceeded the {biz_max_char_length_register_line} characters."
        ).format(biz_max_char_length_register_line=settings.BIZ_MAX_CHAR_LENGTH_REGISTER_LINE))

    register_status = request.POST.get('register_status')
    if register_status and register_status != REGISTER_INVITATION_CODE:
        log.info('Invalid access.')
        return _error_response(_("Invalid access."))

    register_status = register_status or INPUT_INVITATION_CODE

    # To register status. Register or Input
    students = [u'{},{}'.format(register_status, s) for s in students]

    log.info('register_students_create')
    history = ContractTaskHistory.create(request.current_contract, request.user)
    log.info('register_students_bulk_create:task_id' + str(history.id))
    StudentRegisterTaskTarget.bulk_create(history, students)
    log.info('register_students_submit_task:task_id' + str(history.id))
    return _submit_task(request, STUDENT_REGISTER, student_register, history)


@require_GET
@login_required
@check_course_selection
def bulk_students(request):
    return render_to_response(
        'ga_contract_operation/bulk_students.html',
        {
            'max_bulk_students_number': settings.BIZ_MAX_BULK_STUDENTS_NUMBER,
        }
    )


def _submit_task(request, task_type, task_class, history, additional_info_list=None):
    try:
        task_input = {
            'contract_id': request.current_contract.id,
            'history_id': history.id,
        }
        if additional_info_list:
            task_input['additional_info_ids'] = [a.id for a in additional_info_list]

        # Check the task running within the same contract.
        validate_task_message = validate_task(request.current_contract)
        if validate_task_message:
            return _error_response(validate_task_message)
        validate_task_message = validate_task(request.current_organization)
        if validate_task_message:
            return _error_response(validate_task_message)

        # task prevents duplicate execution by contract_id
        task = submit_task(request, task_type, task_class, task_input, get_task_key(request.current_contract))
        history.link_to_task(task)
    except AlreadyRunningError:
        return _error_response(
            _("Processing of {task_type} is running.").format(task_type=TASKS[task_type]) +
            _("Execution status, please check from the task history.")
        )

    return JsonResponse({
        'info': _("Began the processing of {task_type}.").format(task_type=TASKS[task_type]) + _(
            "Execution status, please check from the task history."),
    })


@require_POST
@login_required
@check_course_selection
def task_history_ajax(request):
    """
    Endpoint to get the task history.
    """

    def _task_state(task):
        _state = task.task_state if task else ''
        if _state in READY_STATES:
            return _("Complete")
        elif _state in TASK_STATES:
            return TASK_STATES[_state]
        else:
            return _("Unknown")

    def _task_result(task):
        if task is None or not task.task_output:
            return ''
        task_output = json.loads(task.task_output)
        return _("Total: {total}, Success: {succeeded}, Skipped: {skipped}, Failed: {failed}").format(
            total=task_output.get('total', 0), succeeded=task_output.get('succeeded', 0),
            skipped=task_output.get('skipped', 0), failed=task_output.get('failed', 0)
        )

    def _task_message(task, history):
        _task_targets = None
        if task:
            if task.task_type == STUDENT_REGISTER:
                _task_targets = StudentRegisterTaskTarget.find_by_history_id_and_message(history.id)
            elif task.task_type == STUDENT_UNREGISTER:
                _task_targets = StudentUnregisterTaskTarget.find_by_history_id_and_message(history.id)
            elif task.task_type == PERSONALINFO_MASK:
                _task_targets = ContractTaskTarget.find_by_history_id_and_message(history.id)
            elif task.task_type == ADDITIONALINFO_UPDATE:
                _task_targets = AdditionalInfoUpdateTaskTarget.find_by_history_id_and_message(history.id)
            elif task.task_type == STUDENT_MEMBER_REGISTER:
                _task_targets = StudentMemberRegisterTaskTarget.find_by_history_id_and_message(history.id)
        return [
            {
                'recid': task_target.id,
                'message': task_target.message,
            }
            for task_target in _task_targets
        ] if _task_targets else []

    task_histories = [
        {
            'recid': i + 1,
            'task_type': TASKS[task.task_type] if task and task.task_type in TASKS else _('Unknown'),
            'task_state': _task_state(task),
            'task_result': _task_result(task),
            'requester': history.requester.username,
            'created': to_timezone(history.created).strftime('%Y/%m/%d %H:%M:%S'),
            'messages': _task_message(task, history),
        }
        for i, (history, task) in enumerate(ContractTaskHistory.find_by_contract_with_task(request.current_contract))
    ]
    # The structure of the response is in accordance with the specifications of the load function of w2ui.
    return JsonResponse({
        'status': 'success',
        'total': len(task_histories),
        'records': task_histories,
    })


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
@check_organization_group
@check_contract_register_selection
def submit_personalinfo_mask(request, registers):
    """
    Submit task of masking personal information.
    """

    history = ContractTaskHistory.create(request.current_contract, request.user)
    ContractTaskTarget.bulk_create(history, registers)

    return _submit_task(request, PERSONALINFO_MASK, personalinfo_mask, history)


@require_GET
@login_required
@check_course_selection
def register_mail(request):
    if not request.current_contract.can_customize_mail:
        raise Http404()

    if request.current_contract.has_auth:
        register_new_user_mail = ContractMail.get_register_new_user_logincode(request.current_contract)
        register_exists_mail = ContractMail.get_register_existing_user_logincode(request.current_contract)
    else:
        register_new_user_mail = ContractMail.get_register_new_user(request.current_contract)
        register_exists_mail = ContractMail.get_register_existing_user(request.current_contract)

    return render_to_response(
        'ga_contract_operation/mail.html',
        {
            'mail_info_list': [
                register_new_user_mail,
                register_exists_mail,
            ],
        }
    )


@require_POST
@login_required
@check_course_selection
def register_mail_ajax(request):
    if not request.current_contract.can_customize_mail or any(
            k not in request.POST for k in ['mail_type', 'mail_subject', 'mail_body', 'contract_id']):
        return _error_response(_("Unauthorized access."))

    mail_type = request.POST['mail_type']
    if not ContractMail.is_mail_type(mail_type):
        log.warning('Illegal mail-type: {}'.format(mail_type))
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    mail_subject = request.POST['mail_subject']
    if not mail_subject:
        return _error_response(_("Please enter the subject of an e-mail."))

    mail_subject_max_length = ContractMail._meta.get_field('mail_subject').max_length
    if len(mail_subject) > mail_subject_max_length:
        return _error_response(_("Subject within {0} characters.").format(mail_subject_max_length))

    mail_body = request.POST['mail_body']
    if not mail_body:
        return _error_response(_("Please enter the body of an e-mail."))

    try:
        contract_mail, __ = ContractMail.objects.get_or_create(contract=request.current_contract, mail_type=mail_type)
        contract_mail.mail_subject = mail_subject
        contract_mail.mail_body = mail_body
        contract_mail.save()
    except:
        log.exception('Failed to save the template e-mail.')
        return _error_response(_("Failed to save the template e-mail."))
    else:
        return JsonResponse({
            'info': _("Successfully to save the template e-mail."),
        })


@require_POST
@login_required
@check_course_selection
def send_mail_ajax(request):
    if not request.current_contract.can_customize_mail or any(
            k not in request.POST for k in ['mail_type', 'mail_subject', 'mail_body', 'contract_id']):
        return _error_response(_("Unauthorized access."))

    mail_type = request.POST['mail_type']
    if not ContractMail.is_mail_type(mail_type):
        log.warning('Illegal mail-type: {}'.format(mail_type))
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    contract_mail = ContractMail.get_or_default(request.current_contract, mail_type)
    if contract_mail.mail_subject != request.POST['mail_subject'] or contract_mail.mail_body != request.POST[
        'mail_body']:
        return _error_response(_("Please save the template e-mail before sending."))

    # Send mail
    try:
        send_mail(
            request.user,
            contract_mail.mail_subject,
            contract_mail.mail_body,
            ContractMail.register_replace_dict(
                request.user,
                request.current_contract,
                password='dummyPassword' if contract_mail.has_mail_param_password else None,
                login_code='dummyLoginCode' if request.current_contract.has_auth else None,
            )
        )
    except:
        log.exception('Failed to send the test e-mail.')
        return _error_response(_("Failed to send the test e-mail."))
    else:
        return JsonResponse({
            'info': _("Successfully to send the test e-mail."),
        })


@require_GET
@login_required
@check_course_selection
@check_organization_group
def reminder_mail(request):
    if not request.current_contract.can_send_submission_reminder:
        raise Http404()

    contract = request.current_contract
    course = request.current_course
    is_manager = not request.current_manager.is_director() and request.current_manager.is_manager()

    # Reminder mail
    if request.current_contract.can_send_submission_reminder:
        reminder_mail = ContractReminderMail.get_or_default(
            request.current_contract, ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER)

    # Search Reminder mail
    search_reminder_mail = {
        'student_status_list': [
            _(ScoreStore.FIELD_STUDENT_STATUS__ENROLLED),
            _(ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED),
            _(ScoreStore.FIELD_STUDENT_STATUS__DISABLED),
            _(ScoreStore.FIELD_STUDENT_STATUS__EXPIRED),
        ],
        'search_mail_params': [
            ContractReminderMail.MAIL_PARAM_USERNAME,
            ContractReminderMail.MAIL_PARAM_EMAIL_ADDRESS,
            ContractReminderMail.MAIL_PARAM_COURSE_NAME,
            ContractReminderMail.MAIL_PARAM_FULLNAME,
            ContractReminderMail.MAIL_PARAM_EXPIRE_DATE,
        ],
    }

    # Check score batch
    score_batch_status = ScoreBatchStatus.get_last_status(contract.id, course.id)
    if score_batch_status:
        score_store = ScoreStore(contract.id, unicode(course.id))
        hidden_columns = score_store.get_section_names()
        search_reminder_mail['score_section_names'] = [column[0] for column in hidden_columns]
        search_reminder_mail['hidden_score_columns'] = json.dumps(hidden_columns, cls=EscapedEdxJSONEncoder)
    else:
        search_reminder_mail['hidden_score_columns'] = {}
        search_reminder_mail['score_section_names'] = []

    # Check playback batch
    playback_batch_status = PlaybackBatchStatus.get_last_status(contract.id, course.id)
    if playback_batch_status:
        playback_store = PlaybackStore(contract.id, unicode(course.id))
        hidden_columns = playback_store.get_section_names()
        search_reminder_mail['playback_section_names'] = [column[0] for column in hidden_columns]
        search_reminder_mail['hidden_playback_columns'] = json.dumps(hidden_columns, cls=EscapedEdxJSONEncoder)
    else:
        search_reminder_mail['hidden_playback_columns'] = {}
        search_reminder_mail['playback_section_names'] = []

    # Pulldown of 'Search Detail(Other)'
    search_detail_other_list = OrderedDict()
    search_detail_other_list['login_code'] = _("Login Code")
    search_detail_other_list['full_name'] = _("Full Name")
    search_detail_other_list['username'] = _("Username")
    search_detail_other_list['email'] = _("Email Address")
    for i in range(1, 11):
        search_detail_other_list['org' + str(i)] = _("Organization") + str(i)
    for i in range(1, 11):
        search_detail_other_list['item' + str(i)] = _("Item") + str(i)

    search_reminder_mail['search_detail_other_list'] = search_detail_other_list

    return render_to_response(
        'ga_contract_operation/reminder_mail.html',
        {
            'is_manager': is_manager,
            'mail_info': reminder_mail,
            'search_mail_info': search_reminder_mail,
            'deadline': course.deadline_start,
            'reminder_mail_contract_id': reminder_mail.contract_id,
        }
    )


@require_POST
@login_required
@check_course_selection
def reminder_mail_save_ajax(request):
    if not request.current_contract.can_send_submission_reminder:
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST.get('contract_id'):
        return _error_response(_("Current contract is changed. Please reload this page."))

    # Input check
    mail_type = request.POST.get('mail_type')
    if not ContractReminderMail.is_mail_type(mail_type):
        log.warning('Illegal mail-type: {}'.format(mail_type))
        return _error_response(_("Unauthorized access."))

    reminder_email_days = request.POST.get('reminder_email_days')
    if not reminder_email_days:
        return _error_response(_("Please use the pull-down menu to choose the reminder e-mail days."))
    try:
        reminder_email_days = int(reminder_email_days)
    except ValueError:
        return _error_response(_("Please use the pull-down menu to choose the reminder e-mail days."))
    if reminder_email_days < ContractReminderMail.REMINDER_EMAIL_DAYS_MIN_VALUE or ContractReminderMail.REMINDER_EMAIL_DAYS_MAX_VALUE < reminder_email_days:
        return _error_response(_("Please use the pull-down menu to choose the reminder e-mail days."))

    mail_subject = request.POST.get('mail_subject')
    if not mail_subject:
        return _error_response(_("Please enter the subject of an e-mail."))
    mail_subject_max_length = ContractReminderMail._meta.get_field('mail_subject').max_length
    if len(mail_subject) > mail_subject_max_length:
        return _error_response(_("Subject within {0} characters.").format(mail_subject_max_length))

    mail_body = request.POST.get('mail_body')
    mail_body2 = request.POST.get('mail_body2')
    if not mail_body or not mail_body2:
        return _error_response(_("Please enter the body of an e-mail."))

    # Save template
    try:
        contract_mail, __ = ContractReminderMail.objects.get_or_create(
            contract=request.current_contract, mail_type=mail_type)
        contract_mail.reminder_email_days = reminder_email_days
        contract_mail.mail_subject = mail_subject
        contract_mail.mail_body = mail_body
        contract_mail.mail_body2 = mail_body2
        contract_mail.save()
    except:
        log.exception('Failed to save the template e-mail.')
        return _error_response(_("Failed to save the template e-mail."))
    else:
        return JsonResponse({
            'info': _("Successfully to save the template e-mail."),
        })

@require_POST
@login_required
@check_course_selection
def reminder_mail_delete_ajax(request):
    """
    This Ajax function uses the record registered in the ContractReminderMail table as a delete button.
    Deletes the record registered with the current contract.
    :param request:
    :return:
    """
    if not request.current_contract.can_send_submission_reminder:
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST.get('contract_id'):
        return _error_response(_("Current contract is changed. Please reload this page."))

    mail_type = request.POST.get('mail_type')
    if not ContractReminderMail.is_mail_type(mail_type):
        log.warning('Illegal mail-type: {}'.format(mail_type))
        return _error_response(_("Unauthorized access."))

    # Delete template
    try:
        if ContractReminderMail.objects.filter(
            contract=request.current_contract, mail_type=mail_type).first():
            ContractReminderMail.objects.filter(
            contract=request.current_contract, mail_type=mail_type).delete()
        else:
            return _error_response(_("Input Invitation"))
    except:
        log.exception('Failed to delete the template e-mail.contract: {}'.format(request.current_contract.id))
        return _error_response(_("Failed to deleted item."))
    else:
        log.info('Delete success contract_id: {}'.format(request.current_contract.id))
        return JsonResponse({
            'info': _("Reminder mail deleted."),
        })

@require_POST
@login_required
@check_course_selection
def reminder_mail_send_ajax(request):
    if not request.current_contract.can_send_submission_reminder:
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST.get('contract_id'):
        return _error_response(_("Current contract is changed. Please reload this page."))

    mail_type = request.POST.get('mail_type')
    if not ContractReminderMail.is_mail_type(mail_type):
        log.warning('Illegal mail-type: {}'.format(mail_type))
        return _error_response(_("Unauthorized access."))

    contract_mail = ContractReminderMail.get_or_default(request.current_contract, mail_type)
    if (str(contract_mail.reminder_email_days) != request.POST.get('reminder_email_days') or
            contract_mail.mail_subject != request.POST.get('mail_subject') or
            contract_mail.mail_body != request.POST.get('mail_body') or
            contract_mail.mail_body2 != request.POST.get('mail_body2')):
        return _error_response(_("Please save the template e-mail before sending."))

    if mail_type == ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER:
        # Get target courses to display on the e-mail body
        target_courses = []
        courses = [modulestore().get_course(d.course_id) for d in request.current_contract.details.all().order_by('id')]
        for course in courses:
            grouped_target_sections = get_grouped_target_sections(course)
            if grouped_target_sections.keys():
                target_courses.append(grouped_target_sections)

        # Send mail
        try:
            send_mail(
                request.user,
                contract_mail.mail_subject.encode('utf-8'),
                contract_mail.compose_mail_body(target_courses).encode('utf-8'),
                {'username': request.user.username,
                 'fullname': request.user.profile.name.encode('utf-8')},
            )
        except:
            log.exception('Failed to send the test e-mail.')
            return _error_response(_("Failed to send the test e-mail."))
        else:
            return JsonResponse({
                'info': _("Successfully to send the test e-mail."),
            })


@require_POST
@login_required
@check_course_selection
@check_organization_group
def reminder_search_ajax(request):
    org = request.current_organization
    contract = request.current_contract
    course = request.current_course
    manager = request.current_manager

    if 'contract_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    def _get_mongo_conditions(key):
        has_condition = False
        # Get total condition
        total_key = 'total_' + key
        total_no_val = request.POST[total_key + '_no'] if total_key + '_no' in request.POST else None
        total_from_val = request.POST[total_key + '_from']
        total_to_val = request.POST[total_key + '_to']
        total_condition = {
            'no': total_no_val,
            'from': total_from_val if len(total_from_val) else None,
            'to': total_to_val if len(total_to_val) else None,
        }

        if key is 'playback':
            if total_condition['from']:
                total_condition['from'] = (int(total_condition['from']) * 60) - 60
            if total_condition['to']:
                total_condition['to'] = int(total_condition['to']) * 60

        for condition in total_condition:
            if total_condition[condition]:
                has_condition = True

        # Get section conditions
        section_conditions = []
        counter = 1
        detail_key = 'detail_condition_' + key
        while detail_key + '_name_' + str(counter) in request.POST:
            count = str(counter)
            counter += 1
            name = request.POST[detail_key + '_name_' + count]
            from_val = request.POST[detail_key + '_from_' + count]
            to_val = request.POST[detail_key + '_to_' + count]
            no_val = detail_key + '_no_' + count in request.POST

            if name:
                has_condition = True
                condition = {
                    'name': name,
                    'from': from_val if len(from_val) else None,
                    'to': to_val if len(to_val) else None,
                    'no': no_val,
                }

                if key is 'playback':
                    if condition['from']:
                        condition['from'] = (int(condition['from']) * 60) - 60
                    if condition['to']:
                        condition['to'] = int(condition['to']) * 60

                section_conditions.append(condition)

        return has_condition, total_condition, section_conditions

    def _create_row(recid, student_status, user, score_section_names, score, playback_section_names, playback):
        row = {
            'recid': recid,
            'user_id': user.id or '',
            'user_name': user.username or '',
            'user_email': user.email or '',
            'full_name': user.fullname or '',
            'login_code': user.login_code or '',
        }

        # Set member
        # if not user[select_columns.get('member_org')] or user[select_columns.get('member_org')] == org.id:
        if user.code is not None:
            for p in range(1, 11):
                row['org' + str(p)] = getattr(user, 'org' + str(p), '')
                row['item' + str(p)] = getattr(user, 'item' + str(p), '')
        else:
            for p in range(1, 11):
                row['org' + str(p)] = ''
                row['item' + str(p)] = ''

        # Set student status
        row['student_status'] = student_status

        # Set score
        row['total_score'] = score[_(ScoreStore.FIELD_TOTAL_SCORE)] if score else 'None'
        # Set score of section
        if len(score_section_names) > 0:
            for section_name in score_section_names:
                row[section_name] = score[section_name] if score else 'None'

        # Set playback
        row['total_playback'] = playback[_(PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME)] if playback else 'None'
        # Set playback of section
        if len(playback_section_names) > 0:
            for section_name in playback_section_names:
                row[section_name] = playback[section_name] if playback else 'None'

        return row

    where_sql = ""
    option_sql = [org.id, org.id, str(course.id)]
    if not manager.is_director() and manager.is_manager() and Group.objects.filter(org=org).exists():
        if request.current_organization_visible_group_ids:
            where_sql += "AND group_id IN ("
            group_stock = []
            for group_id in map(str, request.current_organization_visible_group_ids):
                group_stock.append("%s")
                option_sql.append(group_id)
            where_sql += ','.join(group_stock)
            where_sql += ") "
        else:
            where_sql += "AND 0 "

    org_item_key_list = []
    org_item_key_list.extend(['org' + str(i) for i in range(1, 11)])
    org_item_key_list.extend(['item' + str(i) for i in range(1, 11)])

    counter = 1
    while 'detail_condition_other_name_' + str(counter) in request.POST:
        count = str(counter)
        counter += 1
        key = request.POST['detail_condition_other_name_' + count]
        value = request.POST['detail_condition_other_' + count]
        if key and key.strip() and value and value.strip():
            if key in ('email', 'username'):
                where_sql += "AND " + key + " LIKE %s "
                option_sql.append("%" + value + "%")
            elif key == 'full_name':
                where_sql += "AND UP.name LIKE %s "
                option_sql.append("%" + value + "%")
            elif key == 'login_code':
                where_sql += "AND LB.login_code LIKE %s "
                option_sql.append("%" + value + "%")
            elif key in org_item_key_list:
                where_sql += "AND " + key + " LIKE %s "
                option_sql.append("%" + value + "%")

        sql = '''SELECT DISTINCT AU.id, AU.email, UP.name as fullname, AU.username, LB.login_code, SU.account_status, MG.org_id, MG.code, 
    MG.org1, MG.org2, MG.org3, MG.org4, MG.org5, MG.org6, MG.org7, MG.org8, MG.org9, MG.org10, 
    MG.item1, MG.item2, MG.item3, MG.item4, MG.item5, MG.item6, MG.item7, MG.item8, MG.item9, MG.item10 
    FROM auth_user as AU
    INNER JOIN student_courseenrollment as SC ON AU.id = SC.user_id 
    LEFT OUTER JOIN student_userstanding as SU ON AU.id = SU.user_id 
    LEFT OUTER JOIN auth_userprofile as UP ON AU.id = UP.user_id 
    LEFT OUTER JOIN ga_login_bizuser as LB ON AU.id = LB.user_id 
    LEFT OUTER JOIN (
      SELECT M.id, M.code, M.is_active, M.is_delete, M.group_id, M.org_id, M.user_id, G.group_code, G.group_name, 
             M.org1, M.org2, M.org3, M.org4, M.org5, M.org6, M.org7, M.org8, M.org9, M.org10, 
             M.item1, M.item2, M.item3, M.item4, M.item5, M.item6, M.item7, M.item8, M.item9, M.item10
      FROM gx_member_member as M LEFT OUTER JOIN gx_org_group_group as G 
      ON M.group_id = G.id  AND M.org_id = %s 
    ) MG ON AU.id = MG.user_id AND MG.org_id = %s 
    WHERE SC.course_id = %s ''' + where_sql + '''
    ORDER BY AU.id ASC'''

    enroll_users = ContractRegister.objects.raw(sql, option_sql)
    enroll_usernames = [enroll_user.username for enroll_user in enroll_users]

    # Score
    has_score_condition, total_score_condition, section_score_conditions = _get_mongo_conditions('score')
    score_batch_status = ScoreBatchStatus.get_last_status(contract.id, course.id)
    if score_batch_status:
        score_store = ScoreStore(contract.id, unicode(course.id))
        # Score section name
        score_section_names = [columns[0] for columns in score_store.get_section_names()]
        # Score records list
        __, score_list = score_store.get_data_for_w2ui(
            total_condition=total_score_condition,
            section_conditions=section_score_conditions,
            usernames=enroll_usernames,
        )
        username_scores = {score[_(ScoreStore.FIELD_USERNAME)]: score for score in score_list}
    else:
        score_section_names = []
        username_scores = {}

    # Playback
    has_playback_condition, total_playback_condition, section_playback_conditions = _get_mongo_conditions('playback')
    playback_batch_status = PlaybackBatchStatus.get_last_status(contract.id, course.id)
    if playback_batch_status:
        playback_store = PlaybackStore(contract.id, unicode(course.id))

        # Playback section name
        playback_section_names = [column[0] for column in playback_store.get_section_names()]
        # Playback records list
        __, playback_list = playback_store.get_data_for_w2ui(
            total_condition=total_playback_condition,
            section_conditions=section_playback_conditions,
            usernames=enroll_usernames,
        )
        username_playback = {playback[_(PlaybackStore.FIELD_USERNAME)]: playback for playback in playback_list}
    else:
        playback_section_names = []
        username_playback = {}

    # Create row by usernames
    show_list = []
    for i, user in enumerate(enroll_users, start=1):
        score = None
        playback = None

        # Check scores
        if user.username in username_scores:
            score = username_scores[user.username]
        elif has_score_condition:
            # Note: Not need loop for check playback if not found user by search conditions of score
            continue

        # Check playback
        if user.username in username_playback:
            playback = username_playback[user.username]
        elif has_playback_condition:
            # Note: Not need append row if not found user by search conditions of score and playback
            continue

        # Check status
        if score:
            student_status = score[_(ScoreStore.FIELD_STUDENT_STATUS)]
        elif playback:
            student_status = playback[_(PlaybackStore.FIELD_STUDENT_STATUS)]
        else:
            course_enrollment = CourseEnrollment.objects.get(course_id=course.id,
                                                             user=user.id)
            if user.account_status is not None \
                    and user.account_status == UserStanding.ACCOUNT_DISABLED:
                student_status = _(ScoreStore.FIELD_STUDENT_STATUS__DISABLED)
            elif self_paced_api.is_course_closed(course_enrollment):
                student_status = _(ScoreStore.FIELD_STUDENT_STATUS__EXPIRED)
            elif course_enrollment.is_active:
                student_status = _(ScoreStore.FIELD_STUDENT_STATUS__ENROLLED)
            else:
                student_status = _(ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED)

        if request.POST['student_status'] and student_status != request.POST['student_status']:
            continue

        show_list.append(
            _create_row(i, student_status, user, score_section_names, score, playback_section_names, playback)
        )
    return JsonResponse({
        'info': _("Successfully to search."),
        'show_list': json.dumps(show_list, cls=EscapedEdxJSONEncoder),
    })


@require_POST
@login_required
@check_course_selection
def reminder_search_mail_send_ajax(request):
    if not request.current_contract.can_send_submission_reminder or 'contract_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    error_messages = []

    # Check test mail
    is_test = 'is_test' in request.POST and request.POST['is_test'] == "1"

    # Check user ids
    if is_test:
        users = [request.user]
    else:
        mail_user_emails = []
        if request.POST['search_user_emails']:
            mail_user_emails = request.POST['search_user_emails'].split(',')
        if len(mail_user_emails) == 0:
            return _error_response(_("Please select user that you want send reminder mail."))

        users = User.objects.filter(email__in=mail_user_emails).select_related('profile')
        for mail_user_email in mail_user_emails:
            if mail_user_email not in users.values_list('email', flat=True):
                error_messages.append(_("{0}:Not found selected user.").format(mail_user_email))

    # Check mail subject
    mail_subject = request.POST['mail_subject']
    mail_subject_max_length = ContractReminderMail._meta.get_field('mail_subject').max_length
    if not mail_subject or not mail_subject.strip():
        return _error_response(_("Please enter the subject of an e-mail."))
    elif len(mail_subject) > mail_subject_max_length:
        return _error_response(_("Subject within {0} characters.").format(mail_subject_max_length))

    # Check mail body
    mail_body = request.POST['mail_body']
    if not mail_body or not mail_body.strip():
        return _error_response(_("Please enter the body of an e-mail."))

    # Check course info
    contract = request.current_contract
    course = request.current_course
    detail = ContractDetail.find_enabled_by_manager_and_contract_and_course(
        manager=request.current_manager, contract=contract, course=course).first()

    # Send mail
    for user in users:
        expire_datetime = None
        if is_test:
            expire_datetime = course.deadline_start
            try:
                profile = UserProfile.objects.get(user=request.user)
                full_name = profile.name
            except UserProfile.DoesNotExist:
                full_name = ''
        else:
            expire_datetime = course.deadline_start
            full_name = user.profile.name
        try:
            send_mail(user, mail_subject.encode('utf-8'), mail_body.encode('utf-8'), {
                'username': user.username,
                'email_address': user.email,
                'fullname': full_name.encode('utf-8'),
                'course_name': course.display_name.encode('utf-8'),
                'expire_date': unicode(expire_datetime.strftime("%Y-%m-%d")) if expire_datetime else '',
            })

        except Exception as ex:
            log.exception('Failed to send the e-mail.' + ex.message)
            error_messages.append(user.email + ":" + _("Failed to send the e-mail."))

    return JsonResponse({
        'info': _("Complete of send the e-mail."),
        'error_messages': json.dumps(error_messages, cls=EscapedEdxJSONEncoder),
    })


def check_contract_bulk_operation(func):
    """
    This checks for bulk operation.
    unregistered students, personalinfo mask.
    """

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if 'students_list' not in request.POST or 'contract_id' not in request.POST:
            return _error_response(_("Unauthorized access."))

        if str(request.current_contract.id) != request.POST['contract_id']:
            return _error_response(_("Current contract is changed. Please reload this page."))

        students_line = request.POST['students_list'].splitlines()
        if not students_line:
            return _error_response(_("Could not find student list."))

        if len(students_line) > settings.BIZ_MAX_BULK_STUDENTS_NUMBER:
            return _error_response(_(
                "It has exceeded the number({max_bulk_students_number}) of cases that can be a time of specification."
            ).format(max_bulk_students_number=settings.BIZ_MAX_BULK_STUDENTS_NUMBER))

        if any([len(s) > settings.BIZ_MAX_CHAR_LENGTH_BULK_STUDENTS_LINE for s in students_line]):
            return _error_response(_(
                "The number of lines per line has exceeded the {biz_max_char_length_register_line} characters."
            ).format(biz_max_char_length_register_line=settings.BIZ_MAX_CHAR_LENGTH_BULK_STUDENTS_LINE))

        kwargs['students'] = students_line
        return func(request, *args, **kwargs)

    return wrapper


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
@check_contract_bulk_operation
def bulk_unregister_students_ajax(request, students):
    """
    Submit task of unregistering students by bulk operation.
    """

    history = ContractTaskHistory.create(request.current_contract, request.user)

    StudentUnregisterTaskTarget.bulk_create_by_text(history, students)

    return _submit_task(request, STUDENT_UNREGISTER, student_unregister, history)


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
@check_contract_bulk_operation
def bulk_personalinfo_mask_ajax(request, students):
    """
    Submit task of masking personal information by bulk operation.
    """

    history = ContractTaskHistory.create(request.current_contract, request.user)

    ContractTaskTarget.bulk_create_by_text(history, students)

    return _submit_task(request, PERSONALINFO_MASK, personalinfo_mask, history)


@require_POST
@login_required
@check_course_selection
def register_additional_info_ajax(request):
    if any(k not in request.POST for k in ['display_name', 'contract_id']):
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    validate_task_message = validate_task(request.current_contract)
    if validate_task_message:
        return _error_response(validate_task_message)

    display_name = request.POST['display_name']
    if not display_name:
        return _error_response(_("Please enter the name of item you wish to add."))

    max_length_display_name = AdditionalInfo._meta.get_field('display_name').max_length
    if len(display_name) > max_length_display_name:
        return _error_response(_("Please enter the name of item within {max_number} characters.").format(
            max_number=max_length_display_name))

    if AdditionalInfo.objects.filter(contract=request.current_contract, display_name=display_name).exists():
        return _error_response(_("The same item has already been registered."))

    max_additional_info = settings.BIZ_MAX_REGISTER_ADDITIONAL_INFO
    if AdditionalInfo.objects.filter(contract=request.current_contract).count() >= max_additional_info:
        return _error_response(
            _("Up to {max_number} number of additional item is created.").format(max_number=max_additional_info))

    try:
        additional_info = AdditionalInfo.objects.create(
            contract=request.current_contract,
            display_name=display_name,
        )
    except:
        log.exception('Failed to register the display-name of an additional-info.')
        return _error_response(_("Failed to register item."))

    return JsonResponse({
        'info': _("New item has been registered."),
        'id': additional_info.id,
    })


@require_POST
@login_required
@check_course_selection
def edit_additional_info_ajax(request):
    if any(k not in request.POST for k in ['additional_info_id', 'display_name', 'contract_id']):
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    validate_task_message = validate_task(request.current_contract)
    if validate_task_message:
        return _error_response(validate_task_message)

    display_name = request.POST['display_name']
    if not display_name:
        return _error_response(_("Please enter the name of item you wish to add."))

    max_length_display_name = AdditionalInfo._meta.get_field('display_name').max_length
    if len(display_name) > max_length_display_name:
        return _error_response(_("Please enter the name of item within {max_number} characters.").format(
            max_number=max_length_display_name))

    additional_info_id = request.POST['additional_info_id']
    if AdditionalInfo.objects.filter(contract=request.current_contract, display_name=display_name).exclude(
            id=additional_info_id).exists():
        return _error_response(_("The same item has already been registered."))

    try:
        AdditionalInfo.objects.filter(
            id=additional_info_id,
            contract=request.current_contract,
        ).update(
            display_name=display_name,
        )
    except:
        log.exception(
            'Failed to edit the display-name of an additional-info id:{}.'.format(request.POST['additional_info_id']))
        return _error_response(_("Failed to edit item."))

    return JsonResponse({
        'info': _("New item has been updated."),
    })


@require_POST
@login_required
@check_course_selection
def delete_additional_info_ajax(request):
    if any(k not in request.POST for k in ['additional_info_id', 'contract_id']):
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    validate_task_message = validate_task(request.current_contract)
    if validate_task_message:
        return _error_response(validate_task_message)

    try:
        additional_info = AdditionalInfo.objects.get(id=request.POST['additional_info_id'],
                                                     contract=request.current_contract)
        AdditionalInfoSetting.objects.filter(contract=request.current_contract,
                                             display_name=additional_info.display_name).delete()
        additional_info.delete()
    except AdditionalInfo.DoesNotExist:
        log.info('Already deleted additional-info id:{}.'.format(request.POST['additional_info_id']))
        return _error_response(_("Already deleted."))
    except:
        log.exception(
            'Failed to delete the display-name of an additional-info id:{}.'.format(request.POST['additional_info_id']))
        return _error_response(_("Failed to deleted item."))

    return JsonResponse({
        'info': _("New item has been deleted."),
    })


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
def update_additional_info_ajax(request):
    if any(k not in request.POST for k in ['update_students_list', 'contract_id']):
        return _error_response(_("Unauthorized access."))

    if any(k not in request.POST for k in ['additional_info']):
        return _error_response(_("No additional item registered."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    students = request.POST['update_students_list'].splitlines()
    if not students:
        return _error_response(_("Could not find student list."))

    if len(students) > settings.BIZ_MAX_REGISTER_NUMBER:
        return _error_response(_(
            "It has exceeded the number({max_register_number}) of cases that can be a time of registration."
        ).format(max_register_number=settings.BIZ_MAX_REGISTER_NUMBER))

    if any([len(s) > settings.BIZ_MAX_CHAR_LENGTH_REGISTER_ADD_INFO_LINE for s in students]):
        return _error_response(_(
            "The number of lines per line has exceeded the {biz_max_char_length_register_line} characters."
        ).format(biz_max_char_length_register_line=settings.BIZ_MAX_CHAR_LENGTH_REGISTER_ADD_INFO_LINE))

    additional_info_list = AdditionalInfo.validate_and_find_by_ids(
        request.current_contract,
        request.POST.getlist('additional_info') if 'additional_info' in request.POST else []
    )
    if additional_info_list is None:
        return _error_response(_("New item registered. Please reload browser."))

    history = ContractTaskHistory.create(request.current_contract, request.user)
    AdditionalInfoUpdateTaskTarget.bulk_create(history, students)

    return _submit_task(request, ADDITIONALINFO_UPDATE, additional_info_update, history, additional_info_list)


@require_POST
@login_required
@check_course_selection
def register_students_template_download(request):
    date = "{0:%Y%m%d}".format(datetime.now())
    org = request.current_organization.org_name
    contract = request.current_contract.contract_name
    if request.current_contract.has_auth:
        arr_header = [_("Email"), _("Username"), _("Last Name"), _("First Name"), _("Login Code"), _("Password"),
                      _("Organization Code"), _("Member Code"), _("Organization") + '1',
                      _("Organization") + '2', _("Organization") + '3', _("Organization") + '4',
                      _("Organization") + '5', _("Organization") + '6', _("Organization") + '7',
                      _("Organization") + '8', _("Organization") + '9', _("Organization") + '10',
                      _("Item") + '1', _("Item") + '2', _("Item") + '3', _("Item") + '4', _("Item") + '5',
                      _("Item") + '6', _("Item") + '7', _("Item") + '8', _("Item") + '9', _("Item") + '10',
                      ]
        arr = _("username1@domain.com,gaccotarou,gacco,taro,,,,,,,,,,,,,,,,,,,,,,,,")
        arr = [arr.split(',')]
    else:
        arr_header = [_("Email"), _("Username"), _("Last Name"), _("First Name"),
                      _("Organization Code"), _("Member Code"), _("Organization") + '1',
                      _("Organization") + '2', _("Organization") + '3', _("Organization") + '4',
                      _("Organization") + '5', _("Organization") + '6', _("Organization") + '7',
                      _("Organization") + '8', _("Organization") + '9', _("Organization") + '10',
                      _("Item") + '1', _("Item") + '2', _("Item") + '3', _("Item") + '4', _("Item") + '5',
                      _("Item") + '6', _("Item") + '7', _("Item") + '8', _("Item") + '9', _("Item") + '10',
                      ]
        arr = _("username1@domain.com,gaccotarou,gacco,taro,,,,,,,,,,,,,,,,,,,,,,")
        arr = [arr.split(',')]

    filename = org + "-" + contract + "-studentsample-" + date + ".csv"
    return create_csv_response(filename, arr_header, arr)


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
def register_students_csv_ajax(request):
    log.info('register_students_csv_ajax')
    if 'csv_data' not in request.FILES or 'contract_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    try:
        csv_data = get_sjis_csv(request, 'csv_data')
        if csv_data[0][0] != _("Email"):
            return _error_response(_("invalid header or file type"))
    except:
        return _error_response(_("invalid header or file type"))
    csv_all_str = ''
    for csv_rows in csv_data:
        if csv_rows[0] == _("Email") or csv_rows[0] == "username1@domain.com":
            continue
        csv_all_str += ','.join(csv_rows) + '\n'

    students = csv_all_str.splitlines()
    if not students:
        log.info('Could not find student list.')
        return _error_response(_("Could not find student list."))

    if len(students) > BIZ_MAX_REGISTER_NUMBER:
        log.info('max_register_number')
        return _error_response(_(
            "It has exceeded the number({max_register_number}) of cases that can be a time of registration."
        ).format(max_register_number=BIZ_MAX_REGISTER_NUMBER))

    if any([len(s) > BIZ_MAX_CHAR_LENGTH_REGISTER_LINE for s in students]):
        log.info('biz_max_char_length_register_line')
        return _error_response(_(
            "The number of lines per line has exceeded the {biz_max_char_length_register_line} characters."
        ).format(biz_max_char_length_register_line=BIZ_MAX_CHAR_LENGTH_REGISTER_LINE))

    register_status = request.POST.get('register_status')
    if register_status and register_status != REGISTER_INVITATION_CODE:
        log.info('Invalid access.')
        return _error_response(_("Invalid access."))

    register_status = register_status or INPUT_INVITATION_CODE

    # To register status. Register or Input
    students = [u'{},{}'.format(register_status, s) for s in students]

    log.info('register_students_csv_ajax_create')
    history = ContractTaskHistory.create(request.current_contract, request.user)
    log.info('register_students_csv_ajax_bulk_create:task_id' + str(history.id))
    # Repeat register 1000, because timeout of mysql connection.
    task_target_max_num = 1000
    for i in range(1, int(math.ceil(float(len(students)) / task_target_max_num)) + 1):
        StudentMemberRegisterTaskTarget.bulk_create(
            history, students[(i - 1) * task_target_max_num:i * task_target_max_num])
    log.info('register_students_csv_ajax_submit_task:task_id' + str(history.id))
    return _submit_task(request, STUDENT_MEMBER_REGISTER, student_member_register, history)


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
def register_students_new_ajax(request):
    log.info('register_students_new_ajax')
    if 'contract_id' not in request.POST or 'employee_email' not in request.POST or 'user_name' not in request.POST \
            or 'employee_last_name' not in request.POST or 'employee_first_name' not in request.POST:
        log.info('Unauthorized access.')
        return _error_response(_("Unauthorized access."))

    if request.current_contract.has_auth and ('login_code' not in request.POST or 'password' not in request.POST):
        log.info('Unauthorized access.')
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        log.info('Current contract is changed. Please reload this page.')
        return _error_response(_("Current contract is changed. Please reload this page."))

    student = request.POST['employee_email'] + ',' + request.POST['user_name'] + ',' + request.POST[
        'employee_last_name'] + ',' + request.POST['employee_first_name'] + ','
    if request.current_contract.has_auth:
        student += request.POST['login_code'] + ',' + request.POST['password'] + ','

    student += request.POST['employee_group_code'] + ',' + request.POST['employee_code'] + ','
    student += request.POST['org_attr1'] + ',' + request.POST['org_attr2'] + ','
    student += request.POST['org_attr3'] + ',' + request.POST['org_attr4'] + ','
    student += request.POST['org_attr5'] + ',' + request.POST['org_attr6'] + ','
    student += request.POST['org_attr7'] + ',' + request.POST['org_attr8'] + ','
    student += request.POST['org_attr9'] + ',' + request.POST['org_attr10'] + ','
    student += request.POST['grp_attr1'] + ',' + request.POST['grp_attr2'] + ','
    student += request.POST['grp_attr3'] + ',' + request.POST['grp_attr4'] + ','
    student += request.POST['grp_attr5'] + ',' + request.POST['grp_attr6'] + ','
    student += request.POST['grp_attr7'] + ',' + request.POST['grp_attr8'] + ','
    student += request.POST['grp_attr9'] + ',' + request.POST['grp_attr10']

    students = []
    students.append(student)

    if any([len(s) > BIZ_MAX_CHAR_LENGTH_REGISTER_LINE for s in students]):
        log.info('biz_max_char_length_register_line')
        return _error_response(_(
            "The number of lines per line has exceeded the {biz_max_char_length_register_line} characters."
        ).format(biz_max_char_length_register_line=BIZ_MAX_CHAR_LENGTH_REGISTER_LINE))

    register_status = request.POST.get('register_status')
    if register_status and register_status != REGISTER_INVITATION_CODE:
        log.info('Invalid access.')
        return _error_response(_("Invalid access."))

    register_status = register_status or INPUT_INVITATION_CODE

    # To register status. Register or Input
    students = [u'{},{}'.format(register_status, s) for s in students]

    log.info('register_students_new_ajax_create')
    history = ContractTaskHistory.create(request.current_contract, request.user)
    log.info('register_students_new_ajax_bulk_create:task_id' + str(history.id))
    StudentMemberRegisterTaskTarget.bulk_create(history, students)
    log.info('register_students_new_ajax_submit_task:task_id' + str(history.id))
    return _submit_task(request, STUDENT_MEMBER_REGISTER, student_member_register, history)


@require_POST
@login_required
@check_course_selection
def register_students_search_students_ajax(request):
    if not all([k in request.POST for k in ['contract_id', 'search_group_code', 'search_contract_id',
                                            'search_login_code', 'search_name', 'search_email']]):
        log.info('Unauthorized access.')
        return _error_response(_("Unauthorized access."))

    registers = _create_filter_register_students_search_students_ajax(request)

    select_columns = dict({
        'user_id': 'user__id',
        'username': 'user__username',
        'email': 'user__email',
        'login_code': 'user__bizuser__login_code',
        'full_name': 'user__profile__name'
    })

    search_list = []
    search_unique_ids = []
    for i, register in enumerate(registers.values(*select_columns.values()), start=1):
        register_dict = dict(register)
        if register_dict.get(select_columns.get('user_id')) not in search_unique_ids:
            search_unique_ids.append(register_dict.get(select_columns.get('user_id')))
            search_list.append({
                'recid': i,
                'user_id': register_dict.get(select_columns.get('user_id'), ''),
                'full_name': register_dict.get(select_columns.get('full_name'), ''),
                'user_name': register_dict.get(select_columns.get('username'), ''),
                'user_email': register_dict.get(select_columns.get('email'), ''),
                'login_code': register_dict.get(select_columns.get('login_code'), '')
            })

    return JsonResponse({
        'status': 'success',
        'total': len(search_list),
        'records': search_list,
    })


def _create_filter_register_students_search_students_ajax(request):
    """
    Create filter for model of 'Member' or 'ContractRegister'
    :param request: HttpRequest
    :return: search_model
    """
    if request.POST['search_contract_id']:
        search_model = ContractRegister.objects.filter(
            contract_id=request.POST['search_contract_id'],
            status__in=[REGISTER_INVITATION_CODE, INPUT_INVITATION_CODE],
            user__is_active=True).select_related('user').order_by('id')
        member_filter_key = 'user__member__'
    else:
        search_model = Member.find_active_by_org(
            org=request.current_organization).select_related('user', 'group', 'org', 'user__bizuser', 'user__profile')
        member_filter_key = ''

    filters = {}
    # Full name
    if request.POST['search_name'] != '':
        filters['user__profile__name__icontains'] = request.POST['search_name']
    # Login code
    if request.POST['search_login_code'] != '':
        filters['user__bizuser__login_code__icontains'] = request.POST['search_login_code']
    # Email
    if request.POST['search_email'] != '':
        filters['user__email__icontains'] = request.POST['search_email']
    # Group code
    if request.POST['search_group_code'] != '':
        filters[member_filter_key + 'group__group_code'] = request.POST['search_group_code']
    # Org1-10, Item1-10
    for i in range(1, 11):
        if request.POST['search_org' + str(i)] != '':
            filters[member_filter_key + 'org' + str(i)] = request.POST['search_org' + str(i)]
        if request.POST['search_grp' + str(i)] != '':
            filters[member_filter_key + 'item' + str(i)] = request.POST['search_grp' + str(i)]

    return search_model.filter(**filters)


@transaction.non_atomic_requests
@require_POST
@login_required
@check_course_selection
def register_students_list_ajax(request):
    log.info('register_students_list_ajax_start')
    if 'contract_id' not in request.POST or 'add_list' not in request.POST:
        log.info('Unauthorized access.')
        return _error_response(_("Unauthorized access."))
    if str(request.current_contract.id) != request.POST['contract_id']:
        log.info('Current contract is changed. Please reload this page.')
        return _error_response(_("Current contract is changed. Please reload this page."))
    add_list = json.loads(request.POST['add_list'])
    insert_recodes = ''

    for list_item in add_list:
        full_name = list_item['full_name'] or ''
        user_name = list_item['user_name'] or ''
        user_email = list_item['user_email'] or ''
        login_code = list_item['login_code'] or ''
        if request.current_contract.has_auth:
            if login_code != '':
                # Set dummy password to use task of 'student_register'. This password 'AbcDef123' don't registration.
                insert_recodes += user_email + ',' + user_name + ',' + full_name + ',' + login_code + ',AbcDef123' + '\n'
            else:
                log.info('This course required login code register')
                return _error_response(_("This course required login code register"))
        else:
            insert_recodes += user_email + ',' + user_name + ',' + full_name + '\n'

    # common
    students = insert_recodes.splitlines()
    if not students:
        log.info('Could not find student list.')
        return _error_response(_("Could not find student list."))

    if len(students) > BIZ_MAX_REGISTER_NUMBER:
        log.info('max_register_number')
        return _error_response(_(
            "It has exceeded the number({max_register_number}) of cases that can be a time of registration."
        ).format(max_register_number=BIZ_MAX_REGISTER_NUMBER))

    if any([len(s) > BIZ_MAX_CHAR_LENGTH_REGISTER_LINE for s in students]):
        log.info('biz_max_char_length_register_line')
        return _error_response(_(
            "The number of lines per line has exceeded the {biz_max_char_length_register_line} characters."
        ).format(biz_max_char_length_register_line=BIZ_MAX_CHAR_LENGTH_REGISTER_LINE))

    register_status = request.POST.get('register_status')
    if register_status and register_status != REGISTER_INVITATION_CODE:
        log.info('Invalid access.')
        return _error_response(_("Invalid access."))

    register_status = register_status or INPUT_INVITATION_CODE

    # To register status. Register or Input
    students = [u'{},{}'.format(register_status, s) for s in students]

    log.info('register_students_list_ajax_create')
    history = ContractTaskHistory.create(request.current_contract, request.user)
    log.info('register_students_list_ajax_bulk_create:task_id' + str(history.id))
    # Repeat register 1000, because timeout of mysql connection.
    task_target_max_num = 1000
    for i in range(1, int(math.ceil(float(len(students)) / task_target_max_num)) + 1):
        StudentRegisterTaskTarget.bulk_create(
            history, students[(i - 1) * task_target_max_num:i * task_target_max_num])
    log.info('register_students_list_ajax_submit_task:task_id' + str(history.id))
    return _submit_task(request, STUDENT_REGISTER, student_register, history)

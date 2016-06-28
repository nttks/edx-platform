"""
Views for contract_operation feature
"""
from collections import defaultdict
from functools import wraps
import hashlib
import json
import logging

from celery.states import READY_STATES
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory, ContractTaskTarget
from biz.djangoapps.ga_contract_operation.tasks import personalinfo_mask, TASKS
from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting, ContractRegister, STATUS as CONTRACT_REGISTER_STATUS, UNREGISTER_INVITATION_CODE
from biz.djangoapps.util.access_utils import has_staff_access
from biz.djangoapps.util.decorators import check_course_selection
from biz.djangoapps.util.task_utils import submit_task
from edxmako.shortcuts import render_to_response
from lms.djangoapps.instructor.enrollment import send_mail_to_student
from lms.djangoapps.instructor.views.api import (
    generate_unique_password, EMAIL_INDEX, NAME_INDEX, USERNAME_INDEX
)
from microsite_configuration import microsite
from openedx.core.djangoapps.ga_task.api import AlreadyRunningError
from openedx.core.djangoapps.ga_task.task import STATES as TASK_STATES
from openedx.core.lib.ga_datetime_utils import to_timezone
from openedx.core.lib.json_utils import EscapedEdxJSONEncoder
from student.forms import AccountCreationForm
from student.models import CourseEnrollment
from student.views import _do_create_account, AccountValidationError
from util.json_request import JsonResponse, JsonResponseBadRequest

log = logging.getLogger(__name__)


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
def students(request):
    show_list, status, additional_searches, additional_columns = _contract_register_list(request.current_contract)

    return render_to_response(
        'ga_contract_operation/students.html',
        {
            'show_list': json.dumps(show_list, cls=EscapedEdxJSONEncoder),
            'status_list': json.dumps(status.values(), cls=EscapedEdxJSONEncoder),
            'additional_searches': json.dumps(additional_searches, cls=EscapedEdxJSONEncoder),
            'additional_columns': json.dumps(additional_columns, cls=EscapedEdxJSONEncoder),
        }
    )


def _contract_register_list(contract):
    status = {k: unicode(v) for k, v in dict(CONTRACT_REGISTER_STATUS).items()}
    additional_searches = []
    additional_columns = []

    additional_infos = contract.additional_info.all()
    has_additional_infos = bool(additional_infos)
    # Additional settings value of user.
    # key:user_id, value:dict{key:display_name, value:additional_settings_value}
    user_additional_settings = defaultdict(dict)
    if has_additional_infos:
        display_names = []
        for additional_info in additional_infos:
            additional_searches.append({
                'field': additional_info.display_name,
                'caption': additional_info.display_name,
                'type': 'text',
            })
            additional_columns.append({
                'field': additional_info.display_name,
                'caption': additional_info.display_name,
                'sortable': True,
                'hidden': False,
                'size': 1,
            })
            display_names.append(additional_info.display_name)

        for additional_settings in AdditionalInfoSetting.find_by_contract(contract):
            if additional_settings.display_name in display_names:
                user_additional_settings[additional_settings.user_id][additional_settings.display_name] = additional_settings.value

    def _create_row(i, contract_register):
        row = {
            'recid': i + 1,
            'contract_register_id': contract_register.id,
            'contract_register_status': status[contract_register.status],
            'full_name': contract_register.user.profile.name,
            'user_name': contract_register.user.username,
            'user_email': contract_register.user.email,
        }
        # Set additional settings value of user.
        if has_additional_infos and contract_register.user_id in user_additional_settings:
            row.update(user_additional_settings[contract_register.user_id])
        return row

    contract_register_list = [
        _create_row(i, contract_register)
        for i, contract_register in enumerate(ContractRegister.find_by_contract(contract))
    ]

    return (contract_register_list, status, additional_searches, additional_columns)


@require_POST
@login_required
@check_course_selection
@check_contract_register_selection
def unregister_students_ajax(request, registers):

    valid_register_list = []
    warning_register_list = []

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
        with transaction.commit_on_success():
            for register in valid_register_list:
                # ContractRegister and ContractRegisterHistory for end-of-month
                register.status = UNREGISTER_INVITATION_CODE
                register.save()
                # CourseEnrollment only spoc TODO should do by celery
                if request.current_contract.is_spoc_available:
                    for course_key in course_keys:
                        if CourseEnrollment.is_enrolled(register.user, course_key) and not has_staff_access(register.user, course_key):
                            CourseEnrollment.unenroll(register.user, course_key)
    except Exception:
        unregister_list = [register.id for register in registers]
        log.exception('Can not unregister. contract_id({}), unregister_list({})'.format(request.current_contract.id, unregister_list))
        return _error_response(_('Failed to batch unregister. Please operation again after a time delay.'))

    show_list, __, __, __ = _contract_register_list(request.current_contract)

    warning = _('Already unregisterd {user_count} users.').format(user_count=len(warning_register_list)) if warning_register_list else ''

    return JsonResponse({
        'info': _('Succeed to unregister {user_count} users.').format(user_count=len(valid_register_list)) + warning,
        'show_list': show_list,
    })


@require_GET
@login_required
@check_course_selection
def register_students(request):
    return render_to_response('ga_contract_operation/register_students.html')


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

    warnings = []
    row_errors = []
    general_errors = []

    def _make_response(general_message=None):
        """
        Create and return response object
        -If specified a general_message, append to general_errors.
        """

        if general_message:
            general_errors.append({'username': '', 'email': '', 'response': general_message})
        return JsonResponse({
            'row_errors': row_errors,
            'general_errors': general_errors,
            'warnings': warnings
        })

    if 'students_list' not in request.POST or 'contract_id' not in request.POST:
        return _make_response(_('Unauthorized access.'))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _make_response(_('Current contract is changed. Please reload this page.'))

    students = [row.split(',') if row else [] for row in request.POST['students_list'].splitlines()]
    if not students:
        return _make_response(_('Could not find student list.'))

    generated_passwords = []
    row_num = 0
    for student in students:
        row_num = row_num + 1

        # 3 columns(email,username,name) 1 line
        if len(student) != 3:
            if len(student) > 0:
                general_errors.append({
                    'username': '',
                    'email': '',
                    'response': _('Data in row #{row_num} must have exactly three columns: email, username, and full name.').format(row_num=row_num)
                })
            continue

        email = student[EMAIL_INDEX]
        username = student[USERNAME_INDEX]
        name = student[NAME_INDEX]

        try:
            validate_email(email)
        except ValidationError:
            row_errors.append({
                'username': username, 'email': email, 'response': _('Invalid email {email_address}.').format(email_address=email)})
        else:
            email_params = {
                'site_name': microsite.get_value('SITE_NAME', settings.SITE_NAME),
                'platform_name': microsite.get_value('platform_name', settings.PLATFORM_NAME),
                'email_address': email,
            }
            if User.objects.filter(email=email).exists():
                user = User.objects.get(email=email)

                if user.username != username:
                    warning_message = _(
                        'An account with email {email} exists but the registered username {username} is different.'
                    ).format(email=email, username=user.username)

                    warnings.append({
                        'username': username, 'email': email, 'response': warning_message
                    })
                    log.warning(u'email %s already exist', email)

                # Create contract register if not created.
                ContractRegister.objects.get_or_create(user=user, contract=request.current_contract)

                email_params['message'] = 'biz_account_notice'
                email_params['username'] = user.username
                send_mail_to_student(email, email_params)
                log.info(u'email sent to created user at %s', email)

            else:
                password = generate_unique_password(generated_passwords)

                try:
                    form = AccountCreationForm(
                        data={
                            'username': username,
                            'email': email,
                            'password': password,
                            'name': name,
                        },
                        tos_required=False
                    )
                    (user, profile, registration) = _do_create_account(form)
                    # Do activation for new user.
                    registration.activate()
                except (IntegrityError, AccountValidationError):
                    row_errors.append({
                        'username': username, 'email': email, 'response': _('Username {user} already exists.').format(user=username)})
                except ValidationError as ex:
                    row_errors.append({
                        'username': username, 'email': email, 'response': ' '.join(ex.messages)})
                except Exception as ex:
                    log.exception(type(ex).__name__)
                    row_errors.append({
                        'username': username, 'email': email, 'response': type(ex).__name__})
                else:
                    # Create contract register if not created.
                    ContractRegister.objects.get_or_create(user=user, contract=request.current_contract)

                    email_params['message'] = 'biz_account_creation'
                    email_params['password'] = password
                    send_mail_to_student(email, email_params)
                    log.info(u'email sent to new created user at %s', email)

    return _make_response()


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

    task_histories = [
        {
            'recid': i + 1,
            'task_type': TASKS[task.task_type] if task and task.task_type in TASKS else _('Unknown'),
            'task_state': _task_state(task),
            'task_result': _task_result(task),
            'requester': history.requester.username,
            'created': to_timezone(history.created).strftime('%Y/%m/%d %H:%M:%S'),
        }
        for i, (history, task) in enumerate(ContractTaskHistory.find_by_contract_with_task(request.current_contract))
    ]
    # The structure of the response is in accordance with the specifications of the load function of w2ui.
    return JsonResponse({
        'status': 'success',
        'total': len(task_histories),
        'records': task_histories,
    })


@require_POST
@login_required
@check_course_selection
@check_contract_register_selection
def submit_personalinfo_mask(request, registers):
    """
    Submit task of masking personal information.
    """
    def _submit_task(history):
        task_type = 'personalinfo_mask'
        task_class = personalinfo_mask
        task_input = {
            'contract_id': request.current_contract.id,
            'history_id': history.id,
        }
        # personalinfo_mask task prevents duplicate execution by contract_id
        task_key = hashlib.md5(str(request.current_contract.id)).hexdigest()
        task = submit_task(request, task_type, task_class, task_input, task_key)
        history.link_to_task(task)

    if not request.current_contract.is_spoc_available:
        return _error_response(_("Unauthorized access."))

    history = ContractTaskHistory.create(request.current_contract, request.user)
    ContractTaskTarget.bulk_create(history, registers)

    try:
        _submit_task(history)
    except AlreadyRunningError:
        return _error_response(
            _("Processing of {task_type} is running.").format(task_type=_("Personal Information Mask")) +
            _("Execution status, please check from the task history.")
        )

    return JsonResponse({
        'info': _("Began the processing of {task_type}.").format(task_type=_("Personal Information Mask")) + _("Execution status, please check from the task history."),
    })

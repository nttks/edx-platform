"""
Views for contract_operation feature
"""
from collections import defaultdict
from functools import wraps
import json
import logging

from celery.states import READY_STATES
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_achievement.management.commands.update_biz_score_status import get_grouped_target_sections
from biz.djangoapps.ga_contract.models import AdditionalInfo
from biz.djangoapps.ga_contract_operation.models import (
    ContractMail, ContractReminderMail,
    ContractTaskHistory, ContractTaskTarget, StudentRegisterTaskTarget,
    StudentUnregisterTaskTarget, AdditionalInfoUpdateTaskTarget,
)
from biz.djangoapps.ga_contract_operation.tasks import (
    personalinfo_mask, student_register, student_unregister, additional_info_update,
    TASKS, STUDENT_REGISTER, STUDENT_UNREGISTER, PERSONALINFO_MASK, ADDITIONALINFO_UPDATE,
)
from biz.djangoapps.ga_contract_operation.utils import send_mail
from biz.djangoapps.ga_invitation.models import (
    AdditionalInfoSetting,
    ContractRegister,
    STATUS as CONTRACT_REGISTER_STATUS,
    INPUT_INVITATION_CODE,
    REGISTER_INVITATION_CODE,
    UNREGISTER_INVITATION_CODE
)
from biz.djangoapps.util.access_utils import has_staff_access
from biz.djangoapps.util.decorators import check_course_selection
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder
from biz.djangoapps.util.task_utils import submit_task, validate_task, get_task_key
from edxmako.shortcuts import render_to_response

from openedx.core.djangoapps.ga_task.api import AlreadyRunningError
from openedx.core.djangoapps.ga_task.task import STATES as TASK_STATES
from openedx.core.lib.ga_datetime_utils import to_timezone
from student.models import CourseEnrollment
from util.json_request import JsonResponse, JsonResponseBadRequest
from xmodule.modulestore.django import modulestore

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
    return render_to_response(
        'ga_contract_operation/register_students.html',
        {
            'max_register_number': "{:,d}".format(int(settings.BIZ_MAX_REGISTER_NUMBER)),
            'additional_info_list': AdditionalInfo.objects.filter(contract=request.current_contract),
            'max_length_additional_info_display_name': AdditionalInfo._meta.get_field('display_name').max_length,
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

    if 'students_list' not in request.POST or 'contract_id' not in request.POST:
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    students = request.POST['students_list'].splitlines()
    if not students:
        return _error_response(_("Could not find student list."))

    if len(students) > settings.BIZ_MAX_REGISTER_NUMBER:
        return _error_response(_(
            "It has exceeded the number({max_register_number}) of cases that can be a time of registration."
        ).format(max_register_number=settings.BIZ_MAX_REGISTER_NUMBER))

    if any([len(s) > settings.BIZ_MAX_CHAR_LENGTH_REGISTER_LINE for s in students]):
        return _error_response(_(
            "The number of lines per line has exceeded the {biz_max_char_length_register_line} characters."
        ).format(biz_max_char_length_register_line=settings.BIZ_MAX_CHAR_LENGTH_REGISTER_LINE))

    register_status = request.POST.get('register_status')
    if register_status and register_status != REGISTER_INVITATION_CODE:
        return _error_response(_("Invalid access."))

    register_status = register_status or INPUT_INVITATION_CODE

    # To register status. Register or Input
    students = [u'{},{}'.format(register_status, s) for s in students]

    history = ContractTaskHistory.create(request.current_contract, request.user)
    StudentRegisterTaskTarget.bulk_create(history, students)

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

        # task prevents duplicate execution by contract_id
        task = submit_task(request, task_type, task_class, task_input, get_task_key(request.current_contract))
        history.link_to_task(task)
    except AlreadyRunningError:
        return _error_response(
            _("Processing of {task_type} is running.").format(task_type=TASKS[task_type]) +
            _("Execution status, please check from the task history.")
        )

    return JsonResponse({
        'info': _("Began the processing of {task_type}.").format(task_type=TASKS[task_type]) + _("Execution status, please check from the task history."),
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

    if not request.current_contract.can_customize_mail or any(k not in request.POST for k in ['mail_type', 'mail_subject', 'mail_body', 'contract_id']):
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

    if not request.current_contract.can_customize_mail or any(k not in request.POST for k in ['mail_type', 'mail_subject', 'mail_body', 'contract_id']):
        return _error_response(_("Unauthorized access."))

    mail_type = request.POST['mail_type']
    if not ContractMail.is_mail_type(mail_type):
        log.warning('Illegal mail-type: {}'.format(mail_type))
        return _error_response(_("Unauthorized access."))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_("Current contract is changed. Please reload this page."))

    contract_mail = ContractMail.get_or_default(request.current_contract, mail_type)
    if contract_mail.mail_subject != request.POST['mail_subject'] or contract_mail.mail_body != request.POST['mail_body']:
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
def reminder_mail(request):
    if not request.current_contract.can_send_submission_reminder:
        raise Http404()

    if request.current_contract.can_send_submission_reminder:
        submission_reminder_mail = ContractReminderMail.get_or_default(request.current_contract,
                                                                       ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER)

    return render_to_response(
        'ga_contract_operation/reminder_mail.html',
        {
            'mail_info_list': [
                submission_reminder_mail,
            ],
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
        contract_mail, __ = ContractReminderMail.objects.get_or_create(contract=request.current_contract,
                                                                       mail_type=mail_type)
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
        return _error_response(_("Please enter the name of item within {max_number} characters.").format(max_number=max_length_display_name))

    if AdditionalInfo.objects.filter(contract=request.current_contract, display_name=display_name).exists():
        return _error_response(_("The same item has already been registered."))

    max_additional_info = settings.BIZ_MAX_REGISTER_ADDITIONAL_INFO
    if AdditionalInfo.objects.filter(contract=request.current_contract).count() >= max_additional_info:
        return _error_response(_("Up to {max_number} number of additional item is created.").format(max_number=max_additional_info))

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
        return _error_response(_("Please enter the name of item within {max_number} characters.").format(max_number=max_length_display_name))

    additional_info_id = request.POST['additional_info_id']
    if AdditionalInfo.objects.filter(contract=request.current_contract, display_name=display_name).exclude(id=additional_info_id).exists():
        return _error_response(_("The same item has already been registered."))

    try:
        AdditionalInfo.objects.filter(
            id=additional_info_id,
            contract=request.current_contract,
        ).update(
            display_name=display_name,
        )
    except:
        log.exception('Failed to edit the display-name of an additional-info id:{}.'.format(request.POST['additional_info_id']))
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
        additional_info = AdditionalInfo.objects.get(id=request.POST['additional_info_id'], contract=request.current_contract)
        AdditionalInfoSetting.objects.filter(contract=request.current_contract, display_name=additional_info.display_name).delete()
        additional_info.delete()
    except AdditionalInfo.DoesNotExist:
        log.info('Already deleted additional-info id:{}.'.format(request.POST['additional_info_id']))
        return _error_response(_("Already deleted."))
    except:
        log.exception('Failed to delete the display-name of an additional-info id:{}.'.format(request.POST['additional_info_id']))
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

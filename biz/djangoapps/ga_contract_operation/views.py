"""
Views for contract_operation feature
"""
import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting, ContractRegister, STATUS as CONTRACT_REGISTER_STATUS, UNREGISTER_INVITATION_CODE
from biz.djangoapps.util.access_utils import has_staff_access
from biz.djangoapps.util.decorators import check_course_selection
from courseware.courses import get_course_with_access
from edxmako.shortcuts import render_to_response
from lms.djangoapps.instructor.enrollment import send_mail_to_student
from lms.djangoapps.instructor.views.api import (
    generate_unique_password, EMAIL_INDEX, NAME_INDEX, USERNAME_INDEX
)
from microsite_configuration import microsite
from openedx.core.lib.json_utils import EscapedEdxJSONEncoder
from student.forms import AccountCreationForm
from student.models import CourseEnrollment
from student.views import _do_create_account, AccountValidationError
from util.json_request import JsonResponse

log = logging.getLogger(__name__)


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
    contract_register_list= []
    status = {k: unicode(v) for k, v in dict(CONTRACT_REGISTER_STATUS).items()}
    additional_searches = []
    additional_columns = []

    additional_infos = contract.additional_info.all()
    if additional_infos:
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

    for i, contract_register in enumerate(ContractRegister.find_by_contract(contract)):
        row = {
            'recid': i + 1,
            'contract_register_id': contract_register.id,
            'contract_register_status': status[contract_register.status],
            'full_name': contract_register.user.profile.name,
            'user_name': contract_register.user.username,
            'user_email': contract_register.user.email,
        }
        additional_settings = AdditionalInfoSetting.objects.raw('''
            SELECT s.id, s.user_id, s.contract_id, a.display_name, s.value, s.created FROM ga_contract_additionalinfo a
            LEFT OUTER JOIN ga_invitation_additionalinfosetting s
            ON a.contract_id = s.contract_id and a.display_name = s.display_name
            WHERE a.contract_id = {} and (s.user_id = {} or s.user_id IS NULL)
            ORDER BY a.id
            '''.format(contract.id, contract_register.user.id))
        if additional_settings:
            row.update({
                additional_setting.display_name: additional_setting.value
                for additional_setting in additional_settings
            })
        contract_register_list.append(row)
    return (contract_register_list, status, additional_searches, additional_columns)


@require_POST
@login_required
@check_course_selection
def unregister_students_ajax(request):

    def _error_response(message):
        return JsonResponse({
            'error': message,
        })

    if 'target_list' not in request.POST or 'contract_id' not in request.POST:
        return _error_response(_('Unauthorized access.'))

    if str(request.current_contract.id) != request.POST['contract_id']:
        return _error_response(_('Current contract is changed. Please reload this page.'))

    unregister_list = request.POST.getlist('target_list')
    valid_register_list = []
    warning_register_list = []

    # validate
    for register in ContractRegister.objects.select_related().filter(id__in=unregister_list):
        # Validate contract
        if register.contract != request.current_contract:
            log.warning(
                'Not found register in contract_id({}) contract_register_id({}), user_id({})'.format(
                    request.current_contract.id,
                    register.id,
                    register.user.id
                ))
            return _error_response(_('Unauthorized access.'))
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

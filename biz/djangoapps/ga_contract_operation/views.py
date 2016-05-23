"""
Views for contract_operation feature
"""
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_invitation.models import ContractRegister, STATUS as CONTRACT_REGISTER_STATUS
from biz.djangoapps.ga_manager.models import (
    Manager, ManagerPermission, PERMISSION_AGGREGATOR, PERMISSION_DIRECTOR, PERMISSION_MANAGER,
)
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.util.decorators import check_course_selection
from edxmako.shortcuts import render_to_response
from instructor.views.tools import get_student_from_identifier
from lms.djangoapps.instructor.enrollment import send_mail_to_student
from lms.djangoapps.instructor.views.api import (
    generate_unique_password, create_survey_response,
    EMAIL_INDEX, NAME_INDEX, USERNAME_INDEX
)
from microsite_configuration import microsite
from openedx.core.lib.json_utils import EscapedEdxJSONEncoder
from student.forms import AccountCreationForm
from student.models import UserStanding
from student.views import _do_create_account, AccountValidationError
from util.json_request import JsonResponse

log = logging.getLogger(__name__)


@require_GET
@login_required
@check_course_selection
def students(request):
    show_list = []
    status = {k: unicode(v) for k, v in dict(CONTRACT_REGISTER_STATUS).items()}
    for i, contract_register in enumerate(ContractRegister.find_by_contract(request.current_contract)):
        show_list.append({
            'recid': i + 1,
            'contract_register_status': status[contract_register.status],
            'user_name': contract_register.user.profile.name,
            'user_email': contract_register.user.email,
        })

    return render_to_response(
        'ga_contract_operation/students.html',
        {
            'show_list': json.dumps(show_list, cls=EscapedEdxJSONEncoder),
            'status_list': json.dumps(status.values(), cls=EscapedEdxJSONEncoder),
        }
    )


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

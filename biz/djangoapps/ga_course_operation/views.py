"""
This module is view of course_operation.
"""
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.validators import validate_email
from django.db import IntegrityError
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie

from edxmako.shortcuts import render_to_response
from microsite_configuration import microsite
from student.forms import AccountCreationForm
from student.views import _do_create_account, AccountValidationError
from util.json_request import JsonResponse

from lms.djangoapps.instructor.enrollment import (
    get_email_params, send_mail_to_student
)
from lms.djangoapps.instructor.views.api import (
    generate_unique_password, create_survey_response,
    EMAIL_INDEX, NAME_INDEX, USERNAME_INDEX
)

from biz.djangoapps.util.decorators import check_course_selection, require_survey, _render_403
from biz.djangoapps.ga_invitation.models import ContractRegister


log = logging.getLogger(__name__)


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@check_course_selection
def dashboard(request, course_id):
    """
    Displays the biz management dashboard.
    Requires biz course_operation access and equal current course_id and course_id of argument.
    """

    if unicode(request.current_course.id) != course_id:
        return _render_403(request)

    return render_to_response('ga_course_operation/dashboard.html', {
        'course': request.current_course,
        'section_membership': {
            'upload_student_button_url': reverse('biz:course_operation:register_students', kwargs={'course_id': course_id}),
        },
        'section_survey': {
            'get_survey_url': reverse('biz:course_operation:get_survey', kwargs={'course_id': course_id}),
        },
    })


@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@check_course_selection
def register_students(request, course_id):
    """
    Create new accounts.
    Passing a list of students.
    Order in list should be the following email = 0; username = 1; name = 2.
    Requires biz course_operation access and equal current course_id and course_id of argument.

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
        -If speciried a general_message, append to general_errors.
        """

        if general_message:
            general_errors.append({'username': '', 'email': '', 'response': general_message})
        return JsonResponse({
            'row_errors': row_errors,
            'general_errors': general_errors,
            'warnings': warnings
        })

    if unicode(request.current_course.id) != course_id:
        return _make_response(_('Current course is changed. Please reload this page.'))

    if 'students_list' not in request.POST:
        return _make_response(_('Could not find student list.'))

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

        email_params = get_email_params(request.current_course, True, secure=request.is_secure())
        try:
            validate_email(email)
        except ValidationError:
            row_errors.append({
                'username': username, 'email': email, 'response': _('Invalid email {email_address}.').format(email_address=email)})
        else:
            email_params['email_address'] = email
            email_params['platform_name'] = microsite.get_value('platform_name', settings.PLATFORM_NAME)
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


@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@check_course_selection
@require_survey
def get_survey(request, course_id):
    return create_survey_response(request, course_id)

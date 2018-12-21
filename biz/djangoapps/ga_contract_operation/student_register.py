# -*- coding: utf-8 -*-
import logging
import re
import time

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.core.mail import send_mail as django_send_mail, get_connection as get_mail_connection
from django.core.validators import validate_email
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract_operation.models import ContractMail, ContractTaskHistory, StudentRegisterTaskTarget
from biz.djangoapps.ga_invitation.models import ContractRegister, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE
from biz.djangoapps.ga_login.models import BizUser, LOGIN_CODE_MIN_LENGTH, LOGIN_CODE_MAX_LENGTH
from bulk_email.models import Optout
from lms.djangoapps.instructor.views.api import generate_unique_password
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress
from openedx.core.lib.ga_mail_utils import replace_braces
from enrollment.api import _default_course_mode
from student.forms import AccountCreationForm
from student.models import CourseEnrollment, UserProfile
from student.views import _do_create_account, AccountValidationError
from util.password_policy_validators import validate_password_strength


log = logging.getLogger(__name__)


def _validate_and_get_arguments(task_id, task_input):
    if 'contract_id' not in task_input or 'history_id' not in task_input:
        raise ValueError("Task {task_id}: Missing required value {task_input}".format(task_id=task_id, task_input=task_input))

    try:
        history_id = task_input['history_id']
        task_history = ContractTaskHistory.objects.select_related('contract__contractauth').get(pk=history_id)
    except ContractTaskHistory.DoesNotExist:
        # The ContactTaskHistory object should be committed in the view function before the task
        # is submitted and reaches this point.
        log.warning(
            "Task {task_id}: Failed to get ContractTaskHistory with id {history_id}".format(
                task_id=task_id, history_id=history_id
            )
        )
        raise

    contract_id = task_input['contract_id']
    if task_history.contract.id != task_input['contract_id']:
        _msg = "Contract id conflict: submitted value {task_history_contract_id} does not match {contract_id}".format(
            task_history_contract_id=task_history.contract.id, contract_id=contract_id
        )
        log.warning("Task {task_id}: {msg}".format(task_id=task_id, msg=_msg))
        raise ValueError(_msg)

    contract = task_history.contract
    targets = StudentRegisterTaskTarget.find_by_history_id(task_history.id)

    return (contract, targets)


def perform_delegate_student_register(entry_id, task_input, action_name):
    """
    Executes to register students. This function is called by run_main_task.
    """
    entry = Task.objects.get(pk=entry_id)
    task_id = entry.task_id

    contract, targets = _validate_and_get_arguments(task_id, task_input)
    contract_details = [{
        'key': detail.course_id,
        'mode': _default_course_mode(unicode(detail.course_id))
    } for detail in contract.details.all()]
    has_contractauth = contract.has_auth

    mail_connection = None
    if contract.can_send_mail:
        mail_connection = get_mail_connection(username=None, password=None)
        mail_connection.open()

    task_progress = TaskProgress(action_name, len(targets), time.time())
    task_progress.update_task_state()

    generated_passwords = []

    def _fail(message):
        return (message, None, None, None, None)

    def _validate_student_and_get_or_create_user(status, email, username, name, login_code=None, password=None):
        # validate status
        if status not in (INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE):
            log.error('Invalid status: {status}.'.format(status=status))
            return _fail(_("Failed to register. Please operation again after a time delay."))

        # validate email
        try:
            validate_email(email)
        except ValidationError:
            return _fail(_("Invalid email {email_address}.").format(email_address=email))

        # validate name
        name_max_length = UserProfile._meta.get_field('name').max_length
        if len(name) > name_max_length:
            return _fail(_(
                "Name cannot be more than {name_max_length} characters long"
            ).format(name_max_length=name_max_length))

        if has_contractauth:
            # validate login_code
            if not re.match(
                r'^[-\w]{{{min_length},{max_length}}}$'.format(
                    min_length=LOGIN_CODE_MIN_LENGTH,
                    max_length=LOGIN_CODE_MAX_LENGTH),
                login_code):
                return _fail(_("Invalid login code {login_code}.").format(login_code=login_code))

            # validate password
            try:
                validate_password_strength(password)
            except ValidationError:
                return _fail(_("Invalid password {password}.").format(password=password))

            # Get contract register by login code for after-validate.
            contract_register_same_login_code = ContractRegister.get_by_login_code_contract(login_code, contract)

        messages = []
        user = None
        contract_mail = None
        created_password = None
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            if user.username != username:
                messages.append(_(
                    "Warning, an account with the e-mail {email} exists but the registered username {username} is different."
                ).format(email=email, username=user.username))
                log.warning(u'email {email} already exist, but username is different.'.format(email=email))

            # Create BizUser?
            if has_contractauth:
                # validate duplicate login_code in contract
                if contract_register_same_login_code and contract_register_same_login_code.user.id != user.id:
                    return _fail(_("Login code {login_code} already exists.").format(login_code=login_code))

                biz_user, __ = BizUser.objects.get_or_create(user=user, defaults={'login_code': login_code})
                if biz_user.login_code != login_code:
                    messages.append(_(
                        "Warning, an account with the e-mail {email} exists but the registered login code {login_code} is different."
                    ).format(email=email, login_code=biz_user.login_code))
                    log.warning(u'email {email} already exist, but login code is different.'.format(email=email))

                if authenticate(username=user.username, password=password) is None:
                    messages.append(_(
                        "Warning, an account with the e-mail {email} exists but the registered password is different."
                    ).format(email=email))
                    log.warning(u'email {email} already exist, but password is different.'.format(email=email))

                contract_mail = ContractMail.get_register_existing_user_logincode(contract)
            else:
                contract_mail = ContractMail.get_register_existing_user(contract)
        else:
            # validate duplicate login_code in contract
            if login_code and contract_register_same_login_code:
                return _fail(_("Login code {login_code} already exists.").format(login_code=login_code))

            password = password or generate_unique_password(generated_passwords)
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
                user, __, registration = _do_create_account(form)
                # Do activation for new user.
                registration.activate()
                # Create BizUser?
                if has_contractauth:
                    BizUser.objects.create(user=user, login_code=login_code)
                # Optout of bulk email(Global Courses) for only new user.
                for global_course_id in CourseGlobalSetting.all_course_id():
                    Optout.objects.get_or_create(user=user, course_id=global_course_id)
            except (IntegrityError, AccountValidationError):
                return _fail(_("Username {user} already exists.").format(user=username))
            except ValidationError as ex:
                return _fail(' '.join(ex.messages))

            if has_contractauth:
                contract_mail = ContractMail.get_register_new_user_logincode(contract)
            else:
                contract_mail = ContractMail.get_register_new_user(contract)

            created_password = password

        return (
            ''.join(messages),
            user,
            contract_mail,
            ContractMail.register_replace_dict(user, contract, created_password),
            status
        )

    def _validate(student):
        student_columns = student.split(',') if student else []
        len_student_columns = len(student_columns)

        # 2 columns(status,) 1 line and second element is empty
        if len_student_columns == 2 and not student_columns[1]:
            # skip
            return (None, None, None, None, None)

        if has_contractauth and len_student_columns != 6:
            # status + 5 input columns(email,username,name,logincode,password) 1 line
            return _fail(_("Data must have exactly five columns: email, username, full name, login code and password."))
        elif not has_contractauth and len_student_columns != 4:
            # status + 3 input columns(email,username,name) 1 line
            return _fail(_("Data must have exactly three columns: email, username, and full name."))

        return _validate_student_and_get_or_create_user(*student_columns)

    for line_number, target in enumerate(targets, start=1):
        task_progress.attempt()

        try:
            with transaction.atomic():
                message, user, contract_mail, replace_dict, status = _validate(target.student)

                if user is None:
                    if message is None:
                        task_progress.skip()
                    else:
                        task_progress.fail()
                else:
                    # Create contract register if not created.
                    register, __ = ContractRegister.objects.get_or_create(user=user, contract=contract)
                    # Status is Register ?
                    if status == REGISTER_INVITATION_CODE:
                        register.status = REGISTER_INVITATION_CODE
                        register.save()

                        # Note: Perform equivalent processing to CourseEnrollment.enroll()
                        for detail in contract_details:
                            enrollment = CourseEnrollment.get_or_create_enrollment(user, detail['key'])
                            enrollment.update_enrollment(is_active=True, mode=detail['mode'])

                    if contract.can_send_mail and mail_connection:
                        mail_subject = replace_braces(contract_mail.mail_subject, replace_dict)
                        mail_body = replace_braces(contract_mail.mail_body, replace_dict)
                        django_send_mail(
                            subject=mail_subject,
                            message=mail_body,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[user.email],
                            connection=mail_connection
                        )

                    log.info("Task {task_id}: Success to process of register to User {user_id}".format(task_id=task_id, user_id=user.id))
                    task_progress.success()

                target.complete(_("Line {line_number}:{message}").format(line_number=line_number, message=message) if message else "")
        except:
            # If an exception occur, logging it and to continue processing next target.
            log.exception(u"Task {task_id}: Failed to register {student}".format(task_id=task_id, student=target.student))
            task_progress.fail()
            target.incomplete(_("Line {line_number}:{message}").format(
                line_number=line_number,
                message=_("Failed to register. Please operation again after a time delay."),
            ))

    # Close mail connection
    if contract.can_send_mail and mail_connection is not None:
        mail_connection.close()

    return task_progress.update_task_state()

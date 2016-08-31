
import logging
import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory, StudentRegisterTaskTarget
from biz.djangoapps.ga_invitation.models import ContractRegister
from bulk_email.models import Optout
from lms.djangoapps.instructor.enrollment import send_mail_to_student
from lms.djangoapps.instructor.views.api import (
    generate_unique_password, EMAIL_INDEX, NAME_INDEX, USERNAME_INDEX
)
from microsite_configuration import microsite
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress
from student.forms import AccountCreationForm
from student.models import UserProfile
from student.views import _do_create_account, AccountValidationError

log = logging.getLogger(__name__)


def _validate_and_get_arguments(task_id, task_input):
    if 'contract_id' not in task_input or 'history_id' not in task_input:
        raise ValueError("Task {task_id}: Missing required value {task_input}".format(task_id=task_id, task_input=task_input))

    try:
        history_id = task_input['history_id']
        task_history = ContractTaskHistory.objects.get(pk=history_id)
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

    task_progress = TaskProgress(action_name, len(targets), time.time())
    task_progress.update_task_state()

    generated_passwords = []

    def _validate_student_and_get_or_create_user(student):
        # 3 columns(email,username,name) 1 line
        if len(student) != 3:
            if len(student) > 0:
                return (_("Data must have exactly three columns: email, username, and full name."), None, None)
            else:
                return (None, None, None)

        email = student[EMAIL_INDEX]
        username = student[USERNAME_INDEX]
        name = student[NAME_INDEX]

        try:
            validate_email(email)
        except ValidationError:
            return (_("Invalid email {email_address}.").format(email_address=email), None, None)

        name_max_length = UserProfile._meta.get_field('name').max_length
        if len(name) > name_max_length:
            return (_(
                "Name cannot be more than {name_max_length} characters long"
            ).format(name_max_length=name_max_length), None, None)

        message = None
        user = None
        email_params = {
            'site_name': microsite.get_value('SITE_NAME', settings.SITE_NAME),
            'platform_name': microsite.get_value('platform_name', settings.PLATFORM_NAME),
            'email_address': email,
        }
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            if user.username != username:
                message = _(
                    "Warning, an account with email {email} exists but the registered username {username} is different."
                ).format(email=email, username=user.username)
                log.warning(u'email {email} already exist'.format(email=email))
    
            email_params['message'] = 'biz_account_notice'
            email_params['username'] = user.username
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
                user, __, registration = _do_create_account(form)
                # Do activation for new user.
                registration.activate()
                # Optout of bulk email(Global Courses) for only new user.
                for global_course_id in CourseGlobalSetting.all_course_id():
                    Optout.objects.get_or_create(user=user, course_id=global_course_id)
            except (IntegrityError, AccountValidationError):
                return (_("Username {user} already exists.").format(user=username), None, None)
            except ValidationError as ex:
                return (' '.join(ex.messages), None, None)

            email_params['message'] = 'biz_account_creation'
            email_params['password'] = password

        return (message, user, email_params)

    for target in targets:
        task_progress.attempt()

        try:
            with transaction.atomic():
                student = target.student.split(',') if target.student else []
                message, user, email_params = _validate_student_and_get_or_create_user(student)

                if user is None and email_params is None:
                    if message is None:
                        task_progress.skip()
                    else:
                        task_progress.fail()
                else:
                    # Create contract register if not created.
                    ContractRegister.objects.get_or_create(user=user, contract=contract)

                    send_mail_to_student(user.email, email_params)

                    log.info("Task {task_id}: Success to process of register to User {user_id}".format(task_id=task_id, user_id=user.id))
                    task_progress.success()

                target.complete(message)
        except:
            # If an exception occur, logging it and to continue processing next target.
            log.exception(u"Task {task_id}: Failed to register {student}".format(task_id=task_id, student=target.student))
            task_progress.fail()
            target.incomplete(_("Failed to register. Please operation again after a time delay."))

    return task_progress.update_task_state()

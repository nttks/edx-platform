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

from biz.djangoapps.ga_contract_operation.models import ContractMail, ContractTaskHistory, StudentMemberRegisterTaskTarget
from biz.djangoapps.ga_invitation.models import ContractRegister, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE
from biz.djangoapps.ga_login.models import BizUser, LOGIN_CODE_MIN_LENGTH, LOGIN_CODE_MAX_LENGTH
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_username_rule.models import OrgUsernameRule
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
    targets = StudentMemberRegisterTaskTarget.find_by_history_id(task_history.id)

    return (contract, targets)


def perform_delegate_student_member_register(entry_id, task_input, action_name):
    """
    Executes to register students. This function is called by run_main_task.
    """
    log.info('student member register task start')
    entry = Task.objects.get(pk=entry_id)
    task_id = entry.task_id

    contract, targets = _validate_and_get_arguments(task_id, task_input)
    contract_details = [{
        'key': detail.course_id,
        'mode': _default_course_mode(unicode(detail.course_id))
    } for detail in contract.details.all()]
    has_contractauth = contract.has_auth

    # Open mail connection
    mail_connection = None
    if contract.can_send_mail:
        mail_connection = get_mail_connection(username=None, password=None)
        mail_connection.open()

    task_progress = TaskProgress(action_name, len(targets), time.time())
    task_progress.update_task_state()

    generated_passwords = []

    def _fail(message):
        log.info(message)
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
            return _fail(_("Invalid email {email}.").format(email=email))

        # validate name
        name_max_length = UserProfile._meta.get_field('name').max_length
        if len(name) > name_max_length:
            return _fail(_(
                "Name cannot be more than {name_max_length} characters long"
            ).format(name_max_length=name_max_length))

        if has_contractauth:
            # validate login_code
            if not re.match(r'^[-\w]{{{min_length},{max_length}}}$'.format(
                    min_length=LOGIN_CODE_MIN_LENGTH, max_length=LOGIN_CODE_MAX_LENGTH), login_code):
                return _fail(_("Invalid login code {login_code}.").format(login_code=login_code))

            # validate password
            try:
                validate_password_strength(password)
            except ValidationError:
                return _fail(_("Invalid password {password}.").format(password=password))

            # Get contract register by login code for after-validate.
            contract_register_same_login_code = ContractRegister.get_by_login_code_contract(login_code, contract)

        messages = []
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
            if not OrgUsernameRule.exists_org_prefix(org=contract.contractor_organization.id, str=username):
                return _fail(_("Username {user} already exists.").format(user=username))
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

                user.first_name = name.split(' ')[0]
                try:
                    last_name = name.split(' ')[1]
                except IndexError:
                    last_name = ''
                user.last_name = last_name
                user.save()

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
        input_columns = student.split(',') if student else []
        len_student_columns = len(input_columns)

        # 2 columns(status,) 1 line and second element is empty
        if len_student_columns == 2 and not input_columns[1]:
            # skip
            return (None, None, None, None, None)
        if input_columns[3] == "" and input_columns[4] == "":
            return _fail(_("Must provide full name"))
        student_columns = input_columns[:3]
        student_columns.append(User(first_name=input_columns[3], last_name=input_columns[4]).get_full_name())

        if has_contractauth and len_student_columns != 29:
            # status + 28 input columns(email,username,name,logincode,password) and member element 1 line
            return _fail(_("Data must have exactly 28 columns: email, username, firstname, lastname, login code and password."))
        elif not has_contractauth and len_student_columns != 27:
            # status + 26 input columns(email,username,name) and member element 1 line
            return _fail(_("Data must have exactly 26 columns: email, username, firstname and lastname."))
        group_code = input_columns[5]
        member_code = input_columns[6]
        if len_student_columns == 29:
            if not input_columns[5]:
                return _fail(_("The {0} is required.").format(_("Login Code")))
            if not input_columns[6]:
                return _fail(_("The {0} is required.").format(_("Password")))
            student_columns.append(input_columns[5])
            student_columns.append(input_columns[6])
            group_code = input_columns[7]
            member_code = input_columns[8]
            for num in range(9, 19):
                if len(input_columns[num]) > 100:
                    return _fail(_("Please enter of {0} within {1} characters.").format(_("Organization"), 100))
            for num in range(19, 29):
                if len(input_columns[num]) > 100:
                    return _fail(_("Please enter of {0} within {1} characters.").format(_("Item"), 100))
        elif len_student_columns == 27:
            for num in range(7, 17):
                if len(input_columns[num]) > 100:
                    return _fail(_("Please enter of {0} within {1} characters.").format(_("Organization"), 100))
            for num in range(17, 27):
                if len(input_columns[num]) > 100:
                    return _fail(_("Please enter of {0} within {1} characters.").format(_("Item"), 100))
        if member_code:
            if not re.match(r'^[ -~]*$', member_code):
                return _fail(_("Illegal format on {0}.").format(_("Member Code")))
            email = input_columns[1]
            members = Member.find_active_by_email(org=contract.contractor_organization.id, email=email).values('code')
            code_exist = True if len(Member.find_active_by_code(
                org=contract.contractor_organization.id, code=member_code).values('id')) >= 1 else False
            if len(members) > 0:
                member = members[0]
                # Email Exist
                if member['code'] != member_code and code_exist:
                    return _fail(_("Failed member master update. Mail address, member code must unique"))
            else:
                if Member.find_delete_by_email(org=contract.contractor_organization, email=email):
                    return _fail(_("This code member deleted. Please student re-register after the unregistration"))
                elif code_exist:
                    return _fail(_("Failed member master update. Mail address, member code must unique"))
            if group_code != '' and not Group.objects.filter(group_code=group_code, org=contract.contractor_organization.id).exists():
                return _fail(_("Member registration failed. Specified Organization code does not exist"))

        return _validate_student_and_get_or_create_user(*student_columns)

    def _check_update_member(member, group_code, org_item):
        return (not member.group and group_code != '') or (
                member.group and member.group.group_code != group_code) or (
                member.org1 != org_item[0] or member.org2 != org_item[1] or
                member.org3 != org_item[2] or member.org4 != org_item[3] or
                member.org5 != org_item[4] or member.org6 != org_item[5] or
                member.org7 != org_item[6] or member.org8 != org_item[7] or
                member.org9 != org_item[8] or member.org10 != org_item[9] or
                member.item1 != org_item[10] or member.item2 != org_item[11] or
                member.item3 != org_item[12] or member.item4 != org_item[13] or
                member.item5 != org_item[14] or member.item6 != org_item[15] or
                member.item7 != org_item[16] or member.item8 != org_item[17] or
                member.item9 != org_item[18] or member.item10 != org_item[19])

    def _member_create(org, group, user, code, org_item, is_active, created_by, creator_org, updated_by, updated_org):
        Member(
            org=org, group=group, user=user, code=code,
            org1=org_item[0], org2=org_item[1], org3=org_item[2], org4=org_item[3],
            org5=org_item[4], org6=org_item[5], org7=org_item[6], org8=org_item[7],
            org9=org_item[8], org10=org_item[9], item1=org_item[10], item2=org_item[11],
            item3=org_item[12], item4=org_item[13], item5=org_item[14],
            item6=org_item[15],
            item7=org_item[16], item8=org_item[17], item9=org_item[18],
            item10=org_item[19],
            is_active=is_active,
            created_by=created_by, creator_org=creator_org,
            updated_by=updated_by, updated_org=updated_org,
        ).save()

    for line_number, target in enumerate(targets, start=1):
        log.info('student member register transaction start')
        task_progress.attempt()

        try:
            with transaction.atomic():
                message, user, contract_mail, replace_dict, status = _validate(target.student)
                error_flag = False
                if user is None:
                    if message is None:
                        task_progress.skip()
                        log.info('student member register transaction skip')
                    else:
                        task_progress.fail()
                        log.info('student member register transaction fail')
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

                    # 201805 member register
                    input_columns = target.student.split(',') if target.student else []
                    len_student_columns = len(input_columns)
                    email = input_columns[1]
                    group_code, member_code = '', ''
                    if len_student_columns == 29:
                        org_item = input_columns[9:]
                        group_code = input_columns[7]
                        member_code = input_columns[8]
                    else:
                        org_item = input_columns[7:]
                        group_code = input_columns[5]
                        member_code = input_columns[6]

                    if member_code != '':
                        org = contract.contractor_organization
                        group = Group.objects.filter(
                            org=org.id, group_code=group_code).first() if group_code != '' else None
                        member = Member.find_active_by_email(org=org.id, email=email).first()
                        code_exist = True if len(Member.find_active_by_code(
                            org=org.id, code=member_code).values('id')) else False
                        if member:
                            # If found by active member by email, then update member.
                            if member.code == member_code:
                                # Member code not changed.
                                if _check_update_member(member, group_code, org_item):
                                    Member.find_backup_by_code(org=org, code=member_code).delete()
                                    Member.change_active_to_backup_one(org=org, code=member_code)
                                    _member_create(
                                        org=org, group=group, user=register.user, code=member_code,
                                        org_item=org_item, is_active=True,
                                        created_by=member.created_by, creator_org=member.creator_org,
                                        updated_by=entry.requester, updated_org=org
                                    )

                            else:
                                # Member code changed.
                                if not code_exist:
                                    Member.find_backup_by_email(org=org, email=email).delete()
                                    Member.change_active_to_backup_one_email(org=org, email=email)
                                    _member_create(
                                        org=org, group=group, user=register.user, code=member_code,
                                        org_item=org_item, is_active=True,
                                        created_by=member.created_by, creator_org=member.creator_org,
                                        updated_by=entry.requester, updated_org=org
                                    )

                        else:
                            # If not found by active member by email, then create member.
                            if not Member.find_delete_by_email(org=org, email=email) and not code_exist:
                                _member_create(
                                    org=org, group=group, user=register.user, code=member_code,
                                    org_item=org_item, is_active=True,
                                    created_by=entry.requester, creator_org=org,
                                    updated_by=entry.requester, updated_org=org
                                )
                                _member_create(
                                    org=org, group=group, user=register.user, code=member_code,
                                    org_item=org_item, is_active=False,
                                    created_by=entry.requester, creator_org=org,
                                    updated_by=entry.requester, updated_org=org
                                )

                    if not error_flag:
                        log.info("Task {task_id}: Success to process of register to User {user_id}".format(task_id=task_id, user_id=user.id))
                        task_progress.success()
                        log.info('student member register transaction success')

                target.complete(_("Line {line_number}:{message}").format(line_number=line_number, message=message) if message else '')
                log.info('student member register transaction complete')
        except:
            # If an exception occur, logging it and to continue processing next target.
            log.exception(u"Task {task_id}: Failed to register {student}".format(task_id=task_id, student=target.student))
            task_progress.fail()
            target.incomplete(_("Line {line_number}:{message}").format(
                line_number=line_number,
                message=_("Failed to register. Please operation again after a time delay."),
            ))
            log.info('student member register transaction incomplete')

    # Close mail connection
    if contract.can_send_mail and mail_connection is not None:
        mail_connection.close()

    return task_progress.update_task_state()


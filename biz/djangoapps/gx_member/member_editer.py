# -*- coding: utf-8 -*-
import logging
import math
import time
import json
import re

from datetime import datetime
from binascii import Error

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_login.models import BizUser, LOGIN_CODE_MIN_LENGTH, LOGIN_CODE_MAX_LENGTH
from biz.djangoapps.gx_member.models import Member, MemberTaskHistory, MemberRegisterTaskTarget
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_username_rule.models import OrgUsernameRule
from biz.djangoapps.gx_sso_config.models import SsoConfig
from biz.djangoapps.gx_save_register_condition.utils import reflect_condition_execute_call_by_another_task

from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress

from student.forms import AccountCreationForm
from student.views import _do_create_account, AccountValidationError

from util.password_policy_validators import validate_password_strength

log = logging.getLogger(__name__)


def perform_delegate_member_register(entry_id, task_input, action_name):
    """
    Register a member task by file.
    1. Delete backup data
    2. Change active data to backup data
    3. Register active data

    :param entry_id:
    :param task_input:
    :param action_name:
    :return:
    """
    entry = Task.objects.get(pk=entry_id)
    task_id = entry.task_id
    task_history, targets = _validate_and_get_arguments(task_id, task_input)
    task_progress = TaskProgress(action_name, len(targets), time.time())
    task_progress.update_task_state()

    task_result = True
    error_messages = []
    line_error_message = _("Line {line_number}:{message}")
    try:
        with transaction.atomic():
            # Delete backup
            Member.delete_backup(org=task_history.organization)
            # Create backup
            Member.objects.filter(org=task_history.organization, is_active=True).update(is_active=False)
            # Active member data list to bulk create
            active_members = []
            # Backup member data list to find delete target member
            backup_members = []
            # Social auth user create data and flg
            social = SsoConfig.objects.filter(org=task_history.organization).first()

            # Create member
            for line_number, task_target in enumerate(targets, start=1):
                # Note : Task running log.
                if line_number % 1000 == 0:
                    log.info('Member editer task({0}) runing. {1} item end.'.format(
                        task_history.task_id, line_number))
                task_progress.attempt()
                target = json.loads(task_target.member)

                member_data, backup_member, error_message = _create_member(
                    target, task_history.requester, task_history.organization, social)

                if member_data:
                    task_progress.success()
                    # Set active member data to list
                    active_members.append(member_data)
                    # Set backup member data to list
                    if backup_member:
                        backup_members.append(backup_member['id'])
                else:
                    task_progress.fail()

                if error_message:
                    error_messages.append(line_error_message.format(line_number=line_number, message=error_message))

            if task_progress.failed is 0:
                delete_targets = Member.objects.filter(
                    org=task_history.organization, is_active=False, is_delete=False).exclude(
                    id__in=backup_members).values_list('id', flat=True)
                Member.objects.filter(id__in=delete_targets, is_active=False, is_delete=True).delete()
                for delete_target in Member.objects.filter(id__in=delete_targets):
                    delete_target.pk = None
                    delete_target.is_delete = True
                    delete_target.save()

                # Bulk create
                # Note: Repeat register 500, because timeout of mysql connection.
                bulk_create_max_num = 500
                for i in range(1, int(math.ceil(float(len(active_members)) / bulk_create_max_num)) + 1):
                    Member.objects.bulk_create(active_members[(i - 1) * bulk_create_max_num:i * bulk_create_max_num])
            else:
                task_result = False
                raise Error()

    except Error:
        log.warning("Task {task_id}: Failed to create member".format(task_id=task_id))

    with transaction.atomic():
        task_history.update_result(task_result, ','.join(error_messages))

    # Auto student register task.
    reflect_condition_execute_call_by_another_task(
        task_id=task_id, org=task_history.organization, user=task_history.requester,
        action_name='reflect_conditions_member_register')

    return task_progress.update_task_state()


def perform_delegate_member_register_one(entry_id, task_input, action_name):
    """
    Register a member task by form.
    1. Delete a backup data
    2. Change a active data from a backup data
    3. Register a active data

    :param entry_id:
    :param task_input:
    :param action_name:
    :return:
    """
    entry = Task.objects.get(pk=entry_id)
    task_id = entry.task_id
    task_history, targets = _validate_and_get_arguments(task_id, task_input)
    task_progress = TaskProgress(action_name, len(targets), time.time())
    task_progress.update_task_state()

    task_result = True
    error_message= ''
    try:
        with transaction.atomic():
            task_target = targets[0]
            task_progress.attempt()
            target = json.loads(task_target.member)
            # Social auth user create data and flg
            social = SsoConfig.objects.filter(org=task_history.organization).first()
            # Create backup one
            backup_members = Member.find_active_by_code(org=task_history.organization, code=target['code'])
            if len(backup_members) == 0:
                backup_members = Member.find_active_by_email(org=task_history.organization, email=target['email'])
                if len(backup_members) != 0:
                    Member.change_active_to_backup_one(org=task_history.organization, code=backup_members.first().code)
            else:
                Member.change_active_to_backup_one(org=task_history.organization, code=target['code'])

            member_data, backup_member, error_message = _create_member(
                target, task_history.requester, task_history.organization, social)

            if member_data:
                task_progress.success()
                # Create member
                member_data.save()
                # Create backup
                if not backup_member:
                    tmp_member = Member.objects.get(
                        org=task_history.organization, code=member_data.code, user_id=member_data.user_id)
                    tmp_member.pk = None
                    tmp_member.is_active = False
                    tmp_member.is_delete = False
                    tmp_member.save()
            else:
                task_progress.fail()

        if task_progress.failed != 0:
            task_result = False
            raise Error()

    except Error:
        log.warning("Task {task_id}: Failed to create member".format(task_id=task_id))

    with transaction.atomic():
        task_history.update_result(task_result, error_message)

    # Auto student register task.
    reflect_condition_execute_call_by_another_task(
        task_id=task_id, org=task_history.organization, user=task_history.requester,
        action_name='reflect_conditions_member_register')

    return task_progress.update_task_state()


def _validate_and_get_arguments(task_id, task_input):
    """
    Get task history and task targets by task input.

    :param task_id:
    :param task_input:
    :return task_history, task_targets
    """
    if 'organization_id' not in task_input or 'history_id' not in task_input:
        raise ValueError(
            "Task {task_id}: Missing required value {task_input}".format(task_id=task_id, task_input=task_input))

    try:
        history_id = task_input['history_id']
        task_history = MemberTaskHistory.objects.get(pk=history_id)
    except MemberTaskHistory.DoesNotExist:
        # The MemberTaskHistory object should be committed in the view function before the task
        # is submitted and reaches this point.
        log.warning(
            "Task {task_id}: Failed to get MemberTaskHistory with id {history_id}".format(
                task_id=task_id, history_id=history_id
            )
        )
        raise

    organization_id = task_input['organization_id']
    if int(task_history.organization.id) != organization_id:
        _msg = "Organization id conflict: submitted value {task_history_organization_id} does not match {organization_id}" \
            .format(task_history_organization_id=task_history.organization.id, organization_id=organization_id)
        log.warning("Task {task_id}: {msg}".format(task_id=task_id, msg=_msg))
        raise ValueError(_msg)

    targets = MemberRegisterTaskTarget.find_by_history_id(task_history.id)

    return task_history, targets


def _create_member(data, request_user, org, social):
    """
    Create / Update member and if target user data not found, create user.

    :param data:
    :param request_user:
    :param org:
    :return boolean, backups, error_message.
    """

    def _fail(error_message):
        return None, False, error_message

    group_id = None
    backup_member = None
    # Get group
    if data['group']:
        groups = Group.objects.filter(id=data['group']).values('id')
        if len(groups) == 1:
            group_id = groups[0]['id']
        else:
            return _fail(_("Group is not found by group code."))

    # Find backup member data
    backup_members = Member.objects.filter(
        org=org, code=data['code'], is_active=False,is_delete=False).values(
        'id', 'user__id', 'created', 'created_by_id', 'creator_org_id')
    if len(backup_members) != 0:
        # If backup member data was found, then next step.
        backup_member = backup_members[0]
        user_id = backup_member['user__id']
    else:
        # If not found backup member data, then find user data.
        users = User.objects.filter(email=data['email']).values('id', 'email')
        if len(users) != 0:
            # If user data was found, then find backup member data.
            user_id = users[0]['id']
            backup_members = Member.objects.filter(
                org=org, user__email=data['email'], is_active=False, is_delete=False).values(
                'id', 'user__id', 'created', 'created_by_id', 'creator_org_id')
            if len(backup_members) != 0:
                backup_member = backup_members[0]
        else:
            # If not found user data, then create user data.
            try:
                # Validate password
                validate_password_strength(data['password'])
            except ValidationError:
                return _fail(_("Invalid password {password}.").format(password=data['password']))
            if not OrgUsernameRule.exists_org_prefix(org=org, str=data['username']):
                return _fail(_("Username {user} already exists.").format(user=data['username']))
            try:
                # Create user
                user, __, __ = _simple_create_user(
                    data['email'], data['username'], data['password'], data['first_name'], data['last_name'])
                # Get user_id
                user_id = user.id

                # Update name of user after created user.
                user.first_name = data['first_name']
                user.last_name = data['last_name']
                user.save()

                # Create biz user when login_code is not empty.
                if data['login_code'].strip():
                    # Validate login code
                    if re.match(r'^[-\w]{{{min_length},{max_length}}}$'.format(
                            min_length=LOGIN_CODE_MIN_LENGTH, max_length=LOGIN_CODE_MAX_LENGTH), data['login_code']):
                        BizUser(user=user, login_code=data['login_code']).save()
                    else:
                        return _fail(_("Invalid login_code {login_code}.").format(login_code=data['login_code']))

            except ValidationError as e1:
                return _fail(','.join(e1.messages))

            except AccountValidationError as e2:
                return _fail(e2.message)

            except Exception as ex:
                log.error(ex.message)
                return _fail(_("Failed to create user."))

    # Delete member by code
    delete_targets = Member.objects.filter(
        org=org, code=data['code'], is_active=False, is_delete=True).values_list('id', flat=True)
    if len(delete_targets) != 0:
        Member.objects.filter(id__in=delete_targets).delete()

    # Create member
    member = Member(
        org=org,
        group_id=group_id,
        user_id=user_id,
        code=data['code'],
        org1=data['org1'], org2=data['org2'], org3=data['org3'], org4=data['org4'], org5=data['org5'],
        org6=data['org6'], org7=data['org7'], org8=data['org8'], org9=data['org9'], org10=data['org10'],
        item1=data['item1'], item2=data['item2'], item3=data['item3'], item4=data['item4'],
        item5=data['item5'], item6=data['item6'], item7=data['item7'], item8=data['item8'],
        item9=data['item9'], item10=data['item10'],
        is_active=True,
        created=backup_member['created'] if backup_member else datetime.now(),
        created_by_id=backup_member['created_by_id'] if backup_member else request_user.id,
        creator_org_id=backup_member['creator_org_id'] if backup_member else org.id,
        updated_by=request_user,
        updated_org=org
    )

    return member, backup_member, ''


def _simple_create_user(email, username, password, first_name, last_name):
    """
    Only Create user, profile, registration data and activate registration.
    :param email:
    :param username:
    :param password:
    :param first_name:
    :param last_name:
    :return: user, profile, registration
    """
    form = AccountCreationForm(
        data={
            'username': username,
            'email': email,
            'password': password,
            'name': User(first_name=first_name, last_name=last_name).get_full_name(),
        },
        tos_required=False
    )
    user, profile, registration = _do_create_account(form)
    registration.activate()
    log.debug('Create user. username={0}, email={1}, password={2}'
              .format(username, email, password))

    return user, profile, registration

# -*- coding: utf-8 -*-
"""
Test for member edit feature
"""
import ddt
import json
from mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.test.utils import override_settings

from biz.djangoapps.gx_member.models import Member, MemberTaskHistory
from biz.djangoapps.gx_member.tasks import member_register, member_register_one
from biz.djangoapps.gx_member.tests.factories import MemberTaskHistoryFactory, MemberRegisterTaskTargetFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from biz.djangoapps.gx_username_rule.tests.factories import OrgUsernameRuleFactory
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder
from biz.djangoapps.util.tests.testcase import BizViewTestBase

from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin


@ddt.ddt
class MemberEditTaskTest(BizViewTestBase, TaskTestMixin):

    def setUp(self):
        """
        Set up for test
        """
        super(MemberEditTaskTest, self).setUp()
        self.setup_user()
        self.organization = self._create_organization()
        self.test_group1 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='group_code1', group_name='test_group_name1', org=self.organization,
            created_by=self.user, modified_by=self.user)
        self.test_group2 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='group_code2', group_name='test_group_name2', org=self.organization,
            created_by=self.user, modified_by=self.user)
        self.contract = self._create_contract(
            contractor_organization=self.organization, owner_organization=self.gacco_organization,
            auto_register_students_flg=False)

        patcher = patch('biz.djangoapps.gx_member.member_editer.log')
        self.mock_log = patcher.start()
        self.addCleanup(patcher.stop)

    def _assert_failed_log(self):
        task = Task.objects.latest('id')
        self.mock_log.warning.assert_any_call("Task {task_id}: Failed to create member".format(task_id=task.task_id))

    def _create_targets(self, history, members):
        """
        Create MemberRegisterTaskTarget
        :param history: biz.djangoapps.gx_member.MemberTaskHistory
        :param members: [self._create_base_form_param()...]
        :return:
        """
        for member in members:
            MemberRegisterTaskTargetFactory.create(
                history=history, member=json.dumps(member, cls=EscapedEdxJSONEncoder))

    def _create_input_entry(self, organization=None, history=None):
        """
        Create task
        :param organization: biz.djangoapps.ga_organization.models.Organization
        :param history: biz.djangoapps.gx_member.models.MemberTaskHistory
        :return: biz.djangoapps.ga_task.models.Task
        """
        task_input = {}
        if organization is not None:
            task_input['organization_id'] = organization.id
        if history is not None:
            task_input['history_id'] = history.id
        return TaskTestMixin._create_input_entry(self, task_input=task_input)

    @staticmethod
    def _create_base_form_param(
            group=None, code='code', login_code='', email='sample@example.com',
            first_name='first_name', last_name='last_name', password='password', username='username',
            org1='', org2='', org3='', org4='', org5='', org6='', org7='', org8='', org9='', org10='',
            item1='', item2='', item3='', item4='', item5='', item6='', item7='', item8='', item9='', item10=''):
        return {
            'group': group.id if group else None,
            'group_code': group.group_code if group else None,
            'code': code,
            'login_code': login_code,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'password': password,
            'username': username,
            'org1': org1, 'org2': org2, 'org3': org3, 'org4': org4, 'org5': org5,
            'org6': org6, 'org7': org7, 'org8': org8, 'org9': org9, 'org10': org10,
            'item1': item1, 'item2': item2, 'item3': item3, 'item4': item4, 'item5': item5,
            'item6': item6, 'item7': item7, 'item8': item8, 'item9': item9, 'item10': item10
        }

    def _execute_member_register_task(self, task_fnc, members, succeeded):
        """
        Register initial data for backup data and deleted data.
        :param members: [self._create_base_form_param()...]
        :return: biz.djangoapps.gx_member.models.MemberTaskHistory
        """
        history = MemberTaskHistoryFactory.create(organization=self.organization, requester=self.user)
        self._create_targets(history=history, members=members)
        self._test_run_with_task(
            task_fnc,
            'member_register',
            task_entry=self._create_input_entry(organization=self.organization, history=history),
            expected_attempted=len(members),
            expected_num_succeeded=succeeded,
            expected_num_failed=len(members) - succeeded,
            expected_total=len(members),
        )
        return history

    def _assert_create_user_data(self, member):
        """
        Check User, UserProfile data has created
        :param member: _create_base_form_param()
        """
        member_user = User.objects.filter(email=member['email']).select_related('profile')
        self.assertEqual(1, member_user.count())
        self.assertEqual(
            User(first_name=member['first_name'], last_name=member['last_name']).get_full_name(),
            member_user.first().profile.name if hasattr(member_user.first(), 'profile') else False
        )

    def _assert_history_after_execute_task(self, history_id, result, message=None):
        """
        Check MemberTaskHistory data has updated
        :param history_id: MemberTaskHistory.id
        :param result: 0(False) or 1(True)
        :param message: str
        """
        history = MemberTaskHistory.objects.get(id=history_id)
        self.assertEqual(result, history.result)
        if message is not None:
            self.assertEqual(message, history.messages)

    def test_missing_required_input_organization(self):
        history = MemberTaskHistoryFactory.create(organization=self.organization, requester=self.user)
        entry = self._create_input_entry(history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(member_register, entry.id, entry.task_id)

        self.assertEqual("Task {}: Missing required value {}".format(
            entry.task_id, json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_missing_required_input_history(self):
        entry = self._create_input_entry(organization=self.organization)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(member_register, entry.id, entry.task_id)

        self.assertEqual("Task {}: Missing required value {}".format(
            entry.task_id, json.loads(entry.task_input)), cm.exception.message)
        self._assert_task_failure(entry.id)

    def test_not_match_input_organization(self):
        another_org = self._create_organization(org_name='another_org_name', org_code='another_org_code')
        history = MemberTaskHistoryFactory.create(organization=self.organization, requester=self.user)
        entry = self._create_input_entry(organization=another_org, history=history)

        with self.assertRaises(ValueError) as cm:
            self._run_task_with_mock_celery(member_register, entry.id, entry.task_id)

        msg = "Organization id conflict: submitted value {task_history_organization_id} " \
              "does not match {organization_id}".format(
            task_history_organization_id=history.organization.id, organization_id=another_org.id)
        self.assertEqual(msg, cm.exception.message)
        self.mock_log.warning.assert_any_call("Task {task_id}: {msg}".format(task_id=entry.task_id, msg=msg))

    def test_history_does_not_exists(self):
        history = MemberTaskHistoryFactory.create(organization=self.organization, requester=self.user)
        entry = self._create_input_entry(organization=self.organization, history=history)
        history.delete()

        with self.assertRaises(ObjectDoesNotExist):
            self._run_task_with_mock_celery(member_register, entry.id, entry.task_id)

        self._assert_task_failure(entry.id)

    @ddt.data(1, 10)
    def test_member_register_initial_register(self, test_member_num):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        members = [self._create_base_form_param(
            group=self.test_group1,
            email='sample' + str(i) + '@example.com',
            first_name='first_name' + str(i),
            last_name='last_name' + str(i),
            username='username' + str(i),
            code='code' + str(i)
        ) for i in range(test_member_num)]

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = self._execute_member_register_task(member_register, members, test_member_num)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        self._assert_history_after_execute_task(history.id, 1, '')

        # Check active member data
        self.assertEqual(
            test_member_num, Member.objects.filter(
                org=self.organization,
                group=self.test_group1,
                is_active=True,
                is_delete=False).count()
        )

        # Check user and profile data has created
        for member in members:
            self._assert_create_user_data(member)

    def test_member_register_one_initial_register(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        member = self._create_base_form_param(
            group=self.test_group1,
            code='code_one'
        )

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = self._execute_member_register_task(member_register_one, [member], 1)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        self._assert_history_after_execute_task(history.id, 1, '')

        # Check active member data
        self.assertEqual(
            1, Member.objects.filter(
                org=self.organization,
                group=self.test_group1,
                code='code_one',
                is_active=True,
                is_delete=False).count()
        )

        # Check backup member data
        self.assertEqual(
            1, Member.objects.filter(
                org=self.organization,
                group=self.test_group1,
                code='code_one',
                is_active=False,
                is_delete=False).count()
        )

        # Check user and profile data has created
        self._assert_create_user_data(member)

    def test_member_register_initial_register_with_login_code(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        member = self._create_base_form_param(
            group=self.test_group1,
            login_code='login-code'
        )

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        __ = self._execute_member_register_task(member_register, [member], 1)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check active member data
        self.assertEqual(
            1, Member.objects.filter(
                org=self.organization,
                group=self.test_group1,
                is_active=True,
                is_delete=False).count()
        )

        # Check user and profile data has created
        member_user = User.objects.filter(email=member['email']).select_related('profile', 'bizuser')
        self.assertEqual(1, member_user.count())
        self.assertTrue(hasattr(member_user.first(), 'profile'))
        self.assertEqual(
            User(first_name=member['first_name'], last_name=member['last_name']).get_full_name(),
            member_user.first().profile.name if hasattr(member_user.first(), 'profile') else False
        )
        self.assertEqual(
            member['login_code'],
            member_user.first().bizuser.login_code if hasattr(member_user.first(), 'bizuser') else ''
        )

    @ddt.data(1, 10)
    def test_member_register_backup(self, test_member_num):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        # Execute task by init data
        init_members = [self._create_base_form_param(
            group=self.test_group1,
            email='sample' + str(i) + '@example.com',
            username='username' + str(i),
            code='code' + str(i)) for i in range(test_member_num)]
        self._execute_member_register_task(member_register, init_members, len(init_members))

        # Set update column
        members = []
        org1_update_str = 'test_org1'
        first_name_no_update_str = 'test_first_name'
        for member in init_members:
            member['first_name'] = first_name_no_update_str
            member['org1'] = org1_update_str
            members.append(member)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        __ = self._execute_member_register_task(member_register, members, len(members))

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Active data
        active_members = Member.objects.filter(
            org=self.organization, group=self.test_group1, is_active=True, is_delete=False)
        self.assertEqual(len(members), active_members.count())
        for member in active_members:
            # Check user data has not updated
            self.assertNotEqual(first_name_no_update_str, member.user.first_name)
            # Check org1 has updated
            self.assertEqual(org1_update_str, member.org1)

        # Backup data
        backup_members = Member.objects.filter(org=self.organization, is_active=False, is_delete=False)
        self.assertEqual(len(init_members), backup_members.count())
        for member in backup_members:
            self.assertEqual('', member.org1)

        # Delete data
        self.assertEqual(0, Member.objects.filter(org=self.organization, is_active=False, is_delete=True).count())

    def test_member_register_one_backup(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        # Execute task by init data
        init_members = [
            self._create_base_form_param(
                group=self.test_group1,
                email='sample1@example.com',
                username='username1',
                code='code1'
            ),
            self._create_base_form_param(
                group=self.test_group1,
                email='sample2@example.com',
                username='username2',
                code='code2'
            )
        ]
        self._execute_member_register_task(member_register, init_members, len(init_members))

        # Set column for check create backup
        # Set group column
        init_members[0]['group'] = self.test_group2.id
        init_members[0]['group_code'] = self.test_group2.group_code
        # Set group column
        init_members[1]['code'] = 'new_code'

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        __ = self._execute_member_register_task(member_register_one, [init_members[0]], 1)
        __ = self._execute_member_register_task(member_register_one, [init_members[1]], 1)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check create backup by code
        self.assertEqual(1, Member.objects.filter(
            org=self.organization,
            group=self.test_group1,
            code='code1',
            is_active=False,
            is_delete=False).count())
        # Check create backup by email
        self.assertEqual(1, Member.objects.filter(
            org=self.organization,
            group=self.test_group1,
            user__email='sample2@example.com',
            code='code2',
            is_active=False,
            is_delete=False).count())

    @ddt.data(1, 10)
    def test_member_register_deleted(self, test_member_num):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        # Execute task by init data
        init_members = [self._create_base_form_param(
            group=self.test_group1,
            email='test_' + str(i) + '@example.com',
            username='username' + str(i),
            code='code' + str(i)
        ) for i in range(test_member_num)]
        self._execute_member_register_task(member_register, init_members, len(init_members))

        # Backup data
        self._execute_member_register_task(member_register, init_members, len(init_members))

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        members = [member for member in init_members]
        delete_member = members.pop()
        history = self._execute_member_register_task(member_register, members, len(members))

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        self._assert_history_after_execute_task(history.id, 1, '')

        # Active data
        active_members = Member.objects.filter(
            org=self.organization, group=self.test_group1, is_active=True)
        self.assertEqual(len(members), active_members.count())

        # Backup data
        backup_members = Member.objects.filter(org=self.organization, is_active=False, is_delete=False)
        self.assertEqual(len(init_members), backup_members.count())

        # Delete target data
        deleted_members = Member.objects.filter(org=self.organization, is_active=False, is_delete=True)
        self.assertEqual(1, deleted_members.count())
        deleted_member = deleted_members.first()
        self.assertEqual(delete_member['code'], deleted_member.code)
        self.assertEqual(delete_member['email'], deleted_member.user.email)
        self.assertEqual(delete_member['username'], deleted_member.user.username)

    @ddt.data(1, 10)
    def test_member_register_delete_active_code(self, test_member_num):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        # Execute task by init data
        init_members = [
            self._create_base_form_param(
                group=self.test_group1,
                email='test_' + str(i) + '@example.com',
                username='username' + str(i),
                code='code' + str(i)
            ) for i in range(test_member_num)
        ]
        self._execute_member_register_task(member_register, init_members, len(init_members))

        # Backup data
        self._execute_member_register_task(member_register, init_members, len(init_members))

        # Delete data
        delete_member = init_members.pop()
        self._execute_member_register_task(member_register, init_members, len(init_members))
        # Check delete target data has created
        self.assertEqual(1, Member.objects.filter(
            org=self.organization,
            code=delete_member['code'],
            is_active=False,
            is_delete=True).count()
                         )
        # Set renew code
        init_members.append(self._create_base_form_param(
            group=self.test_group1,
            email='email_renew_code@example.com',
            username='username_renew_code',
            code=delete_member['code'])
        )

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        __ = self._execute_member_register_task(member_register, init_members, len(init_members))

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check delete target data is not found
        self.assertEqual(0, Member.objects.filter(
            org=self.organization,
            code=delete_member['code'],
            is_active=False,
            is_delete=True).count()
                         )

    @ddt.data(member_register, member_register_one)
    def test_member_register_validate_error_group_not_found(self, task_fnc):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        member = self._create_base_form_param(
            group=self.test_group1
        )
        member['group'] = 1234
        member['group_code'] = 'not_exist_group_code'

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = self._execute_member_register_task(task_fnc, [member], 0)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        if task_fnc is member_register:
            self._assert_history_after_execute_task(history.id, 0, "Line {line_number}:{message}".format(
                line_number=1, message="Group is not found by group code."))
        elif task_fnc is member_register_one:
            self._assert_history_after_execute_task(history.id, 0, "Group is not found by group code.")
        # Check data has not created
        self.assertEqual(0, Member.objects.filter(org=self.organization).count())
        self.assertEqual(0, User.objects.filter(email=member['email']).count())
        self._assert_failed_log()

    @ddt.unpack
    @ddt.data(
        (member_register, 't'),
        (member_register_one, 't'),
        (member_register, 'Test@Student_1'),
        (member_register_one, 'Test@Student_1'),
        (member_register, 'Test_Student_1Test_Student_1Test_Student_1'),
        (member_register_one, 'Test_Student_1Test_Student_1Test_Student_1'),
    )
    def test_member_register_validate_error_login_code(self, task_fnc, login_code):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        member = self._create_base_form_param(login_code=login_code)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = self._execute_member_register_task(task_fnc, [member], 0)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        if task_fnc is member_register:
            self._assert_history_after_execute_task(history.id, 0, "Line {line_number}:{message}".format(
                line_number=1, message="Invalid login_code {login_code}.".format(login_code=login_code)))
        elif task_fnc is member_register_one:
            self._assert_history_after_execute_task(
                history.id, 0, "Invalid login_code {login_code}.".format(login_code=login_code))

        self._assert_failed_log()

    @override_settings(
        PASSWORD_MIN_LENGTH=7,
        PASSWORD_COMPLEXITY={
            'DIGITS': 1,
            'LOWER': 1,
            'UPPER': 1,
        }
    )
    @ddt.unpack
    @ddt.data(
        (member_register, ''),
        (member_register_one, ''),
        (member_register, 'abAB12'),
        (member_register_one, 'abAB12'),
        (member_register, 'abcdABCD'),
        (member_register_one, 'abcdABCD'),
        (member_register, 'abcd1234'),
        (member_register_one, 'abcd1234'),
        (member_register, 'ABCD1234'),
        (member_register_one, 'ABCD1234')
    )
    def test_member_register_validate_error_password(self, task_fnc, password):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        member = self._create_base_form_param(password=password)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = self._execute_member_register_task(task_fnc, [member], 0)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        if task_fnc is member_register:
            self._assert_history_after_execute_task(history.id, 0, "Line {line_number}:{message}".format(
                line_number=1, message="Invalid password {password}.".format(password=password)))
        elif task_fnc is member_register_one:
            self._assert_history_after_execute_task(
                history.id, 0, "Invalid password {password}.".format(password=password))

        self._assert_failed_log()

    @ddt.unpack
    @ddt.data(
        (member_register, 't'),
        (member_register_one, 't'),
        (member_register, 'test@user_name'),
        (member_register_one, 'test@user_name'),
        (member_register, 'test_user_name_test_user_name_test_user_name'),
        (member_register_one, 'test_user_name_test_user_name_test_user_name')
    )
    def test_member_register_validate_error_username(self, task_fnc, username):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        member = self._create_base_form_param(username=username)

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = self._execute_member_register_task(task_fnc, [member], 0)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        self._assert_history_after_execute_task(history.id, 0)

        # Check data has not created
        self.assertEqual(0, Member.objects.filter(org=self.organization).count())
        self.assertEqual(0, User.objects.filter(username=username).count())
        self._assert_failed_log()

    def test_member_register_validate_error_username_overlap(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        members = [
            self._create_base_form_param(
                email='overlap1@example.com',
                code='code1',
                username='overlap'
            ),
            self._create_base_form_param(
                email='overlap2@example.com',
                code='code2',
                username='overlap'
            )
        ]

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = self._execute_member_register_task(member_register, members, 1)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        history_message = "Line {line_number}:{message}".format(
            line_number=2,
            message="An account with the Public Username '{username}' already exists.".format(username='overlap'))
        self._assert_history_after_execute_task(history.id, 0, history_message)

        # Check data has not created
        self.assertEqual(0, Member.objects.filter(org=self.organization).count())
        self.assertEqual(0, User.objects.filter(email='overlap@example.com').count())
        self._assert_failed_log()

    def test_member_register_integrity_error_create_user(self):
        # ----------------------------------------------------------
        # Setup test data
        # ----------------------------------------------------------
        members = [self._create_base_form_param(username='username_integrity_error')]

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = MemberTaskHistoryFactory.create(organization=self.organization, requester=self.user)
        self._create_targets(history=history, members=members)
        with patch('biz.djangoapps.gx_member.member_editer._simple_create_user',
                   side_effect=IntegrityError('sample_error_message')):
            self._test_run_with_task(
                member_register,
                'member_register',
                task_entry=self._create_input_entry(organization=self.organization, history=history),
                expected_attempted=len(members),
                expected_num_failed=1,
                expected_total=len(members),
            )

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        self._assert_history_after_execute_task(
            history.id, 0, "Line {line_number}:{message}".format(line_number=1, message="Failed to create user."))
        # Check data has not created
        self.assertEqual(0, Member.objects.filter(org=self.organization).count())
        self.assertEqual(0, User.objects.filter(username='username_integrity_error').count())
        self.mock_log.error.assert_any_call('sample_error_message')
        self._assert_failed_log()

    def test_current_org_username_rule_true(self):

        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=self.organization)

        members = [
            self._create_base_form_param(
                email='rule1@example.com',
                code='code1',
                username='abc__123'
            ),
            self._create_base_form_param(
                email='rule4@example.com',
                code='code4',
                username='abc__456'
            )
        ]

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = self._execute_member_register_task(member_register, members, 2)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check data has not created
        self.assertEqual(2, Member.objects.filter(org=self.organization).count())
        self.assertEqual(1, User.objects.filter(email='rule1@example.com').count())

    def test_current_org_username_rule_false(self):

        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=self.organization)

        members = [
            self._create_base_form_param(
                email='rule1@example.com',
                code='code1',
                username='abc__123'
            ),
            self._create_base_form_param(
                email='rule2@example.com',
                code='code2',
                username='xabc__123'
            ),
            self._create_base_form_param(
                email='rule3@example.com',
                code='code3',
                username='abc123'
            ),
            self._create_base_form_param(
                email='rule4@example.com',
                code='code4',
                username='abc__456'
            )
        ]

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = self._execute_member_register_task(member_register, members, 2)

        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        history_message = []
        history_message.append("Line {line_number}:{message}".format(
            line_number=2,
            message="Username {username} already exists.".format(username='xabc__123')))
        history_message.append("Line {line_number}:{message}".format(
            line_number=3,
            message="Username {username} already exists.".format(username='abc123')))
        self._assert_history_after_execute_task(history.id, 0, ','.join(history_message))

        # Check data has not created
        self.assertEqual(0, Member.objects.filter(org=self.organization).count())
        self.assertEqual(0, User.objects.filter(email='rule1@example.com').count())
        self._assert_failed_log()

    def test_another_org_username_rule_true(self):
        another_org1 = self._create_organization(org_name='another_rule_org_name', org_code='another_rule_org_code')
        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=self.organization)

        username_rule2 = OrgUsernameRuleFactory.create(prefix='xabc__', org=another_org1)


        members1 = [
            self._create_base_form_param(
                email='rule1@example.com',
                code='code1',
                username='abc__123'
            ),
            self._create_base_form_param(
                email='rule2@example.com',
                code='code2',
                username='abc__456'
            )
        ]
        members2 = [
            self._create_base_form_param(
                email='rule3@example.com',
                code='code3',
                username='xabc__123'
            ),
            self._create_base_form_param(
                email='rule4@example.com',
                code='code4',
                username='xabc__456'
            )
        ]

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = self._execute_member_register_task(member_register, members1, 2)
        history = MemberTaskHistoryFactory.create(organization=another_org1, requester=self.user)
        self._create_targets(history=history, members=members2)
        self._test_run_with_task(
            member_register,
            'member_register',
            task_entry=self._create_input_entry(organization=another_org1, history=history),
            expected_attempted=len(members2),
            expected_num_succeeded=2,
            expected_num_failed=len(members2) - 2,
            expected_total=len(members2),
        )
        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check data has not created
        self.assertEqual(2, Member.objects.filter(org=another_org1).count())
        self.assertEqual(1, User.objects.filter(email='rule1@example.com').count())

    def test_another_org_username_rule_false(self):
        another_org1 = self._create_organization(org_name='other_rule_org_name', org_code='other_rule_org_code')
        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=self.organization)

        username_rule2 = OrgUsernameRuleFactory.create(prefix='cde__', org=another_org1)


        members = [
            self._create_base_form_param(
                email='rule1@example.com',
                code='code1',
                username='cde__123'
            ),
            self._create_base_form_param(
                email='rule2@example.com',
                code='code2',
                username='abc__123'
            ),
        ]
        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = MemberTaskHistoryFactory.create(organization=another_org1, requester=self.user)
        self._create_targets(history=history, members=members)
        self._test_run_with_task(
            member_register,
            'member_register',
            task_entry=self._create_input_entry(organization=another_org1, history=history),
            expected_attempted=len(members),
            expected_num_succeeded=1,
            expected_num_failed=len(members) - 1,
            expected_total=len(members),
        )
        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        history_message = "Line {line_number}:{message}".format(
            line_number=2,
            message="Username {username} already exists.".format(username='abc__123'))
        self._assert_history_after_execute_task(history.id, 0, history_message)

        # Check data has not created
        self.assertEqual(0, Member.objects.filter(org=another_org1).count())
        self.assertEqual(0, User.objects.filter(email='rule1@example.com').count())
        self._assert_failed_log()

    def test_another_org_not_username_rule_true(self):
        another_org1 = self._create_organization(org_name='another_rule_org_name', org_code='another_rule_org_code')
        another_org2 = self._create_organization(org_name='not_rule_org_name', org_code='not_rule_org_code')
        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=self.organization)

        username_rule2 = OrgUsernameRuleFactory.create(prefix='cde__', org=another_org1)


        members = [
            self._create_base_form_param(
                email='rule1@example.com',
                code='code1',
                username='abc_123'
            ),
            self._create_base_form_param(
                email='rule2@example.com',
                code='code2',
                username='cde_123'
            ),
            self._create_base_form_param(
                email='rule3@example.com',
                code='code3',
                username='xabc__123'
            ),
            self._create_base_form_param(
                email='rule4@example.com',
                code='code4',
                username='cde123'
            )
        ]

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = MemberTaskHistoryFactory.create(organization=another_org2, requester=self.user)
        self._create_targets(history=history, members=members)
        self._test_run_with_task(
            member_register,
            'member_register',
            task_entry=self._create_input_entry(organization=another_org2, history=history),
            expected_attempted=len(members),
            expected_num_succeeded=4,
            expected_num_failed=len(members) - 4,
            expected_total=len(members),
        )
        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check data has not created
        self.assertEqual(4, Member.objects.filter(org=another_org2).count())
        self.assertEqual(1, User.objects.filter(email='rule1@example.com').count())

    def test_another_org_not_username_rule_false(self):
        another_org1 = self._create_organization(org_name='another_rule_org_name', org_code='another_rule_org_code')
        another_org2 = self._create_organization(org_name='not_rule_org_name', org_code='not_rule_org_code')
        username_rule = OrgUsernameRuleFactory.create(prefix='abc__', org=self.organization)

        username_rule2 = OrgUsernameRuleFactory.create(prefix='cde__', org=another_org1)


        members = [
            self._create_base_form_param(
                email='rule1@example.com',
                code='code1',
                username='abc__123'
            ),
            self._create_base_form_param(
                email='rule2@example.com',
                code='code2',
                username='cde__123'
            ),
            self._create_base_form_param(
                email='rule3@example.com',
                code='code3',
                username='abc_123'
            ),
            self._create_base_form_param(
                email='rule4@example.com',
                code='code4',
                username='cde___123'
            )
        ]

        # ----------------------------------------------------------
        # Execute task
        # ----------------------------------------------------------
        history = MemberTaskHistoryFactory.create(organization=another_org2, requester=self.user)
        self._create_targets(history=history, members=members)
        self._test_run_with_task(
            member_register,
            'member_register',
            task_entry=self._create_input_entry(organization=another_org2, history=history),
            expected_attempted=len(members),
            expected_num_succeeded=1,
            expected_num_failed=len(members) - 1,
            expected_total=len(members),
        )
        # ----------------------------------------------------------
        # Assertion
        # ----------------------------------------------------------
        # Check history column
        history_message = []
        history_message.append("Line {line_number}:{message}".format(
            line_number=1,
            message="Username {username} already exists.".format(username='abc__123')))
        history_message.append("Line {line_number}:{message}".format(
            line_number=2,
            message="Username {username} already exists.".format(username='cde__123')))
        history_message.append("Line {line_number}:{message}".format(
            line_number=4,
            message="Username {username} already exists.".format(username='cde___123')))
        self._assert_history_after_execute_task(history.id, 0, ','.join(history_message))

        # Check data has not created
        self.assertEqual(0, Member.objects.filter(org=another_org2).count())
        self.assertEqual(0, User.objects.filter(email='rule1@example.com').count())
        self._assert_failed_log()

    def test_reflect_condition_execute_call_by_another_task(self):
        """ Note: Detail test is written to 'gx_save_register_condition/tests/test_utils.py'."""
        pass

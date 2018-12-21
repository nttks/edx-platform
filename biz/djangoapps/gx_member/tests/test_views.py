# -*- coding: utf-8 -*-
"""
Test for member feature
"""
import hashlib
import json
import ddt
import pytz
from mock import patch
from datetime import datetime, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from biz.djangoapps.ga_login.models import BizUser, LOGIN_CODE_MIN_LENGTH
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.gx_member.builders import MemberTsv
from biz.djangoapps.gx_member.models import Member, MemberTaskHistory, MemberRegisterTaskTarget
from biz.djangoapps.gx_member.tasks import MEMBER_REGISTER, TASKS
from biz.djangoapps.gx_member.tests.factories import MemberFactory, MemberTaskHistoryFactory
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from biz.djangoapps.util.tests.testcase import BizViewTestBase

from openedx.core.djangoapps.ga_task.tests.factories import TaskFactory
from openedx.core.lib.ga_datetime_utils import to_timezone
from student.tests.factories import UserFactory


@ddt.ddt
class MemberViewTest(BizViewTestBase):

    def setUp(self):
        """
        Set up for test
        """
        super(MemberViewTest, self).setUp()
        self.file_delimiter = "\t"
        self.file_quotechar = "'"
        self.setup_user()

        self.organization = self.gacco_organization
        self.test_default_group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='group_code', group_name='test_group_name', org=self.organization,
            created_by=self.user, modified_by=self.user)

        self._director_manager = self._create_manager(
            org=self.organization,
            user=self.user,
            created=self.organization,
            permissions=[self.director_permission]
        )

    @property
    def _url_index(self):
        return reverse("biz:member:index")

    @property
    def _url_register_ajax(self):
        return reverse("biz:member:register_ajax")

    @property
    def _url_register_csv_ajax(self):
        return reverse("biz:member:register_csv_ajax")

    @property
    def _url_download_ajax(self):
        return reverse("biz:member:download_ajax")

    @property
    def _url_task_history_ajax(self):
        return reverse("biz:member:task_history_ajax")

    def _create_member(
            self, org, group, user, code, is_active, is_delete,
            org1='', org2='', org3='', org4='', org5='', org6='', org7='', org8='', org9='', org10='',
            item1='', item2='', item3='', item4='', item5='', item6='', item7='', item8='', item9='', item10=''):
        return MemberFactory.create(
            org=org,
            group=group,
            user=user,
            code=code,
            created_by=user,
            creator_org=org,
            updated_by=user,
            updated_org=org,
            is_active=is_active,
            is_delete=is_delete,
            org1=org1, org2=org2, org3=org3, org4=org4, org5=org5, org6=org6, org7=org7, org8=org8, org9=org9,
            org10=org10,
            item1=item1, item2=item2, item3=item3, item4=item4, item5=item5, item6=item6, item7=item7, item8=item8,
            item9=item9, item10=item10
        )

    def _create_base_form_param(
            self, group=None, group_code='', code='code', login_code='', email='sample@example.com',
            first_name='first_name', last_name='last_name', password='password', username='username',
            org1='', org2='', org3='', org4='', org5='', org6='', org7='', org8='', org9='', org10='',
            item1='', item2='', item3='', item4='', item5='', item6='', item7='', item8='', item9='', item10=''):
        return {
            'group': group,
            'group_code': group_code,
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

    def _create_content_uploaded_file(self, org):
        content = ""
        tsv = MemberTsv(org)
        # set header
        header_columns = tsv.headers_for_export
        for i, column in enumerate(header_columns, start=1):
            content += "'" + column + "'" + ("\t" if i != len(header_columns) else "")
        # set record
        records = tsv.get_rows_for_export()
        for i, record in enumerate(records, start=1):
            content += "\n"
            for j, column in enumerate(record, start=1):
                content += "'" + (column if column else "") + "'" + ("\t" if j != len(record) else "")

        return content

    def _create_uploaded_file(self, org, content=None):
        if content is None:
            content = self._create_content_uploaded_file(org)
        return SimpleUploadedFile('sample.csv', content.encode('utf-16'), content_type='multipart/form-data')

    def _create_task(self, task_type, task_key, task_id, task_state, total=0, attempted=0, succeeded=0, skipped=0,
                     failed=0):
        task_output = json.dumps({
            'total': total,
            'attempted': attempted,
            'succeeded': succeeded,
            'skipped': skipped,
            'failed': failed,
        })
        return TaskFactory.create(
            task_type=task_type, task_key=task_key, task_id=task_id, task_state=task_state, task_output=task_output
        )

    def _assert_task_history(self, history, recid, result, messages, requester, created, updated,
                             total=0, succeeded=0, skipped=0, failed=0):
        self.assertEqual(history['recid'], recid)
        if result is 'progress':
            self.assertEqual(history['result'], 'Processing of Member Register is running.')
            self.assertEqual(history['result_message'], 'Task is being executed. Please wait a moment.')
        else:
            self.assertEqual(history['result'], result)
            self.assertEqual(history['result_message'],
                             "Total: {}, Success: {}, Skipped: {}, Failed: {}".format(total, succeeded, skipped,
                                                                                      failed))
        self.assertEqual(history['messages'], messages)
        self.assertEqual(history['requester'], requester)
        self.assertEqual(history['created'], to_timezone(created).strftime('%Y/%m/%d %H:%M:%S'))
        self.assertEqual(history['updated'], to_timezone(updated).strftime('%Y/%m/%d %H:%M:%S'))

    def test_index(self):
        # Request
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.get(self._url_index)

        # Assertion
        self.assertEqual(200, response.status_code)

    def test_register_ajax(self):
        # create ajax param
        param = self._create_base_form_param(
            group=self.test_default_group.id,
            group_code=self.test_default_group.group_code
        )
        for i in range(1, 11):
            param['org' + str(i)] = '0001_org' + str(i)
            param['item' + str(i)] = '0001_item' + str(i)

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)

        # Assertion
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['info'],
            "Began the processing of Member Register.Execution status, please check from the task history."
        )

        task_history = MemberTaskHistory.objects.get(organization=self.organization, requester=self.user)
        task_target = MemberRegisterTaskTarget.objects.get(history=task_history)
        task_target_member = dict(json.loads(task_target.member))
        for key in param:
            self.assertEqual(param[key], task_target_member[key])

    def test_register_ajax_validate_error(self):
        # Set
        Group(parent_id=0, level_no=0, group_code='group_code', group_name='test_group_name',
              org=self.organization, created_by=self.user, modified_by=self.user).save()

        def _create_over_length_string(max_length):
            return ''.join(map(str, [num for num in range(max_length + 1)]))

        # ------------------------------------------------------------------------------------------
        # Group Code
        # ------------------------------------------------------------------------------------------
        # Set over max number
        group_code_max_length = Group._meta.get_field('group_code').max_length
        param = self._create_base_form_param(group_code=_create_over_length_string(group_code_max_length))
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Please enter of {0} within {1} characters.".format("Organization", group_code_max_length)
        )

        # Set not found group
        param = self._create_base_form_param(group_code='no_exist_group_code')
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'][0], "Organization Groups is not found by organization.")

        # ------------------------------------------------------------------------------------------
        # Member Code
        # ------------------------------------------------------------------------------------------
        # Set required
        param = self._create_base_form_param(code='')
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'][0], "The {0} is required.".format("Member Code"))

        # Set over max number
        code_max_length = Member._meta.get_field('code').max_length
        param = self._create_base_form_param(code=_create_over_length_string(code_max_length))
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Please enter of {0} within {1} characters.".format("Member Code", code_max_length)
        )

        # ------------------------------------------------------------------------------------------
        # First Name
        # ------------------------------------------------------------------------------------------
        # Over max number
        # Set over max number
        first_name_max_length = User._meta.get_field('first_name').max_length
        param = self._create_base_form_param(first_name=_create_over_length_string(first_name_max_length))
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Please enter of {0} within {1} characters.".format("First Name", first_name_max_length)
        )

        # ------------------------------------------------------------------------------------------
        # Last Name
        # ------------------------------------------------------------------------------------------
        # Set over max number
        last_name_max_length = User._meta.get_field('last_name').max_length
        param = self._create_base_form_param(last_name=_create_over_length_string(last_name_max_length))
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Please enter of {0} within {1} characters.".format("Last Name", last_name_max_length)
        )

        # ------------------------------------------------------------------------------------------
        # Password
        # ------------------------------------------------------------------------------------------
        # Set over max number
        password_max_length = User._meta.get_field('password').max_length
        param = self._create_base_form_param(password=_create_over_length_string(password_max_length))
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)

        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Please enter of {0} within {1} characters.".format("Password", password_max_length)
        )

        # ------------------------------------------------------------------------------------------
        # Username
        # ------------------------------------------------------------------------------------------
        # Set required
        param = self._create_base_form_param(username='')
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'][0], "The {0} is required.".format("Username"))

        # Set over max number
        username_max_length = User._meta.get_field('username').max_length
        param = self._create_base_form_param(username=_create_over_length_string(username_max_length))
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Please enter of {0} within {1} characters.".format("Username", username_max_length)
        )

        # ------------------------------------------------------------------------------------------
        # Email
        # ------------------------------------------------------------------------------------------
        # Set required
        param = self._create_base_form_param(email='')
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'][0], "The {0} is required.".format("Email Address"))

        # Set invalid format
        param = self._create_base_form_param(email='invalid_email')
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'][0], "Illegal format on {0}.".format("Email Address"))

        # ------------------------------------------------------------------------------------------
        # Login Code
        # ------------------------------------------------------------------------------------------
        # Set less min number
        param = self._create_base_form_param(login_code='t')
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Please enter of {0} within {1} characters.".format("Login Code", LOGIN_CODE_MIN_LENGTH)
        )
        # Set over max number
        login_code_max_length = BizUser._meta.get_field('login_code').max_length
        param = self._create_base_form_param(login_code=_create_over_length_string(login_code_max_length))
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Please enter of {0} within {1} characters.".format("Login Code", login_code_max_length)
        )
        # Set invalid format
        param = self._create_base_form_param(login_code='Test@Student_1')
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'][0], "Illegal format on {0}.".format("Login Code"))

        # ------------------------------------------------------------------------------------------
        # Organization 1-10, Item1-10
        # ------------------------------------------------------------------------------------------
        org_item_max_length = Member._meta.get_field('org1').max_length
        for i in range(1, 11):
            # Set organization1-10
            param = self._create_base_form_param()
            param['org' + str(i)] = _create_over_length_string(org_item_max_length)
            # Post
            with self.skip_check_course_selection(
                    current_organization=self.organization, current_manager=self._director_manager):
                response = self.client.post(self._url_register_ajax, param)

            self.assertEqual(400, response.status_code)
            data = json.loads(response.content)
            self.assertEqual(
                data['error'][0],
                "Please enter of {0} within {1} characters.".format("Organization " + str(i), org_item_max_length)
            )

            # Set item1-10
            param = self._create_base_form_param()
            param['item' + str(i)] = _create_over_length_string(org_item_max_length)
            # Post
            with self.skip_check_course_selection(
                    current_organization=self.organization, current_manager=self._director_manager):
                response = self.client.post(self._url_register_ajax, param)
            # Assertion
            self.assertEqual(400, response.status_code)
            data = json.loads(response.content)
            self.assertEqual(
                data['error'][0],
                "Please enter of {0} within {1} characters.".format("Item " + str(i), org_item_max_length)
            )

        # ------------------------------------------------------------------------------------------
        # Error Multi Column
        # ------------------------------------------------------------------------------------------
        # Set
        param = self._create_base_form_param(
            first_name=_create_over_length_string(first_name_max_length),
            password=_create_over_length_string(password_max_length))
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)
        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'],
            ["Please enter of {0} within {1} characters.".format("First Name", first_name_max_length),
             "Please enter of {0} within {1} characters.".format("Password", password_max_length)]
        )

    @ddt.data(1, 10)
    def test_download_ajax(self, test_member_num):
        # Set test data
        another_org = self._create_organization(org_name='another_org_name', org_code='another_org_code')

        for i in range(test_member_num):
            # Active data
            active_user = UserFactory.create()
            member = self._create_member(
                org=self.organization, group=self.test_default_group, user=active_user,
                code="code_" + str(i), is_active=True, is_delete=False
            )
            BizUserFactory.create(user=active_user, login_code='login-code' + str(i))
            # Backup data
            self._create_member(
                org=self.organization, group=self.test_default_group, user=member.user,
                code="code_" + str(i) + "_backup", is_active=False, is_delete=False
            )
            # Delete data
            self._create_member(
                org=self.organization, group=self.test_default_group, user=UserFactory.create(),
                code='code_' + str(i) + "_delete", is_active=False, is_delete=True
            )
            # Another organization data
            self._create_member(
                org=another_org, group=self.test_default_group, user=UserFactory.create(),
                code="code_" + str(i), is_active=True, is_delete=False
            )

        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_download_ajax, {'organization': self.organization.id})

        # Assertion
        self.assertEqual(200, response.status_code)

        tmp_utf8_str = response.content.decode('utf-16').replace(self.file_quotechar, '')
        lines = tmp_utf8_str.splitlines()
        # header(index 0) pop
        lines.pop(0)
        # Check count member num
        self.assertTrue(len(lines) == Member.objects.filter(
            org=self.organization, is_active=True, is_delete=False).count())

        tsv = MemberTsv(self.organization)
        for line in lines:
            member = tsv.get_dic_by_import_row(line.split(self.file_delimiter))
            # Check member data has created
            member_counter = Member.objects.filter(
                org=self.organization,
                code=member['code'],
                group__group_code=member['group_code'],
                user__email=member['email'],
                user__first_name=member['first_name'],
                user__last_name=member['last_name'],
                user__username=member['username'],
                org1=member['org1'], org2=member['org2'], org3=member['org3'], org4=member['org4'],
                org5=member['org5'], org6=member['org6'], org7=member['org7'], org8=member['org8'],
                org9=member['org9'], org10=member['org10'],
                item1=member['item1'], item2=member['item2'], item3=member['item3'], item4=member['item4'],
                item5=member['item5'], item6=member['item6'], item7=member['item7'], item8=member['item8'],
                item9=member['item9'], item10=member['item10'],
                is_active=True,
                is_delete=False
            )
            if member['login_code']:
                member_counter.filter(user__bizuser__login_code=member['login_code'])
            self.assertEqual(1, member_counter.count())

    def test_download_ajax_validate_authorized_error(self):
        # Post
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_download_ajax, {})

        # Assertion
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    @ddt.data(1, 10)
    def test_register_csv_ajax(self, test_member_num):
        # Create member (and backup member data)
        for i in range(test_member_num):
            member = self._create_member(
                org=self.organization, group=self.test_default_group, user=UserFactory.create(),
                code="code_" + str(i), is_active=True, is_delete=False
            )
            self._create_member(
                org=self.organization, group=self.test_default_group, user=member.user,
                code="code_" + str(i) + "_backup", is_active=False, is_delete=False
            )

        param = {
            'organization': self.organization.id,
            'member_csv': self._create_uploaded_file(org=self.organization)
        }

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['info'],
            "Began the processing of Member Register.Execution status, please check from the task history."
        )

    @ddt.data(
        {},
        {'member_csv': SimpleUploadedFile('sample.csv', "test", content_type='multipart/form-data')},
        {'organization': 'xxx'}
    )
    def test_register_csv_ajax_validate_authority_error(self, param):
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_register_csv_ajax_validate_error_file_content_empty(self):
        director_manager = self._director_manager

        param = {
            'organization': self.organization.id,
            'member_csv': self._create_uploaded_file(self.organization, "")
        }

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "The file is empty.")

    def test_register_csv_ajax_validate_error_file_content_not_unicode(self):
        # Create member
        self._create_member(
            org=self.organization, group=self.test_default_group, user=UserFactory.create(),
            code="code", is_active=True, is_delete=False
        )

        param = {
            'organization': self.organization.id,
            'member_csv': SimpleUploadedFile(
                'sample.csv',
                self._create_content_uploaded_file(org=self.organization).encode('utf-8'),
                content_type='multipart/form-data'
            )
        }

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "invalid header or file type")

    def test_register_csv_ajax_validate_error(self):
        # This case test only simple pattern, because this case is same as 'self.test_register_ajax_validate_error'
        # Create member
        self._create_member(
            org=self.organization, group=self.test_default_group, user=UserFactory.create(),
            code="code_validate_error", is_active=True, is_delete=False
        )
        # Set empty to member code
        content = self._create_content_uploaded_file(org=self.organization)
        content = content.replace("code_validate_error", "")

        param = {
            'organization': self.organization.id,
            'member_csv': self._create_uploaded_file(org=self.organization, content=content)
        }

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], ["Line {line_number}:{message}".format(
            line_number=1, message="The {0} is required.".format("Member Code"))])

    def test_register_csv_ajax_validate_error_not_match_header(self):
        param = {
            'organization': self.organization.id,
            'member_csv': SimpleUploadedFile(
                'sample.csv',
                "\'Sample1\'\t\'Sample2\'\t\'Sample3\'\t\'Sample4\'\t".encode('utf-16'),
                content_type='multipart/form-data'
            )
        }

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "invalid header or file type")

    def test_register_csv_ajax_validate_error_not_match_column_number(self):
        self._create_member(
            org=self.organization, group=self.test_default_group, user=UserFactory.create(),
            code="code", is_active=True, is_delete=False
        )

        # Create file content
        content = ""
        tsv = MemberTsv(self.organization)
        header_columns = tsv.headers_for_export
        for i, column in enumerate(header_columns, start=1):
            content += "'" + column + "'" + ("\t" if i != len(header_columns) else "")

        records = tsv.get_rows_for_export()
        for i, record in enumerate(records, start=1):
            content += "\n"
            for j, column in enumerate(record, start=1):
                content += "'" + (column if column else "") + "'" + ("\t" if j != len(record) else "")

        content += "\t'add_over_column'"

        param = {
            'organization': self.organization.id,
            'member_csv': self._create_uploaded_file(self.organization, content)
        }

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], ["Line {line_number}:{message}".format(
            line_number=1, message="The number of columns did not match.")])

    def test_register_csv_ajax_validate_error_email_overlap(self):
        member_user1 = UserFactory.create()
        # Create member
        self._create_member(
            org=self.organization, group=self.test_default_group, user=member_user1,
            code="code", is_active=True, is_delete=False
        )
        member_user2 = UserFactory.create()
        self._create_member(
            org=self.organization, group=self.test_default_group, user=member_user2,
            code="code", is_active=True, is_delete=False
        )
        # Create file content(set row of same email)
        content = self._create_content_uploaded_file(self.organization)
        content = content.replace(member_user2.email, member_user1.email)

        param = {
            'organization': self.organization.id,
            'member_csv': self._create_uploaded_file(self.organization, content)
        }

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Line {line_number}:{message}".format(line_number=2, message="Email is already used in file.")
        )

    def test_register_csv_ajax_validate_error_username_overlap(self):
        member_user1 = UserFactory.create()
        # Create member
        self._create_member(
            org=self.organization, group=self.test_default_group, user=member_user1,
            code="code", is_active=True, is_delete=False
        )
        member_user2 = UserFactory.create()
        self._create_member(
            org=self.organization, group=self.test_default_group, user=member_user2,
            code="code", is_active=True, is_delete=False
        )
        # Create file content(set row of same email)
        content = self._create_content_uploaded_file(self.organization)
        content = content.replace(member_user2.username, member_user1.username)

        param = {
            'organization': self.organization.id,
            'member_csv': self._create_uploaded_file(self.organization, content)
        }

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Line {line_number}:{message}".format(line_number=2, message="Username is already used in file.")
        )

    def test_register_csv_ajax_validate_error_code_overlap(self):
        # Create member
        self._create_member(
            org=self.organization, group=self.test_default_group, user=UserFactory.create(),
            code="code1", is_active=True, is_delete=False
        )
        self._create_member(
            org=self.organization, group=self.test_default_group, user=UserFactory.create(),
            code="code2", is_active=True, is_delete=False
        )
        # Create file content(set row of same email)
        content = self._create_content_uploaded_file(self.organization)
        content = content.replace("code2", "code1")

        param = {
            'organization': self.organization.id,
            'member_csv': self._create_uploaded_file(self.organization, content)
        }

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'][0],
            "Line {line_number}:{message}".format(line_number=2, message="Member code is already used in file.")
        )

    def test_register_csv_ajax_validate_error_not_found_group(self):
        # Create another org and group
        org = self._create_organization()
        org_group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='not_found_group_code', group_name='not_found_group_name', org=org,
            created_by=self.user, modified_by=self.user
        )

        # Create member
        self._create_member(
            org=self.organization, group=org_group, user=UserFactory.create(),
            code="code1", is_active=True, is_delete=False
        )

        param = {
            'organization': self.organization.id,
            'member_csv': self._create_uploaded_file(self.organization)
        }

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_csv_ajax, param, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'][0], "Line {line_number}:{message}".format(
            line_number=1, message="Organization Groups is not found by organization."))

    def test_task_history_ajax(self):
        task_key = self.organization.org_code
        task_list = [
            self._create_task(MEMBER_REGISTER, task_key, 'task_id1', 'SUCCESS', 1, 1, 1, 0, 0),
            self._create_task(MEMBER_REGISTER, task_key, 'task_id2', 'FAILURE', 1, 1, 0, 0, 1),
            self._create_task(MEMBER_REGISTER, task_key, 'task_id3', 'QUEUING', 1, 1, 0, 1, 0),
            self._create_task('dummy_task', 'dummy_task_key1', 'dummy_task_id5', 'PROGRESS', 1, 1, 1, 0, 0),
            self._create_task('dummy_task', 'dummy_task_key2', 'dummy_task_id6', 'DUMMY', 1, 1, 1, 0, 0),
        ]
        # Create histories for target organization
        _now = datetime.now(pytz.UTC)
        histories = [MemberTaskHistoryFactory.create(
            organization=self.organization,
            task_id=task.task_id,
            created=_now + timedelta(seconds=i),
            updated=_now + timedelta(seconds=i * 10),
            requester=self.user
        ) for i, task in enumerate(task_list)]

        # Set result of executed task
        histories[0].result = True
        histories[0].messages = 'Sample success message1'
        histories[0].save()
        histories[0].result = False
        histories[1].messages = 'Sample fail message1'
        histories[1].save()

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_task_history_ajax, {})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual('success', data['status'])
        self.assertEqual(len(task_list), data['total'])
        records = data['records']
        self._assert_task_history(
            history=records[0], recid=1, result='progress', messages=[],
            requester=self.user.username, created=histories[4].created, updated=histories[4].updated)
        self._assert_task_history(
            history=records[1], recid=2, result='progress', messages=[],
            requester=self.user.username, created=histories[3].created, updated=histories[3].updated)
        self._assert_task_history(
            history=records[2], recid=3, result='progress', messages=[],
            requester=self.user.username, created=histories[2].created, updated=histories[2].updated)
        self._assert_task_history(
            history=records[3], recid=4, result='Failed', messages=[{'recid': 1, 'message': 'Sample fail message1'}],
            requester=self.user.username, created=histories[1].created, updated=histories[1].updated, total=1, failed=1)
        self._assert_task_history(
            history=records[4], recid=5, result='Success', messages=[{'recid': 1, 'message': 'Sample success message1'}],
            requester=self.user.username, created=histories[0].created, updated=histories[0].updated, total=1,
            succeeded=1)

    def test_task_history_ajax_not_found(self):
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_task_history_ajax, {})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Task is not found.")

    @ddt.data(1, 3, 10)
    def test_task_history_ajax_limit(self, limit):
        task_key = self.organization.org_code
        task_list = [
            self._create_task(MEMBER_REGISTER, task_key, 'task_id1', 'SUCCESS', 1, 1, 1, 0, 0),
            self._create_task(MEMBER_REGISTER, task_key, 'task_id2', 'SUCCESS', 1, 1, 1, 0, 0),
            self._create_task(MEMBER_REGISTER, task_key, 'task_id3', 'SUCCESS', 1, 1, 1, 0, 0),
            self._create_task(MEMBER_REGISTER, task_key, 'task_id4', 'SUCCESS', 1, 1, 1, 0, 0),
            self._create_task(MEMBER_REGISTER, task_key, 'task_id5', 'SUCCESS', 1, 1, 1, 0, 0)
        ]
        # Create histories for target organization
        _now = datetime.now(pytz.UTC)
        for i, task in enumerate(task_list):
            MemberTaskHistoryFactory.create(
                organization=self.organization,
                result=True,
                messages='Sample success message1',
                task_id=task.task_id,
                created=_now + timedelta(seconds=i),
                updated=_now + timedelta(seconds=i * 10),
                requester=self.user
            )

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_task_history_ajax, {'limit': limit})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual('success', data['status'])
        self.assertEqual(len(task_list) if limit > len(task_list) else limit, data['total'])

    def test_task_validate_error_already_running(self):
        self._create_task(
            task_type=MEMBER_REGISTER,
            task_key=hashlib.md5(self.organization.org_code).hexdigest(),
            task_id='task_id',
            task_state='PROGRESS'
        )
        param = self._create_base_form_param()

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_register_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'],
            "{task_type_name} is being executed. Please check task history, leave time and try again.".format(
                task_type_name=TASKS[MEMBER_REGISTER])
        )

    def test_task_submit_duplicated(self):
        self._create_task(
            task_type=MEMBER_REGISTER,
            task_key=hashlib.md5(self.organization.org_code).hexdigest(),
            task_id='task_id',
            task_state='PROGRESS'
        )
        param = self._create_base_form_param()

        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager), patch(
                'biz.djangoapps.gx_member.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = None
            response = self.client.post(self._url_register_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'],
            "Processing of Member Register is running.Execution status, please check from the task history."
        )

    def test_task_history_ajax_unmatch_history(self):
        patcher = patch('biz.djangoapps.gx_member.views.log')
        self.mock_log = patcher.start()
        self.addCleanup(patcher.stop)

        _now = datetime.now(pytz.UTC)
        MemberTaskHistoryFactory.create(
            organization=self.organization,
            result=True,
            messages='',
            task_id='task_id',
            created=_now,
            updated=_now + timedelta(seconds=10),
            requester=self.user
        )
        with self.skip_check_course_selection(
                current_organization=self.organization, current_manager=self._director_manager):
            response = self.client.post(self._url_task_history_ajax, {})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual('success', data['status'])
        self.assertEqual(0, data['total'])
        self.mock_log.warning.assert_any_call('Can not find Task by member task history')

    def test_models(self):
        """
        test model unicode string for Django Admin
        :return:
        """
        member = self._create_member(
            org=self.organization, group=self.test_default_group, user=UserFactory.create(),
            code="sample_code", is_active=True, is_delete=False
        )
        self.assertEqual(u"sample_code", unicode(member))

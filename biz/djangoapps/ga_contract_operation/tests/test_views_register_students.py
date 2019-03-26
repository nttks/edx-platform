# -*- coding: utf-8 -*-
"""
Test for contract_operation register_students feature
"""
import ddt
import hashlib
import json
from collections import OrderedDict
from mock import patch

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract.models import AdditionalInfo
from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory, AdditionalInfoUpdateTaskTarget
from biz.djangoapps.ga_contract_operation.tasks import ADDITIONALINFO_UPDATE
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.ga_invitation.models import ContractRegister, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupUtil
from biz.djangoapps.gx_org_group.models import Group

from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.tests.factories import TaskFactory

from student.models import UserProfile
from student.tests.factories import UserFactory


ERROR_MSG = "Test Message"


class ContractOperationViewTestRegisterStudents(BizContractTestBase):
    # ------------------------------------------------------------
    # ContractOperationViewTestRegisterStudents
    # ------------------------------------------------------------
    @property
    def _url_register_students_ajax(self):
        return reverse('biz:contract_operation:register_students')

    @property
    def _director_manager(self):
        return self._create_manager(org=self.contract_org, user=self.user,
                                    created=self.gacco_organization, permissions=[self.director_permission])

    @property
    def _manager_manager(self):
        return self._create_manager(
            org=self.contract_org, user=self.user, created=self.contract_org, permissions=[self.manager_permission])

    def test_register_students_director(self):
        self.setup_user()
        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract,
                                              current_manager=self._director_manager):
            self.assert_request_status_code(200, self._url_register_students_ajax)

    def test_register_students_manager(self):
        self.setup_user()
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract,
                                              current_manager=self._manager_manager):
            self.assert_request_status_code(200, self._url_register_students_ajax)


@ddt.ddt
class ContractOperationViewTestSearchStudentsAjax(BizContractTestBase):
    # ------------------------------------------------------------
    # ContractOperationViewTestSearchStudentsAjax
    # ------------------------------------------------------------
    @property
    def _url_register_students_ajax(self):
        return reverse('biz:contract_operation:register_students_search_students_ajax')

    @property
    def _director_manager(self):
        return self._create_manager(org=self.gacco_organization, user=self.user,
                                    created=self.gacco_organization, permissions=[self.director_permission])

    def _create_user_and_contract_register(self, contract, **kwargs):
        user = UserFactory.create(**kwargs)
        register = self.create_contract_register(user=user, contract=contract)
        return user, register

    def _create_member(self, org, group, user, code, is_active=True, is_delete=False, **kwargs):
        return MemberFactory.create(
            org=org,
            group=group,
            user=user,
            code=code,
            created_by=self.user,
            creator_org=org,
            updated_by=self.user,
            updated_org=org,
            is_active=is_active,
            is_delete=is_delete,
            **kwargs
        )

    def _assert_search_record(self, record, user_id, full_name, user_name, user_email, login_code=None):
        self.assertEqual(record['user_id'], user_id)
        self.assertEqual(record['full_name'], full_name)
        self.assertEqual(record['user_name'], user_name)
        self.assertEqual(record['user_email'], user_email)
        self.assertEqual(record['login_code'], login_code)

    def _create_param_search_students(
            self, contract_id=None, search_group_code='', search_contract_id='', search_login_code='',
            search_name='', search_email='', **kwargs):
        param = {
            'contract_id': contract_id or self.contract.id,
            'search_group_code': search_group_code,
            'search_contract_id': search_contract_id,
            'search_login_code': search_login_code,
            'search_name': search_name,
            'search_email': search_email,
        }
        for i in range(1, 11):
            param['search_org' + str(i)] = ''
            param['search_grp' + str(i)] = ''

        param.update(**kwargs)

        return param

    def test_search_students_ajax(self):
        self.setup_user()
        director_manager = self._director_manager
        another_contract = self._create_contract(contractor_organization=self.contract_org, contract_name='contract1')
        user1, register1 = self._create_user_and_contract_register(contract=self.contract)
        profile1 = UserProfile.objects.get(user=user1)
        user2, register2 = self._create_user_and_contract_register(contract=another_contract)
        profile2 = UserProfile.objects.get(user=user2)

        param = self._create_param_search_students(search_contract_id=self.contract.id)

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 1)
        self._assert_search_record(
            record=data['records'][0], user_id=user1.id, full_name=profile1.name, user_name=user1.username,
            user_email=user1.email)

    def test_search_students_ajax_no_search_contract_id(self):
        self.setup_user()
        director_manager = self._director_manager
        user1, register1 = self._create_user_and_contract_register(contract=self.contract)
        user2 = UserFactory.create()
        profile2 = UserProfile.objects.get(user=user2)
        self._create_member(org=self.contract_org, group=None, user=user2, code='sample_code1')
        user3, register3 = self._create_user_and_contract_register(contract=self.contract)
        profile3 = UserProfile.objects.get(user=user3)
        self._create_member(org=self.contract_org, group=None, user=user3, code='sample_code3')

        param = self._create_param_search_students()

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 2)
        self._assert_search_record(
            record=data['records'][0], user_id=user2.id, full_name=profile2.name, user_name=user2.username,
            user_email=user2.email)
        self._assert_search_record(
            record=data['records'][1], user_id=user3.id, full_name=profile3.name, user_name=user3.username,
            user_email=user3.email)

    def test_search_students_ajax_deficit(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = dict()
        register_data['contract_id'] = self.contract.id

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, register_data)
        self.assertEqual(400, response.status_code)

    def test_search_students_ajax_contract_id(self):
        self.setup_user()
        director_manager = self._director_manager
        another_contract = self._create_contract(contractor_organization=self.contract_org, contract_name='contract1')
        user1, register1 = self._create_user_and_contract_register(contract=self.contract)
        profile1 = UserProfile.objects.get(user=user1)
        user2, register2 = self._create_user_and_contract_register(contract=another_contract)
        profile2 = UserProfile.objects.get(user=user1)

        param = self._create_param_search_students(search_contract_id=self.contract.id)

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 1)

    def test_search_students_ajax_email(self):
        self.setup_user()
        director_manager = self._director_manager
        self._create_user_and_contract_register(contract=self.contract, email='test_student1@example.com')
        param = self._create_param_search_students(
            search_contract_id=self.contract.id,
            search_email='test_student1'
        )

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['records'][0]['user_email'], 'test_student1@example.com')

    def test_search_students_ajax_name(self):
        self.setup_user()
        director_manager = self._director_manager
        user1, __ = self._create_user_and_contract_register(contract=self.contract)
        profile1 = UserProfile.objects.get(user=user1)
        profile1.name = 'test_student1_name'
        profile1.save()
        param = self._create_param_search_students(
            search_contract_id=self.contract.id,
            search_name='test_student1'
        )

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['records'][0]['full_name'], 'test_student1_name')

    def test_search_students_ajax_login_code(self):
        self.setup_user()
        director_manager = self._director_manager
        user1, __ = self._create_user_and_contract_register(contract=self.contract)
        BizUserFactory.create(user=user1, login_code='test_student1_login_code')
        param = self._create_param_search_students(
            search_contract_id=self.contract.id,
            search_login_code='test_student1'
        )

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['records'][0]['login_code'], 'test_student1_login_code')

    def test_search_students_ajax_group_code(self):
        self.setup_user()
        director_manager = self._director_manager
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        group = Group.objects.filter(org=self.contract_org, group_code='G01-01').first()
        user1, __ = self._create_user_and_contract_register(contract=self.contract, username='sample_students1')
        self._create_member(org=self.contract_org, code='sample', group=group, user=user1)

        param = self._create_param_search_students(
            search_contract_id=self.contract.id,
            search_group_code='G01-01'
        )

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['records'][0]['user_name'], 'sample_students1')

    @ddt.data('org', 'item')
    def test_search_students_ajax_org_item(self, key):
        self.setup_user()
        director_manager = self._director_manager
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        group = Group.objects.filter(org=self.contract_org, group_code='G01-01').first()
        for i in range(1, 11):
            user, __ = self._create_user_and_contract_register(contract=self.contract)
            self._create_member(org=self.contract_org, code='sample' + key + str(i), group=group, user=user, **dict({
                key + str(i) : 'sample' + key + str(i)
            }))

        for i in range(1, 11):
            if key is 'org':
                param = self._create_param_search_students(
                    search_contract_id=self.contract.id,
                    **dict({'search_org' + str(i) : 'sample' + key + str(i)})
                )
            else:
                param = self._create_param_search_students(
                    search_contract_id=self.contract.id,
                    **dict({'search_grp' + str(i) : 'sample' + key + str(i)})
                )

            with self.skip_check_course_selection(current_organization=self.contract_org,
                                                  current_contract=self.contract,
                                                  current_manager=director_manager):
                response = self.client.post(self._url_register_students_ajax, param)

            self.assertEqual(200, response.status_code)
            data = json.loads(response.content)
            self.assertEqual(data['total'], 1)

    def test_search_students_ajax_no_search_contract_id_email(self):
        self.setup_user()
        director_manager = self._director_manager
        user1 = UserFactory.create(email='test_student1@example.com')
        self._create_member(org=self.contract_org, group=None, user=user1, code='sample_code')
        param = self._create_param_search_students(search_email='test_student1')

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['records'][0]['user_email'], 'test_student1@example.com')

    def test_search_students_ajax_no_search_contract_id_name(self):
        self.setup_user()
        director_manager = self._director_manager
        user1 = UserFactory.create()
        profile1 = UserProfile.objects.get(user=user1)
        profile1.name = 'test_student1_name'
        profile1.save()
        self._create_member(org=self.contract_org, group=None, user=user1, code='sample_code')

        param = self._create_param_search_students(
            search_name='test_student1'
        )

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['records'][0]['full_name'], 'test_student1_name')

    def test_search_students_ajax_no_search_contract_id_login_code(self):
        self.setup_user()
        director_manager = self._director_manager
        user1 = UserFactory.create()
        BizUserFactory.create(user=user1, login_code='test_student1_login_code')
        self._create_member(org=self.contract_org, group=None, user=user1, code='sample_code')

        param = self._create_param_search_students(
            search_login_code='test_student1'
        )

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['records'][0]['login_code'], 'test_student1_login_code')

    def test_search_students_ajax_no_search_contract_id_group_code(self):
        self.setup_user()
        director_manager = self._director_manager
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        group = Group.objects.filter(org=self.contract_org, group_code='G01-01').first()
        user1 = UserFactory.create(username='sample_students1')
        self._create_member(org=self.contract_org, group=group, user=user1, code='sample_code')
        param = self._create_param_search_students(
            search_group_code='G01-01'
        )

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract, current_manager=director_manager):
            response = self.client.post(self._url_register_students_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['records'][0]['user_name'], 'sample_students1')

    @ddt.data('org', 'item')
    def test_search_students_ajax_no_search_contract_id_org_item(self, key):
        self.setup_user()
        director_manager = self._director_manager
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        for i in range(1, 11):
            user = UserFactory.create()
            self._create_member(
                org=self.contract_org, group=None, user=user, code='sample_code' + str(i), **dict({
                key + str(i) : 'sample' + key + str(i)
            }))

        for i in range(1, 11):
            if key is 'org':
                param = self._create_param_search_students(
                    **dict({'search_org' + str(i) : 'sample' + key + str(i)})
                )
            else:
                param = self._create_param_search_students(
                    **dict({'search_grp' + str(i) : 'sample' + key + str(i)})
                )

            with self.skip_check_course_selection(current_organization=self.contract_org,
                                                  current_contract=self.contract,
                                                  current_manager=director_manager):
                response = self.client.post(self._url_register_students_ajax, param)

            self.assertEqual(200, response.status_code)
            data = json.loads(response.content)
            self.assertEqual(data['total'], 1)


@ddt.ddt
class ContractOperationViewTestTemplateDownload(BizContractTestBase):

    # ------------------------------------------------------------
    # ContractOperationViewTestTemplateDownload
    # ------------------------------------------------------------
    @property
    def _url_register_students_ajax(self):
        return reverse('biz:contract_operation:register_students_template_download')

    @property
    def _director_manager(self):
        return self._create_manager(org=self.gacco_organization, user=self.user,
                                    created=self.gacco_organization, permissions=[self.director_permission])

    def test_template_download(self):
        self.setup_user()
        director_manager = self._director_manager
        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax)
        self.assertEqual(200, response.status_code)

    def test_template_download_auth(self):
        self.setup_user()
        director_manager = self._director_manager
        with self.skip_check_course_selection(current_contract=self.contract_auth, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax)
        self.assertEqual(200, response.status_code)


@ddt.ddt
class ContractOperationViewTestRegisterStudentsAjax(BizContractTestBase):

    def _url_register_students_ajax(self):
        return reverse('biz:contract_operation:register_students_ajax')

    def test_register_contract_unmatch(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract_mooc.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Current contract is changed. Please reload this page.')

    def test_register_validate_task_error(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], ERROR_MSG)

    def test_register_validate_org_task_error(self):
        self.setup_user()
        TaskFactory.create(
            task_type='student_register', task_key=hashlib.md5(str(self.contract_org.org_code)).hexdigest())
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(
            current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(
                self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            data['error'], "Student Register is being executed. Please check task history, leave time and try again.")

    def test_register_no_param(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_param_students_list(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract_mooc.id})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_param_contract_id(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_student(self):
        self.setup_user()
        csv_content = ""

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Could not find student list.')

    def test_register_student_not_allowed_method(self):
        response = self.client.get(self._url_register_students_ajax())
        self.assertEqual(405, response.status_code)

    def test_register_student_submit_successful(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)
        self.assertItemsEqual([u'Input,{}'.format(s) for s in csv_content.splitlines()], [target.student for target in history.studentregistertasktarget_set.all()])

    def test_register_student_submit_successful_register(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content, 'register_status': REGISTER_INVITATION_CODE})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)
        self.assertItemsEqual([u'Register,{}'.format(s) for s in csv_content.splitlines()], [target.student for target in history.studentregistertasktarget_set.all()])

    def test_register_student_submit_illegal_register(self):
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content, 'register_status': UNREGISTER_INVITATION_CODE})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Invalid access.')

    def test_register_student_submit_duplicated(self):
        TaskFactory.create(task_type='student_register', task_key=hashlib.md5(str(self.contract.id)).hexdigest())
        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_1,テスター２"

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = None
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Processing of Student Register is running.Execution status, please check from the task history.", data['error'])
        # assert not to be created new Task instance.
        self.assertEqual(1, Task.objects.count())

    @override_settings(BIZ_MAX_REGISTER_NUMBER=2)
    def test_register_students_over_max_number(self):

        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_2,テスター２\n" \
                      u"test_student3@example.com,test_student_3,テスター３"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("It has exceeded the number(2) of cases that can be a time of registration.", data['error'])

        self.assertFalse(User.objects.filter(username='test_student_1', email='test_student1@example.com').exists())
        self.assertFalse(User.objects.filter(username='test_student_2', email='test_student2@example.com').exists())
        self.assertFalse(User.objects.filter(username='test_student_3', email='test_student3@example.com').exists())

        self.assertFalse(ContractRegister.objects.filter(user__email='test_student1@example.com', contract=self.contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=self.contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=self.contract).exists())

    @override_settings(BIZ_MAX_CHAR_LENGTH_REGISTER_LINE=45)
    def test_register_students_over_max_char_length(self):

        self.setup_user()
        csv_content = u"test_student1@example.com,test_student_1,テスター１\n" \
                      u"test_student2@example.com,test_student_2,テスター２\n" \
                      u"test_student3@example.com,test_student_3,テスター３"

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_register_students_ajax(), {'contract_id': self.contract.id, 'students_list': csv_content})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("The number of lines per line has exceeded the 45 characters.", data['error'])

        self.assertFalse(User.objects.filter(username='test_student_1', email='test_student1@example.com').exists())
        self.assertFalse(User.objects.filter(username='test_student_2', email='test_student2@example.com').exists())
        self.assertFalse(User.objects.filter(username='test_student_3', email='test_student3@example.com').exists())

        self.assertFalse(ContractRegister.objects.filter(user__email='test_student1@example.com', contract=self.contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student2@example.com', contract=self.contract).exists())
        self.assertFalse(ContractRegister.objects.filter(user__email='test_student3@example.com', contract=self.contract).exists())


@ddt.ddt
class ContractOperationViewTestRegisterStudentsNewAjax(BizContractTestBase):

    # ------------------------------------------------------------
    # ContractOperationViewTestRegisterStudentsNewAjax
    # ------------------------------------------------------------
    @property
    def _url_register_students_ajax(self):
        return reverse('biz:contract_operation:register_students_new_ajax')

    @property
    def _director_manager(self):
        return self._create_manager(org=self.gacco_organization, user=self.user,
                                    created=self.gacco_organization, permissions=[self.director_permission])

    @property
    def _register_students_data(self):
        register_data = dict()
        register_data['employee_email'] = 'test_student1@example.com'
        register_data['user_name'] = 'test_student_1'
        register_data['employee_last_name'] = 'Test'
        register_data['employee_first_name'] = 'er1'
        register_data['login_code'] = ''
        register_data['password'] = ''
        register_data['employee_group_code'] = ''
        register_data['employee_code'] = ''
        for i in range(1, 11):
            register_data['org_attr' + str(i)] = ''
            register_data['grp_attr' + str(i)] = ''

        return register_data

    def test_register_contract_unmatch(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            register_data['contract_id'] = self.contract_mooc.id
            response = self.client.post(self._url_register_students_ajax, register_data)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Current contract is changed. Please reload this page.')

    def test_register_no_param(self):
        self.setup_user()
        director_manager = self._director_manager
        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_param_students_list(self):
        self.setup_user()
        director_manager = self._director_manager
        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract_mooc.id})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_param_contract_id(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, register_data)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_student(self):
        self.setup_user()
        director_manager = self._director_manager
        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract.id,
                                                                           'employee_email': None,
                                                                           'user_name': None})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_student_csv_over_item_length(self):
        self.setup_user()
        director_manager = self._director_manager

        register_data = dict()
        register_data['employee_email'] = 'test_student1@example.com'
        register_data['user_name'] = 'test_student_1'
        register_data['employee_last_name'] = 'Test'
        register_data['employee_first_name'] = 'er1'
        register_data['employee_group_code'] = ''
        register_data['employee_code'] = ''
        for i in range(1, 11):
            register_data['org_attr' + str(i)] = 'a' * 350
            register_data['grp_attr' + str(i)] = 'a' * 350

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            register_data['contract_id'] = self.contract.id
            response = self.client.post(self._url_register_students_ajax, register_data)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'The number of lines per line has exceeded the 7000 characters.')

    def test_register_student_not_allowed_method(self):
        response = self.client.get(self._url_register_students_ajax)
        self.assertEqual(405, response.status_code)

    def test_register_student_submit_has_auth_login_code_empty(self):
        self.setup_user()
        director_manager = self._director_manager

        register_data = dict()
        register_data['employee_email'] = 'test_student1@example.com'
        register_data['user_name'] = 'test_student_1'
        register_data['employee_last_name'] = 'Test'
        register_data['employee_first_name'] = 'er1'
        register_data['employee_group_code'] = ''
        register_data['employee_code'] = ''
        for i in range(1, 11):
            register_data['org_attr' + str(i)] = ''
            register_data['grp_attr' + str(i)] = ''

        with self.skip_check_course_selection(current_contract=self.contract_auth, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            register_data['contract_id'] = self.contract_auth.id
            response = self.client.post(self._url_register_students_ajax, register_data)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_student_submit_successful(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            register_data['contract_id'] = self.contract.id
            response = self.client.post(self._url_register_students_ajax, register_data)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Member Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_member_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful_mail_flg(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            register_data['contract_id'] = self.contract.id
            register_data['sendmail_flg'] = 'on'
            response = self.client.post(self._url_register_students_ajax, register_data)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Member Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_member_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful_has_auth(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data

        with self.skip_check_course_selection(current_contract=self.contract_auth, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            register_data['contract_id'] = self.contract_auth.id
            register_data['login_code'] = 'login_code'
            response = self.client.post(self._url_register_students_ajax, register_data)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Member Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_member_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract_auth.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful_register(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_data['register_status'] = REGISTER_INVITATION_CODE

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            register_data['contract_id'] = self.contract.id
            response = self.client.post(self._url_register_students_ajax, register_data)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Member Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_member_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful_register_invalid(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_data['register_status'] = 'invalid'

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            register_data['contract_id'] = self.contract.id
            response = self.client.post(self._url_register_students_ajax, register_data)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Invalid access.')


@ddt.ddt
class ContractOperationViewTestRegisterStudentsListAjax(BizContractTestBase):

    # ------------------------------------------------------------
    # ContractOperationViewTestRegisterStudentsListAjax
    # ------------------------------------------------------------
    @property
    def _url_register_students_ajax(self):
        return reverse('biz:contract_operation:register_students_list_ajax')

    @property
    def _director_manager(self):
        return self._create_manager(org=self.gacco_organization, user=self.user,
                                    created=self.gacco_organization, permissions=[self.director_permission])

    @property
    def _register_students_data(self):
        register_data = dict()
        register_data['user_email'] = 'test_student1@example.com'
        register_data['user_name'] = 'test_student_1'
        register_data['full_name'] = 'Test er1'
        register_data['login_code'] = ''
        register_data['password'] = ''
        register_data['org_id'] = '1'
        register_data['member_code'] = ''

        register_data_list = list()
        register_data_list.append(register_data)

        return register_data_list

    def test_register_contract_unmatch(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract_mooc.id,
                                        'add_list': register_json})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Current contract is changed. Please reload this page.')

    def test_register_no_param(self):
        self.setup_user()
        director_manager = self._director_manager
        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_param_students_list(self):
        self.setup_user()
        director_manager = self._director_manager
        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract_mooc.id})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_param_contract_id(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'add_list': register_json})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_has_auth(self):
        self.setup_user()
        director_manager = self._director_manager

        register_data_one = dict()
        register_data_one['user_email'] = 'test_student1@example.com'
        register_data_one['user_name'] = 'test_student_1'
        register_data_one['full_name'] = 'Test er1'
        register_data_one['org_id'] = '1'
        register_data_one['member_code'] = ''

        register_data_list = list()
        register_data_list.append(register_data_one)

        register_data = register_data_list

        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract_auth, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'add_list': register_json})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_student(self):
        self.setup_user()
        director_manager = self._director_manager
        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract.id,
                                                                           'add_list': json.dumps('')})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Could not find student list.')

    def test_register_student_not_allowed_method(self):
        response = self.client.get(self._url_register_students_ajax)
        self.assertEqual(405, response.status_code)

    def test_register_student_submit_over_records(self):
        self.setup_user()
        director_manager = self._director_manager

        register_data_one = dict()
        register_data_one['user_email'] = 'test_student1@example.com'
        register_data_one['user_name'] = 'test_student_1'
        register_data_one['full_name'] = 'Test er1'
        register_data_one['login_code'] = ''
        register_data_one['password'] = ''
        register_data_one['org_id'] = '1'
        register_data_one['member_code'] = ''
        register_data = list()
        for i in range(1, 60000):
            register_data.append(register_data_one)

        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract.id,
                                                                           'add_list': register_json})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'It has exceeded the number(50000) of cases that can be a time of registration.')

    def test_register_student_submit_over_item_length(self):
        self.setup_user()
        director_manager = self._director_manager

        register_data_one = dict()
        register_data_one['user_email'] = 'test_student1@example.com'
        register_data_one['user_name'] = 'test_student_1'
        register_data_one['full_name'] = 'a' * 7000
        register_data_one['login_code'] = ''
        register_data_one['password'] = ''
        register_data_one['org_id'] = '1'
        register_data_one['member_code'] = ''
        register_data = list()
        register_data.append(register_data_one)
        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract.id,
                                                                           'add_list': register_json})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'The number of lines per line has exceeded the 7000 characters.')

    def test_register_student_submit_successful_used_contract(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_data[0]['login_code'] = "0001"
        register_data[0]['member_code'] = "0001"
        register_data[0]['org_id'] = "1"
        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract.id,
                                                                           'add_list': register_json})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract.id,
                                                                           'add_list': register_json})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful_mail_flg(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract.id,
                                                                           'add_list': register_json,
                                                                           'sendmail_flg': 'on'},)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful_has_auth(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_data[0]['login_code'] = 'login_code'
        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract_auth, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract_auth.id,
                                                                           'add_list': register_json})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract_auth.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_has_auth_login_code_empty(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract_auth, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract_auth.id,
                                                                           'add_list': register_json})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'This course required login code register')

    def test_register_student_submit_successful_register(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract.id,
                                                                           'add_list': register_json,
                                                                           'register_status': REGISTER_INVITATION_CODE})

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual("Began the processing of Student Register.Execution status, please check from the task history.", data['info'])

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful_register_invalid(self):
        self.setup_user()
        director_manager = self._director_manager
        register_data = self._register_students_data
        register_json = json.dumps(register_data)

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {'contract_id': self.contract.id,
                                                                           'add_list': register_json,
                                                                           'register_status': 'invalid'})

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Invalid access.')


@ddt.ddt
class ContractOperationViewTestRegisterStudentsCsvAjax(BizContractTestBase):

    # ------------------------------------------------------------
    # ContractOperationViewTestRegisterStudentsCsvAjax
    # ------------------------------------------------------------
    @property
    def _url_register_students_ajax(self):
        return reverse('biz:contract_operation:register_students_csv_ajax')

    @property
    def _director_manager(self):
        return self._create_manager(org=self.gacco_organization, user=self.user,
                                    created=self.gacco_organization, permissions=[self.director_permission])

    @property
    def _file_content(self):
        file_content = OrderedDict()
        file_content["Email"] = 'test_student1@example.com'
        file_content["Username"] = 'test_student_1'
        file_content["Last Name"] = 'test_sei'
        file_content["First Name"] = 'test_mei'
        file_content["Organization Code"] = ''
        file_content["Member Code"] = ''
        for i in range(1, 11):
            file_content['Organization' + str(i)] = ''
        for i in range(1, 11):
            file_content['Item' + str(i)] = ''

        return file_content

    def _register_students_data(self, **kwargs):
        file_content = self._file_content
        if kwargs and len(kwargs):
            file_content.update(kwargs)

        return SimpleUploadedFile(
            'sample.csv',
            (','.join(file_content.keys()) + '\n' + ','.join(file_content.values())).encode('cp932'),
            content_type='multipart/form-data'
        )

    def test_register_contract_unmatch(self):
        self.setup_user()
        director_manager = self._director_manager
        register_csv_data = self._register_students_data()

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract_mooc.id,
                    'csv_data': register_csv_data
                }, format='multipart'
            )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Current contract is changed. Please reload this page.')

    def test_register_no_param(self):
        self.setup_user()
        director_manager = self._director_manager
        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(self._url_register_students_ajax, {}, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_param_students_list(self):
        self.setup_user()
        director_manager = self._director_manager
        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract_mooc.id,
                    'csv_data': None
                }, format='multipart'
            )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_no_param_contract_id(self):
        self.setup_user()
        director_manager = self._director_manager
        register_csv_data = self._register_students_data()

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {'csv_data': register_csv_data}, format='multipart')

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    def test_register_student_not_allowed_method(self):
        response = self.client.get(self._url_register_students_ajax)
        self.assertEqual(405, response.status_code)

    def test_register_student_csv_empty(self):
        self.setup_user()
        director_manager = self._director_manager
        register_csv_data = SimpleUploadedFile('sample.csv', '', content_type='multipart/form-data')

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract.id,
                    'csv_data': register_csv_data
                }, format='multipart'
            )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'invalid header or file type')

    def test_register_student_csv_over_records(self):
        self.setup_user()
        director_manager = self._director_manager

        header = ','.join(self._file_content.keys()) + '\n'
        row = self._file_content.values()
        rows = '\n'.join([','.join(row) for i in range(1, 60000)])

        register_csv_data = SimpleUploadedFile(
            'sample.csv', (header + rows).encode('cp932'), content_type='multipart/form-data')

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract.id,
                    'csv_data': register_csv_data
                }, format='multipart'
            )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(
            data['error'], 'It has exceeded the number(9999) of cases that can be a time of registration.')

    def test_register_student_csv_over_item_length(self):
        self.setup_user()
        director_manager = self._director_manager

        header = ','.join(self._file_content.keys()) + '\n'
        rows = "test_student1@example.com,test_student_1,Test,er1," + 'a' * 7000 + ",,,,,,,,,,,,,,,,,,,,,,,\n"

        register_csv_data = SimpleUploadedFile(
            'sample.csv', (header + rows).encode('cp932'), content_type='multipart/form-data')

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract.id,
                    'csv_data': register_csv_data
                }, format='multipart'
            )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'The number of lines per line has exceeded the 7000 characters.')

    def test_register_student_csv_only_header(self):
        self.setup_user()
        director_manager = self._director_manager

        header = ','.join(self._file_content.keys()) + '\n'
        register_csv_data = SimpleUploadedFile('sample.csv', header.encode('cp932'), content_type='multipart/form-data')

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract.id,
                    'csv_data': register_csv_data
                }, format='multipart'
            )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Could not find student list.')

    def test_register_student_csv_pure_template(self):
        self.setup_user()
        director_manager = self._director_manager
        register_csv_data = self._register_students_data(**{
            'Email': 'username1@domain.com', 'Username': 'gaccotarou', 'Last Name': 'gacco', 'First Name': 'taro'})

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract.id,
                    'csv_data': register_csv_data
                }, format='multipart'
            )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Could not find student list.')

    def test_register_student_csv_utf16(self):
        self.setup_user()
        director_manager = self._director_manager
        register_csv_data = SimpleUploadedFile(
            'sample.csv', "sample".encode('utf-8'), content_type='multipart/form-data')

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract.id,
                    'csv_data': register_csv_data
                }, format='multipart'
            )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'invalid header or file type')

    def test_register_student_submit_successful(self):
        self.setup_user()
        director_manager = self._director_manager
        register_csv_data = self._register_students_data()

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract.id,
                    'csv_data': register_csv_data
                }, format='multipart'
            )

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            "Began the processing of Student Member Register.Execution status, please check from the task history.",
            data['info']
        )

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_member_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful_mail_flg(self):
        self.setup_user()
        director_manager = self._director_manager
        register_csv_data = self._register_students_data()

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract.id,
                    'csv_data': register_csv_data,
                    'sendmail_flg': 'on',
                }, format='multipart'
            )

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            "Began the processing of Student Member Register.Execution status, please check from the task history.",
            data['info']
        )

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_member_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful_register(self):
        self.setup_user()
        director_manager = self._director_manager
        register_csv_data = self._register_students_data()

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract.id,
                    'csv_data': register_csv_data,
                    'register_status': REGISTER_INVITATION_CODE}, format='multipart'
            )

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(
            "Began the processing of Student Member Register.Execution status, please check from the task history.",
            data['info']
        )

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual('student_member_register', task.task_type)

        task_input = json.loads(task.task_input)
        self.assertEqual(self.contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)

    def test_register_student_submit_successful_register_invalid(self):
        self.setup_user()
        director_manager = self._director_manager
        register_csv_data = self._register_students_data()

        with self.skip_check_course_selection(current_contract=self.contract, current_manager=director_manager,
                                              current_organization=self.gacco_organization):
            response = self.client.post(
                self._url_register_students_ajax, {
                    'contract_id': self.contract.id,
                    'csv_data': register_csv_data,
                    'register_status': 'invalid'
                }, format='multipart'
            )

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Invalid access.')


@ddt.ddt
class ContractOperationViewAdditionalInfoTest(BizContractTestBase):

    def setUp(self):
        super(ContractOperationViewAdditionalInfoTest, self).setUp()
        self.setup_user()

    def _register_additional_info_ajax(self, params):
        return self.client.post(reverse('biz:contract_operation:register_additional_info_ajax'), params)

    def _edit_additional_info_ajax(self, params):
        return self.client.post(reverse('biz:contract_operation:edit_additional_info_ajax'), params)

    def _delete_additional_info_ajax(self, params):
        return self.client.post(reverse('biz:contract_operation:delete_additional_info_ajax'), params)

    def _assert_response_error_json(self, response, error_message):
        self.assertEqual(400, response.status_code)
        self.assertEqual(error_message, json.loads(response.content)['error'])

    # ------------------------------------------------------------
    # register_additional_info_ajax
    # ------------------------------------------------------------
    @ddt.data('display_name', 'contract_id')
    def test_register_additional_info_no_param(self, param):
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }
        del params[param]

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Unauthorized access.")

    def test_register_additional_info_different_contract(self):
        params = {'display_name': 'test',
                  'contract_id': self._create_contract().id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Current contract is changed. Please reload this page.")

    def test_register_additional_info_validate_task_error(self):
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            self._assert_response_error_json(self._register_additional_info_ajax(params), ERROR_MSG)

    def test_register_additional_info_empty_display_name(self):
        params = {'display_name': '',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Please enter the name of item you wish to add.")

    def test_register_additional_info_over_length_display_name(self):
        max_length = AdditionalInfo._meta.get_field('display_name').max_length
        params = {'display_name': get_random_string(max_length + 1),
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Please enter the name of item within {max_number} characters.".format(max_number=max_length))

    def test_register_additional_info_same_display_name(self):
        self._create_additional_info(contract=self.contract, display_name='test')
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "The same item has already been registered.")

    @override_settings(BIZ_MAX_REGISTER_ADDITIONAL_INFO=1)
    def test_register_additional_info_max_additional_info(self):
        self._create_additional_info(contract=self.contract, display_name='hoge')
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Up to {max_number} number of additional item is created.".format(max_number=1))

    def test_register_additional_info_db_error(self):
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch.object(AdditionalInfo, 'objects') as patched_manager:
            patched_manager.create.side_effect = Exception
            patched_manager.filter.return_value.exists.return_value = False
            patched_manager.filter.return_value.count.return_value = 0

            self._assert_response_error_json(self._register_additional_info_ajax(params),
                                             "Failed to register item.")

    def test_register_additional_info_success(self):
        params = {'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self._register_additional_info_ajax(params)
        self.assertEqual(200, response.status_code)
        self.assertEqual("New item has been registered.", json.loads(response.content)['info'])

    # ------------------------------------------------------------
    # edit_additional_info_ajax
    # ------------------------------------------------------------
    @ddt.data('additional_info_id', 'display_name', 'contract_id')
    def test_edit_additional_info_no_param(self, param):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self.contract.id, }
        del params[param]

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "Unauthorized access.")

    def test_edit_additional_info_different_contract(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self._create_contract().id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "Current contract is changed. Please reload this page.")

    def test_edit_additional_info_validate_task_error(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            self._assert_response_error_json(self._edit_additional_info_ajax(params), ERROR_MSG)

    def test_edit_additional_info_empty_display_name(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': '',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "Please enter the name of item you wish to add.")

    def test_edit_additional_info_over_length_display_name(self):
        max_length = AdditionalInfo._meta.get_field('display_name').max_length
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': get_random_string(max_length + 1),
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "Please enter the name of item within {max_number} characters.".format(max_number=max_length))

    def test_edit_additional_info_same_display_name(self):
        self._create_additional_info(contract=self.contract, display_name='test')
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "The same item has already been registered.")

    def test_edit_additional_info_db_error(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch.object(AdditionalInfo, 'objects') as patched_manager:
            patched_manager.filter.return_value.exclude.return_value.exists.return_value = False
            patched_manager.filter.return_value.update.side_effect = Exception

            self._assert_response_error_json(self._edit_additional_info_ajax(params),
                                             "Failed to edit item.")

    def test_edit_additional_info_success(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'display_name': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self._edit_additional_info_ajax(params)
        self.assertEqual(200, response.status_code)
        self.assertEqual("New item has been updated.", json.loads(response.content)['info'])

    # ------------------------------------------------------------
    # delete_additional_info_ajax
    # ------------------------------------------------------------
    @ddt.data('additional_info_id', 'contract_id')
    def test_delete_additional_info_no_param(self, param):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self.contract.id, }
        del params[param]

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._delete_additional_info_ajax(params),
                                             "Unauthorized access.")

    def test_delete_additional_info_different_contract(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self._create_contract().id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._delete_additional_info_ajax(params),
                                             "Current contract is changed. Please reload this page.")

    def test_delete_additional_info_validate_task_error(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            self._assert_response_error_json(self._delete_additional_info_ajax(params), ERROR_MSG)

    def test_delete_additional_info_does_not_exist(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch.object(AdditionalInfo, 'objects') as patched_manager:
            patched_manager.get.side_effect = AdditionalInfo.DoesNotExist

            self._assert_response_error_json(self._delete_additional_info_ajax(params),
                                             "Already deleted.")

    def test_delete_additional_info_db_error(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract), patch.object(AdditionalInfo, 'objects') as patched_manager:
            patched_manager.get.return_value.delete.side_effect = Exception

            self._assert_response_error_json(self._delete_additional_info_ajax(params),
                                             "Failed to deleted item.")

    def test_delete_additional_info_success(self):
        additional_info = self._create_additional_info(contract=self.contract)
        params = {'additional_info_id': additional_info.id,
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            response = self._delete_additional_info_ajax(params)
        self.assertEqual(200, response.status_code)
        self.assertEqual("New item has been deleted.", json.loads(response.content)['info'])


class ContractOperationViewUpdateAdditionalInfoTest(BizContractTestBase):

    def setUp(self):
        super(ContractOperationViewUpdateAdditionalInfoTest, self).setUp()
        self.setup_user()

    def _update_additional_info_ajax(self, params):
        return self.client.post(reverse('biz:contract_operation:update_additional_info_ajax'), params)

    def _assert_response_error_json(self, response, error_message):
        self.assertEqual(400, response.status_code)
        self.assertEqual(error_message, json.loads(response.content)['error'])

    # ------------------------------------------------------------
    # update_additional_info_ajax
    # ------------------------------------------------------------
    def test_update_additional_info_success(self):
        contract = self._create_contract(contract_name='test_update_additional_info_success')
        self._create_user_and_contract_register(contract=contract, email='test_student1@example.com')
        self._create_user_and_contract_register(contract=contract, email='test_student2@example.com')
        additional_info1 = self._create_additional_info(contract=contract)
        additional_info2 = self._create_additional_info(contract=contract)
        input_line = u"test_student1@example.com,add1,add2\n" \
                     u"test_student2@example.com,add1,add2"

        params = {'additional_info': [additional_info1.id, additional_info2.id],
                  'contract_id': contract.id,
                  'update_students_list': input_line}

        with self.skip_check_course_selection(current_organization=self.contract_org, current_contract=contract):
            response = self._update_additional_info_ajax(params)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)

        # get latest task and assert
        task = Task.objects.all().order_by('-id')[0]
        self.assertEqual(ADDITIONALINFO_UPDATE, task.task_type)
        task_input = json.loads(task.task_input)
        self.assertEqual(contract.id, task_input['contract_id'])
        history = ContractTaskHistory.objects.get(pk=task_input['history_id'])
        self.assertEqual(history.task_id, task.task_id)
        for target in AdditionalInfoUpdateTaskTarget.objects.filter(history=history):
            self.assertIn(target.inputline, input_line)
        self.assertEqual(
            "Began the processing of Additional Item Update.Execution status, please check from the task history.",
            data['info'])

    def test_update_additional_info_contract_id_no_param(self):
        params = {'update_students_list': 'test',
                  'additional_info': 'test', }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._update_additional_info_ajax(params),
                                             "Unauthorized access.")

    def test_update_additional_info_student_list_no_param(self):
        params = {'contract_id': self.contract.id,
                  'additional_info': 'test', }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._update_additional_info_ajax(params),
                                             "Unauthorized access.")

    def test_update_additional_info_additional_info_no_param(self):
        params = {'update_students_list': 'test',
                  'contract_id': self.contract.id, }

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._update_additional_info_ajax(params),
                                             "No additional item registered.")

    def test_update_additional_info_different_contract(self):
        params = {'update_students_list': 'test',
                  'contract_id': self._create_contract().id,
                  'additional_info': 'test'}

        with self.skip_check_course_selection(current_contract=self.contract):
            self._assert_response_error_json(self._update_additional_info_ajax(params),
                                             "Current contract is changed. Please reload this page.")

    def test_update_additional_info_validate_task_error(self):
        contract = self._create_contract(contract_name='test_update_additional_info_success')
        self._create_user_and_contract_register(contract=contract, email='test_student1@example.com')
        self._create_user_and_contract_register(contract=contract, email='test_student2@example.com')
        additional_info1 = self._create_additional_info(contract=contract)
        additional_info2 = self._create_additional_info(contract=contract)
        input_line = u"test_student1@example.com,add1,add2\n" \
                     u"test_student2@example.com,add1,add2"

        params = {'additional_info': [additional_info1.id, additional_info2.id],
                  'contract_id': contract.id,
                  'update_students_list': input_line}

        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.validate_task') as mock_validate_task:
            mock_validate_task.return_value = ERROR_MSG
            self._assert_response_error_json(self._update_additional_info_ajax(params), ERROR_MSG)

    def test_update_additional_info_not_find_student_list(self):
        params = {'update_students_list': '',
                  'contract_id': self.contract.id,
                  'additional_info': 'test'}

        self._assert_response_error_json(self._update_additional_info_ajax(params),
                                         "Could not find student list.")

    @override_settings(BIZ_MAX_REGISTER_NUMBER=2)
    def test_update_additional_info_over_max_line(self):
        input_line = u"test_student1@example.com,add1,add2\n" \
                     u"test_student2@example.com,add1,add2\n" \
                     u"test_student3@example.com,add1,add2"

        params = {'update_students_list': input_line,
                  'contract_id': self.contract.id,
                  'additional_info': 'test'}

        self._assert_response_error_json(self._update_additional_info_ajax(params),
                                         "It has exceeded the number(2) of cases that can be a time of registration.")

    def test_update_additional_info_over_max_char_length(self):
        input_line = get_random_string(3001)
        params = {'update_students_list': input_line,
                  'contract_id': self.contract.id,
                  'additional_info': 'test'}

        self._assert_response_error_json(self._update_additional_info_ajax(params),
                                         "The number of lines per line has exceeded the 3000 characters.")

    def test_update_additional_info_different_id(self):
        additional_info1 = self._create_additional_info(contract=self.contract)
        input_line = u"test_student1@example.com,add1"
        params = {'additional_info': additional_info1.id,
                  'contract_id': self.contract.id,
                  'update_students_list': input_line}

        self._assert_response_error_json(self._update_additional_info_ajax(params),
                                         "New item registered. Please reload browser.")

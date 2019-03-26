# -*- coding: utf-8 -*-
"""
This test is a test of user specified registration
"""
import os
import re
import codecs
from boto import connect_s3
from boto.s3.key import Key
from moto import mock_s3
from moto.s3.models import S3Backend
from collections import OrderedDict
from datetime import datetime
from dateutil.tz import tzutc
from django.test.utils import override_settings

from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from biz.djangoapps.ga_contract.tests.factories import ContractAuthFactory
from biz.djangoapps.ga_contract.models import ContractDetail

from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from biz.djangoapps.gx_register_api.models import APIContractMail
from biz.djangoapps.gx_register_api.tests.factories import APIContractMailFactory, APIGatewayKeyFactory

from biz.djangoapps.util.tests.testcase import BizViewTestBase
from biz.djangoapps.gx_students_register_batch.tests.factories import S3BucketNameFactory

@override_settings(AWS_ACCESS_KEY_ID='apicontractregister', AWS_SECRET_ACCESS_KEY='test')
class StudentRegisterAllAPI(BizViewTestBase, ModuleStoreTestCase, TaskTestMixin):
    """
    This test naming convention is [ra_]
    ra == register all api
    """

    def setUp(self):
        super(StudentRegisterAllAPI, self).setUp()
        self._delete_local_file()

        self.ra_main_org = self._create_organization(org_name='ra_main_org_name',
                                             org_code='ra_main_org_code')
        self.ra_other_org = self._create_organization(org_name='ra_other_org_name',
                                             org_code='ra_other_org_code')
        self.ra_main_user = UserFactory.create(username='abc-ra_main_user', email='ra_main_user@example.com')
        self.ra_sub_user = UserFactory.create(username='abc-ra_sub_user', email='ra_sub_user@example.com')
        self.ra_irregular_user = UserFactory.create(username='a-irregular_user', email='ra_irregular_user@example.com')
        self.ra_other_user = UserFactory.create(username='ra_other_user', email='ra_other_user@example.com')
        self.ra_api_key = APIGatewayKeyFactory.create(api_key='ra_api_key12345', org_id=self.ra_main_org)
        self.bucket_name = S3BucketNameFactory.create(bucket_name='ra-test-bucket', type='student_register_batch')
        self.ra_main_course = CourseFactory.create(
            org=self.ra_main_org.org_code, number='ra_main_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            individual_end_days=10,
        )
        self.ra_main_contract = self._create_contract(
            contract_name='test main contract',
            contractor_organization=self.ra_main_org,
            detail_courses=[self.ra_main_course.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        # Settings when using tasks one line
        self.ra_main_contract_auth = ContractAuthFactory.create(contract=self.ra_main_contract, send_mail=False)

        self.ra_other_course = CourseFactory.create(
            org=self.ra_other_org.org_code, number='ra_other_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            individual_end_days=10,
        )
        self.ra_other_contract = self._create_contract(
            contract_name='test other contract',
            contractor_organization=self.ra_other_org,
            detail_courses=[self.ra_other_course.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        self.ra_main_group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='ra_main_group_name', org=self.ra_main_org,
            created_by=self.user, modified_by=self.user
        )
        self.ra_other_group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='11111', group_name='ra_other_group_name', org=self.ra_other_org,
            created_by=self.user, modified_by=self.user
        )
        self.ra_main_member = MemberFactory.create(
            org=self.ra_main_org,
            group=self.ra_main_group,
            user=self.ra_main_user,
            code='00001',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        self.ra_sub_member = MemberFactory.create(
            org=self.ra_main_org,
            group=self.ra_main_group,
            user=self.ra_sub_user,
            code='00002',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        self.ra_irregular_member = MemberFactory.create(
            org=self.ra_main_org,
            group=self.ra_main_group,
            user=self.ra_irregular_user,
            code='00003',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        self.ra_other_member = MemberFactory.create(
            org=self.ra_other_org,
            group=self.ra_other_group,
            user=self.ra_other_user,
            code='11111',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        self.ra_main_mail = APIContractMailFactory.create(
            contract=self.ra_main_contract,
            mail_type=APIContractMail.API_MAIL_TYPE_REGISTER_NEW_USER,
            mail_subject='Test Subject API student register',
            mail_body='Test Body API student register\n{username}\n{fullname}\n{link_url1}\n{link_url2}\n{contract_name}\n{course_name}\n{Not_defined}',
        )
        self.url = 'http://localhost:8000/biz/register_api/v1.00/enrollment/{}/{}/_all'
        self.not_enough_path_url1 = 'http://localhost:8000/biz/register_api/v1.00/{}/{}/_all'
        self.link_url1 = 'https://gacco.org/auth/login/tpa-saml/?auth_entry=login%26next=xxxx'
        self.link_url2 = 'https://gacco.org/auth/login/tpa-saml/?auth_entry=login%26next=dashboard'
        self.param = OrderedDict({
            'send_mail_flg': '1',
            'link_url1': self.link_url1,
            'link_url2': self.link_url2,
        })
        self.add_full_param = OrderedDict()
        for i in range(1, 11):
            self.add_full_param['add_' + str(i)] = 'value_add_' + str(i)

        self.param_random_position = {
            'send_mail_flg': '1',
            'link_url1': self.link_url1,
            'link_url2': self.link_url2,
        }
        self.add_full_param_random_position = {}
        for i in range(1, 11):
            self.add_full_param_random_position['add_' + str(i)] = 'value_add_' + str(i)
        self.param_random_position.update(self.add_full_param_random_position)
        self.header = {'HTTP_X_API_KEY': self.ra_api_key.api_key}

    def assertHttpBadRequest(self, response):
        """Assert that the given response has the status code 400"""
        self.assertEqual(response.status_code, 400)

    def _create_bucket(self, org_id=0, contract_id=0):
        org_id = str(self.ra_main_org.id) if org_id == 0 else str(org_id)
        contract_id = str(self.ra_main_contract.id) if contract_id == 0 else str(contract_id)
        conn = connect_s3('apicontractregister', 'test')
        try:
            conn.create_bucket('ra-test-bucket')
        except:
            pass
        bucket = conn.get_bucket('ra-test-bucket')
        key = Key(bucket)
        key.key = org_id + '/' + contract_id + '/' + 'input_data/'
        try:
            self._delete_s3_all_key_helper(bucket, key)
        except:
            pass
        key.set_contents_from_string('')
        return bucket, key, org_id, contract_id

    def get_s3_target_key(self, bucket, org_id, contract_id):
        key_list =[]
        for key in bucket.get_all_keys():
            if org_id + '/' + contract_id + '/' + 'input_data/student' in str(key):
                key_list += [key]
        return key_list


    def _delete_s3_all_key_helper(self, bucket, key):
        backend = S3Backend
        backend.delete_key(bucket, key)

    def _delete_local_file(self):
        try:
            for root, y, files in os.walk('/tmp/'):
                for file in files:
                    if file.startswith('student_all') or file.startswith('student_group'):
                        os.remove(root + file)
        except:
            pass

    def _get_split_only_key(self, key):
        return re.split(re.compile(r'[.,\s/]'), re.sub(re.compile(r'[<>:]'), '', str(key)))

    def _get_students_list(self, bucket, org_id, contract_id):
        key_list = self.get_s3_target_key(bucket, org_id, contract_id)
        str_key = self._get_split_only_key(key_list[0])
        students_list = []
        key_list[0].get_contents_to_filename('/tmp/' + str_key[-2] + '.' + str_key[-1])
        try:
            with codecs.open('/tmp/' + str_key[-2] + '.' + str_key[-1], 'r', 'SJIS') as fin:
                for line in fin:
                    students_list.append(line.replace('\r', '').replace('\n', '').replace('"', ''))
        except Exception as e:
            pass
        return [x for x in students_list if x != u''], str_key

    @mock_s3
    def test_register_success_post(self):
        bucket, key, org_id, contract_id = self._create_bucket()

        # method POST success
        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id), self.param, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "Has completed. It will be reflected in tomorrow.", "code": "34"}', response.content)
        students_list, str_key = self._get_students_list(bucket, org_id, contract_id)
        self.assertTrue('student_all_POST' in str_key[-2])
        # send_mail_flg : 1
        self.assertTrue('_1' in str_key[-2])

    @mock_s3
    def test_register_success_post_send_flg_false(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        param = self.param
        param['send_mail_flg'] = '0'

        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id), param,
                                    **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "Has completed. It will be reflected in tomorrow.", "code": "34"}',
                         response.content)
        students_list, str_key = self._get_students_list(bucket, org_id, contract_id)
        self.assertTrue('student_all_POST' in str_key[-2])
        # send_mail_flg : 0
        self.assertTrue('_0' in str_key[-2])

    @mock_s3
    def test_register_success_post_send_flg_other(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        param = self.param
        param['send_mail_flg'] = 'a'

        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id), param,
                                    **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "Has completed. It will be reflected in tomorrow.", "code": "34"}',
                         response.content)
        students_list, str_key = self._get_students_list(bucket, org_id, contract_id)
        self.assertTrue('student_all_POST' in str_key[-2])
        # send_mail_flg : 0
        self.assertTrue('_0' in str_key[-2])

    @mock_s3
    def test_register_success_post_send_flg_none(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        param = self.param
        del param['send_mail_flg']

        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id), param,
                                    **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "Has completed. It will be reflected in tomorrow.", "code": "34"}',
                         response.content)
        students_list, str_key = self._get_students_list(bucket, org_id, contract_id)
        self.assertTrue('student_all_POST' in str_key[-2])
        # send_mail_flg : 0
        self.assertTrue('_0' in str_key[-2])

    @mock_s3
    def test_register_success_delete(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        # method DELETE success
        response = self.client.delete(self.url.format(self.ra_main_org.id, self.ra_main_contract.id), **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "Has completed. It will be reflected in tomorrow.", "code": "34"}', response.content)
        students_list, str_key = self._get_students_list(bucket, org_id, contract_id)
        self.assertTrue('student_all_DELETE' in str_key[-2])
        # send_mail_flg : None
        self.assertTrue('_0' in str_key[-2])
        self.assertEqual(u'email,add_1,add_2,add_3,add_4,add_5,add_6,add_7,add_8,add_9,add_10,link_url1,link_url2',
                         students_list[0])
        self.assertEqual('ra_main_user@example.com,,,,,,,,,,,,', students_list[1])
        self.assertTrue('ra_sub_user@example.com' in students_list[2])
        self.assertTrue('ra_irregular_user@example.com' in students_list[3])
        self.assertEqual([], [x for x in students_list if self.ra_other_user.email in x])

    @mock_s3
    def test_full_param_success(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        # method POST full param random position
        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id),
                                    self.param_random_position, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "Has completed. It will be reflected in tomorrow.", "code": "34"}',
                         response.content)
        students_list, str_key = self._get_students_list(bucket, org_id, contract_id)
        self.assertEqual(4, len(students_list))

        self.assertEqual(u'email,add_1,add_2,add_3,add_4,add_5,add_6,add_7,add_8,add_9,add_10,link_url1,link_url2', students_list[0])
        self.assertTrue('ra_main_user@example.com' in students_list[1])
        self.assertTrue(
            'value_add_1,value_add_2,value_add_3,value_add_4,value_add_5,value_add_6,value_add_7,value_add_8,value_add_9,value_add_10,' in
            students_list[1])
        self.assertTrue('https://gacco.org/auth/login/tpa-saml/?auth_entry=login%26next=xxxx,' in students_list[1])
        self.assertTrue('https://gacco.org/auth/login/tpa-saml/?auth_entry=login%26next=dashboard' in students_list[1])
        self.assertTrue('ra_sub_user@example.com' in students_list[2])
        self.assertTrue('ra_irregular_user@example.com' in students_list[3])

    @mock_s3
    def test_exception(self):
        # Not Exists Bucket
        # method POST
        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id), self.param,
                                    **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "An unexpected error occurred", "code": "23"}', response.content)

        # method DELETE
        response = self.client.delete(self.url.format(self.ra_main_org.id, self.ra_main_contract.id), **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "An unexpected error occurred", "code": "23"}', response.content)

    @mock_s3
    def test_diffs_request_method(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        # request GET
        response = self.client.get(self.url.format(self.ra_main_org.id, self.ra_main_contract.id), **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "Please a method of POST or DELETE", "code": "20"}', response.content)
        # request PUT
        response = self.client.put(self.url.format(self.ra_main_org.id, self.ra_main_contract.id), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "Please a method of POST or DELETE", "code": "20"}', response.content)

    @mock_s3
    def test_register_toothless_url_error(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        # Toothless URL path
        response = self.client.post(self.not_enough_path_url1.format(self.ra_main_org.id, self.ra_main_contract.id), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "not enough url", "code": "21"}', response.content)

        # Toothless URL org_id
        response = self.client.post(
            self.url.format(None, self.ra_main_contract.id), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "not enough url", "code": "21"}', response.content)

        # Toothless URL contract_id
        response = self.client.post(
            self.url.format(self.ra_main_org.id, int()), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error contract.", "code": "12"}', response.content)

    @mock_s3
    def test_register_more_than_param(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        # method POST full param
        self.param.update(self.add_full_param)

        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id),
                                    self.param, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "Has completed. It will be reflected in tomorrow.", "code": "34"}',
                         response.content)
        students_list, str_key = self._get_students_list(bucket, org_id, contract_id)
        self.assertEqual(4, len(students_list))
        self.assertEqual(u'email,add_1,add_2,add_3,add_4,add_5,add_6,add_7,add_8,add_9,add_10,link_url1,link_url2',
                         students_list[0])
        self.assertTrue('ra_main_user@example.com' in students_list[1])
        self.assertTrue('value_add_1,value_add_2,value_add_3,value_add_4,value_add_5,value_add_6,value_add_7,value_add_8,value_add_9,value_add_10,' in students_list[1])

    @mock_s3
    def test_register_toothless_param(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        # method POST full param
        self.param.update(self.add_full_param)

        self.param['add_8'] = ''
        del self.param['add_10']
        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id),
                                    self.param, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "Has completed. It will be reflected in tomorrow.", "code": "34"}',
                         response.content)
        students_list, str_key = self._get_students_list(bucket, org_id, contract_id)
        self.assertEqual(4, len(students_list))
        self.assertEqual(u'email,add_1,add_2,add_3,add_4,add_5,add_6,add_7,add_8,add_9,add_10,link_url1,link_url2',
                         students_list[0])
        self.assertTrue('ra_main_user@example.com' in students_list[1])
        self.assertTrue('value_add_1,value_add_2,value_add_3,value_add_4,value_add_5,value_add_6,value_add_7, ,value_add_9,,' in students_list[1])
        self.assertTrue('value_add_10' not in students_list[1])

    @mock_s3
    def test_register_param_is_diffs_error(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        # Not exists org_id
        response = self.client.post(
            self.url.format(1000, self.ra_main_contract.id), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error organization", "code": "10"}', response.content)

        # other org_id
        response = self.client.post(
            self.url.format(self.ra_other_org.id, self.ra_main_contract.id,
                            self.ra_main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error organization. not exists org_id", "code": "11"}', response.content)

        # Not exists contract_id
        response = self.client.post(
            self.url.format(self.ra_main_org.id, 1000,
                            self.ra_main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error contract.", "code": "12"}', response.content)

        # other contract_id
        response = self.client.post(
            self.url.format(self.ra_main_org.id, self.ra_other_contract.id,
                            self.ra_main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error contract.", "code": "12"}', response.content)

        # other contract_id
        response = self.client.post(
            self.url.format(self.ra_main_org.id, self.ra_other_contract.id,
                            self.ra_main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error contract.", "code": "12"}', response.content)

    @mock_s3
    def test_header_none_or_mismatch(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        # method POST header None
        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id),
                                    self.param)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "not enough url", "code": "21"}', response.content)

        # method POST header mismatch
        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id),
                                    self.param, **{'HTTP_X_API_KEY': 'differ'})
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error organization. not exists org_id", "code": "11"}', response.content)

        # method DELETE header None
        response = self.client.delete(self.url.format(self.ra_main_org.id, self.ra_main_contract.id))
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "not enough url", "code": "21"}', response.content)

        # method DELETE header mismatch
        response = self.client.delete(self.url.format(self.ra_main_org.id, self.ra_main_contract.id), **{'HTTP_X_API_KEY': 'differ'})
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error organization. not exists org_id", "code": "11"}', response.content)

    @mock_s3
    def test_contract_detail_not_settings(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        self.assertTrue(ContractDetail.objects.filter(contract_id=self.ra_main_contract.id))
        ContractDetail.objects.all().delete()
        self.assertFalse(ContractDetail.objects.filter(contract_id=self.ra_main_contract.id))
        response = self.client.post(
            self.url.format(self.ra_main_org.id, self.ra_main_contract.id), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error contract not settings contract details.", "code": "13"}', response.content)

    @mock_s3
    def test_error_add_over_char(self):
        bucket, key, org_id, contract_id = self._create_bucket()
        self.param_random_position['add_1'] = 'a' * 256
        # method POST full param random position
        response = self.client.post(self.url.format(self.ra_main_org.id, self.ra_main_contract.id),
                                    self.param_random_position, **self.header)
        self.assertEqual(400, response.status_code)
        self.assertEqual('{"message": "The number of characters of additional information exceeds 255 characters", "code": "24"}',
                         response.content)

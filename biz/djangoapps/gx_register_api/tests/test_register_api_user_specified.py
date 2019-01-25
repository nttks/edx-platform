# -*- coding: utf-8 -*-
"""
This test is a test of user specified registration
"""
from collections import OrderedDict
from datetime import datetime
from dateutil.tz import tzutc

from mock import patch
from opaque_keys.edx.locator import CourseLocator
from openedx.core.djangoapps.ga_task.tests.test_task import TaskTestMixin
from student.tests.factories import UserFactory
from student.models import CourseEnrollment
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from biz.djangoapps.ga_contract.models import ContractDetail, AdditionalInfo
from biz.djangoapps.ga_contract.tests.factories import ContractAuthFactory
from biz.djangoapps.ga_invitation.models import ContractRegister, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE, AdditionalInfoSetting

from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from biz.djangoapps.gx_register_api.models import APIContractMail, APIGatewayKey
from biz.djangoapps.gx_register_api.tests.factories import APIContractMailFactory, APIGatewayKeyFactory
from biz.djangoapps.gx_sso_config.tests.factories import SsoConfigFactory
from biz.djangoapps.gx_username_rule.tests.factories import OrgUsernameRuleFactory

from biz.djangoapps.util.tests.testcase import BizViewTestBase


class UserSpecifiedRegistrationAPI(BizViewTestBase, ModuleStoreTestCase, TaskTestMixin):

    def setUp(self):
        super(UserSpecifiedRegistrationAPI, self).setUp()

        self.main_org = self._create_organization(org_name='main_org_name',
                                             org_code='main_org_code')
        self.other_org = self._create_organization(org_name='other_org_name',
                                             org_code='other_org_code')
        self.main_user = UserFactory.create(username='abc-main_user', email='main_user@example.com')
        self.sub_user = UserFactory.create(username='abc-sub_user', email='sub_user@example.com')
        self.irregular_user = UserFactory.create(username='a-irregular_user', email='irregular_user@example.com')
        self.other_user = UserFactory.create(username='other_user', email='other_user@example.com')
        self.main_username_rule = OrgUsernameRuleFactory.create(prefix='abc-', org=self.main_org)
        self.main_sso = SsoConfigFactory.create(idp_slug='abcde', org=self.main_org)
        self.api_key = APIGatewayKeyFactory.create(api_key='api_key12345', org_id=self.main_org)
        self.main_course = CourseFactory.create(
            org=self.main_org.org_code, number='main_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            individual_end_days=10,
        )
        self.main_contract = self._create_contract(
            contract_name='test main contract',
            contractor_organization=self.main_org,
            detail_courses=[self.main_course.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        # Settings when using tasks one line
        self.main_contract_auth = ContractAuthFactory.create(contract=self.main_contract, send_mail=False)

        self.other_course = CourseFactory.create(
            org=self.other_org.org_code, number='other_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            individual_end_days=10,
        )
        self.other_contract = self._create_contract(
            contract_name='test other contract',
            contractor_organization=self.other_org,
            detail_courses=[self.other_course.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        self.main_group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='main_group_name', org=self.main_org,
            created_by=self.user, modified_by=self.user
        )
        self.other_group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='11111', group_name='other_group_name', org=self.other_org,
            created_by=self.user, modified_by=self.user
        )
        self.main_member = MemberFactory.create(
            org=self.main_org,
            group=self.main_group,
            user=self.main_user,
            code='00001',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        self.sub_member = MemberFactory.create(
            org=self.main_org,
            group=self.main_group,
            user=self.sub_user,
            code='00002',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        self.irregular_member = MemberFactory.create(
            org=self.main_org,
            group=self.main_group,
            user=self.irregular_user,
            code='00003',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        self.other_member = MemberFactory.create(
            org=self.other_org,
            group=self.other_group,
            user=self.other_user,
            code='11111',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        self.main_mail = APIContractMailFactory.create(
            contract=self.main_contract,
            mail_type=APIContractMail.API_MAIL_TYPE_REGISTER_NEW_USER,
            mail_subject='Test Subject API student register',
            mail_body='Test Body API student register\n{username}\n{fullname}\n{link_url1}\n{link_url2}\n{contract_name}\n{course_name}\n{Not_defined}',
        )
        self.url = 'http://localhost:8000/biz/register_api/v1.00/enrollment/{}/{}/{}'
        self.not_enough_path_url1 = 'http://localhost:8000/biz/register_api/v1.00/{}/{}/{}'
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
        self.header = {'HTTP_X_API_KEY': self.api_key.api_key}

    def assertHttpBadRequest(self, response):
        """Assert that the given response has the status code 400"""
        self.assertEqual(response.status_code, 400)

    def test_register_success(self):
        # method POST success
        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email), self.param, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And send mail.", "code": "30"}', response.content)
        self.assertEqual(REGISTER_INVITATION_CODE, ContractRegister.objects.get(user_id=self.main_user.id).status)
        self.assertEqual(CourseLocator.from_string(u'main_org_code/main_course/run'),
                         CourseEnrollment.objects.get(user_id=self.main_user.id).course_id)
        self.assertEqual(True,
                         CourseEnrollment.objects.get(user_id=self.main_user.id, course_id=CourseLocator.from_string(
                             u'main_org_code/main_course/run')).is_active)
        self.assertEqual(1, len(ContractRegister.objects.all()))
        self.assertEqual(1, len(CourseEnrollment.objects.all()))

        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.sub_user.email), self.param, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: sub_user@example.com register. And send mail.", "code": "30"}', response.content)
        self.assertEqual(REGISTER_INVITATION_CODE, ContractRegister.objects.get(user_id=self.sub_user.id).status)
        self.assertEqual(CourseLocator.from_string(u'main_org_code/main_course/run'),
                         CourseEnrollment.objects.get(user_id=self.main_user.id).course_id)
        self.assertEqual(True,
                         CourseEnrollment.objects.get(user_id=self.sub_user.id, course_id=CourseLocator.from_string(
                             u'main_org_code/main_course/run')).is_active)
        self.assertEqual(2, len(ContractRegister.objects.all()))
        self.assertEqual(2, len(CourseEnrollment.objects.all()))

        # method DELETE success
        response = self.client.delete(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email), **self.header)

        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com unregister.", "code": "33"}', response.content)
        self.assertEqual(UNREGISTER_INVITATION_CODE, ContractRegister.objects.get(user_id=self.main_user.id).status)
        self.assertEqual(CourseLocator.from_string(u'main_org_code/main_course/run'),
                         CourseEnrollment.objects.get(user_id=self.main_user.id).course_id)
        self.assertEqual(False,
                         CourseEnrollment.objects.get(user_id=self.main_user.id, course_id=CourseLocator.from_string(
                             u'main_org_code/main_course/run')).is_active)

    def test_register_create_full_param_success(self):
        # method POST full param random position
        AdditionalInfo.objects.all().delete()
        self.assertEqual(0, len(AdditionalInfo.objects.all()))
        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email),
                                    self.param_random_position, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And send mail.", "code": "30"}',
                         response.content)
        self.assertEqual(REGISTER_INVITATION_CODE, ContractRegister.objects.get(user_id=self.main_user.id).status)
        self.assertEqual(CourseLocator.from_string(u'main_org_code/main_course/run'),
                         CourseEnrollment.objects.get(user_id=self.main_user.id).course_id)
        self.assertEqual(True,
                         CourseEnrollment.objects.get(user_id=self.main_user.id,
                                                      course_id=CourseLocator.from_string(
                                                          u'main_org_code/main_course/run')).is_active)
        self.assertEqual(1, len(ContractRegister.objects.all()))
        self.assertEqual(1, len(CourseEnrollment.objects.all()))
        self.assertEqual(10, len(AdditionalInfo.objects.all()))
        self.assertEqual(1, len(AdditionalInfo.objects.filter(display_name='Additional Info2')))
        self.assertEqual(10, len(AdditionalInfoSetting.objects.all()))
        self.assertEqual('value_add_3', AdditionalInfoSetting.objects.get(display_name='Additional Info3').value)

        # AdditionalInfoSetting update and not send mail
        self.add_full_param_random_position['add_3'] = 'update_add_3'
        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email),
                                    self.add_full_param_random_position, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And not send mail.", "code": "31"}',
                         response.content)
        self.assertEqual(REGISTER_INVITATION_CODE, ContractRegister.objects.get(user_id=self.main_user.id).status)
        self.assertEqual(CourseLocator.from_string(u'main_org_code/main_course/run'),
                         CourseEnrollment.objects.get(user_id=self.main_user.id).course_id)
        self.assertEqual(True,
                         CourseEnrollment.objects.get(user_id=self.main_user.id,
                                                      course_id=CourseLocator.from_string(
                                                          u'main_org_code/main_course/run')).is_active)
        self.assertEqual(1, len(ContractRegister.objects.all()))
        self.assertEqual(1, len(CourseEnrollment.objects.all()))
        self.assertEqual(10, len(AdditionalInfo.objects.all()))
        self.assertEqual(1, len(AdditionalInfo.objects.filter(display_name='Additional Info2')))
        self.assertEqual(10, len(AdditionalInfoSetting.objects.all()))
        self.assertEqual('update_add_3', AdditionalInfoSetting.objects.get(display_name='Additional Info3').value)

    def test_register_add_to_additional_info_records(self):
        # setup data
        self.assertEqual(2, len(AdditionalInfo.objects.filter(contract_id=self.main_contract.id)))
        self.assertEqual(1, len(AdditionalInfo.objects.filter(contract_id=self.main_contract.id, display_name='country')))
        self.assertEqual(0, len(AdditionalInfoSetting.objects.all()))

        self.param.update(self.add_full_param)
        self.param['add_1'] = 'not_update_country'
        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email),
                                    self.param, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And send mail.", "code": "30"}',
                         response.content)
        self.assertEqual(REGISTER_INVITATION_CODE, ContractRegister.objects.get(user_id=self.main_user.id).status)
        self.assertEqual(CourseLocator.from_string(u'main_org_code/main_course/run'),
                         CourseEnrollment.objects.get(user_id=self.main_user.id).course_id)
        self.assertEqual(True,
                         CourseEnrollment.objects.get(user_id=self.main_user.id,
                                                      course_id=CourseLocator.from_string(
                                                          u'main_org_code/main_course/run')).is_active)
        self.assertEqual(1, len(ContractRegister.objects.all()))
        self.assertEqual(1, len(CourseEnrollment.objects.all()))
        self.assertEqual(10, len(AdditionalInfo.objects.filter(contract_id=self.main_contract.id)))
        self.assertEqual(0, len(AdditionalInfo.objects.filter(display_name='Additional Info2')))
        self.assertEqual(1, len(AdditionalInfo.objects.filter(contract_id=self.main_contract.id, display_name='dept')))
        self.assertEqual(10, len(AdditionalInfoSetting.objects.all()))
        self.assertEqual('not_update_country', AdditionalInfoSetting.objects.get(contract_id=self.main_contract.id, display_name='country').value)

    def test_register_more_than_param(self):
        # method POST full param
        AdditionalInfo.objects.all().delete()
        self.assertEqual(0, len(AdditionalInfo.objects.all()))
        self.param.update(self.add_full_param)
        self.param['add_11'] = 'surplus_data_1'
        self.param['add_12'] = 'surplus_data_2'
        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email),
                                    self.param, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And send mail.", "code": "30"}',
                         response.content)
        self.assertEqual(REGISTER_INVITATION_CODE, ContractRegister.objects.get(user_id=self.main_user.id).status)
        self.assertEqual(CourseLocator.from_string(u'main_org_code/main_course/run'),
                         CourseEnrollment.objects.get(user_id=self.main_user.id).course_id)
        self.assertEqual(True,
                         CourseEnrollment.objects.get(user_id=self.main_user.id,
                                                      course_id=CourseLocator.from_string(
                                                          u'main_org_code/main_course/run')).is_active)
        self.assertEqual(1, len(ContractRegister.objects.all()))
        self.assertEqual(1, len(CourseEnrollment.objects.all()))
        self.assertEqual(10, len(AdditionalInfo.objects.all()))
        self.assertEqual(10, len(AdditionalInfoSetting.objects.all()))
        self.assertEqual(0, len(AdditionalInfoSetting.objects.filter(display_name=self.param['add_11'])))

    def test_register_irregular_param_delete(self):
        # method POST full param
        AdditionalInfo.objects.all().delete()
        self.assertEqual(0, len(AdditionalInfo.objects.all()))
        self.param.update(self.add_full_param)
        del self.param['add_2']
        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email),
                                    self.param, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And send mail.", "code": "30"}',
                         response.content)
        self.assertEqual(REGISTER_INVITATION_CODE, ContractRegister.objects.get(user_id=self.main_user.id).status)
        self.assertEqual(CourseLocator.from_string(u'main_org_code/main_course/run'),
                         CourseEnrollment.objects.get(user_id=self.main_user.id).course_id)
        self.assertEqual(True,
                         CourseEnrollment.objects.get(user_id=self.main_user.id,
                                                      course_id=CourseLocator.from_string(
                                                          u'main_org_code/main_course/run')).is_active)
        self.assertEqual(1, len(ContractRegister.objects.all()))
        self.assertEqual(1, len(CourseEnrollment.objects.all()))
        self.assertEqual(10, len(AdditionalInfo.objects.all()))
        self.assertEqual(10, len(AdditionalInfoSetting.objects.all()))
        self.assertFalse(AdditionalInfoSetting.objects.filter(contract_id=self.main_contract.id, value='value_add_2').first())

    def test_register_url_method_delete_fail(self):
        # method DELETE fail. not create register record
        response = self.client.delete(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email), **self.header)

        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "main_user@example.com is not taking classes. Or, attendance registration has been canceled", "code": "19"}', response.content)
        self.assertEqual(0, len(ContractRegister.objects.all()))
        self.assertEqual(0, len(CourseEnrollment.objects.all()))

    def test_diffs_request_method(self):
        # request GET
        response = self.client.get(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email), **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "Please a method of POST or DELETE", "code": "20"}', response.content)
        # request PUT
        response = self.client.put(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "Please a method of POST or DELETE", "code": "20"}', response.content)

    def test_register_toothless_url_error(self):
        # Toothless URL path
        response = self.client.post(self.not_enough_path_url1.format(self.main_org.id, self.main_contract.id, self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "not enough url", "code": "21"}', response.content)

        # Toothless URL user_email
        response = self.client.post(
            self.url.format(self.main_org.id, self.main_contract.id, ''), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "not enough url", "code": "21"}', response.content)

        # Toothless URL org_id
        response = self.client.post(
            self.url.format(None, self.main_contract.id, self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "not enough url", "code": "21"}', response.content)

        # Toothless URL contract_id
        response = self.client.post(
            self.url.format(self.main_org.id, int(), self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error contract.", "code": "12"}', response.content)

        # Toothless URL param send_mail_flg
        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email), {
            'link_url1': self.link_url1,
            'link_url2': self.link_url2,
        }, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And not send mail.", "code": "31"}', response.content)

    def test_register_param_is_diffs_error(self):
        # Not exists org_id
        response = self.client.post(
            self.url.format(1000, self.main_contract.id, self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error organization", "code": "10"}', response.content)

        # other org_id
        response = self.client.post(
            self.url.format(self.other_org.id, self.main_contract.id,
                            self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error organization. not exists org_id", "code": "11"}', response.content)

        # Not exists contract_id
        response = self.client.post(
            self.url.format(self.main_org.id, 1000,
                            self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error contract.", "code": "12"}', response.content)

        # other contract_id
        response = self.client.post(
            self.url.format(self.main_org.id, self.other_contract.id,
                            self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error contract.", "code": "12"}', response.content)

        # Not exists user_email
        response = self.client.post(
            self.url.format(self.main_org.id, self.main_contract.id,
                            'not_exists_user@example.com'), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error user_email: not exists user", "code": "16"}', response.content)

        # other contract_id
        response = self.client.post(
            self.url.format(self.main_org.id, self.other_contract.id,
                            self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error contract.", "code": "12"}', response.content)

        # other user_id
        response = self.client.post(
            self.url.format(self.main_org.id, self.main_contract.id,
                            self.other_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error user_email: not exists member.", "code": "14"}', response.content)

        # irregular user_id
        response = self.client.post(
            self.url.format(self.main_org.id, self.main_contract.id,
                            self.irregular_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error user_email: abc- diffs", "code": "15"}', response.content)

    def test_register_success_pattern(self):
        # post data diffs pattern1
        response = self.client.post(
            self.url.format(self.main_org.id, self.main_contract.id,
                            self.main_user.email), {
                'send_mail_flg': 'a',
                'link_url1': self.link_url1,
                'link_url2': self.link_url2,
            }, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And not send mail.", "code": "31"}',
                         response.content)

        # post data send_mail_flg diffs pattern2
        response = self.client.post(
            self.url.format(self.main_org.id, self.main_contract.id,
                            self.main_user.email), {
                'send_mail_flg': '0',
                'link_url1': self.link_url1,
                'link_url2': self.link_url2,
            }, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And not send mail.", "code": "31"}',
                         response.content)

        # post data send_mail_flg diffs pattern3
        response = self.client.post(
            self.url.format(self.main_org.id, self.main_contract.id,
                            self.main_user.email), {
                'send_mail_flg': '1',
                'link_url2': self.link_url2,
            }, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And send mail.", "code": "30"}',
                         response.content)

        # post data send_mail_flg diffs pattern4
        response = self.client.post(
            self.url.format(self.main_org.id, self.main_contract.id,
                            self.main_user.email), {
                'send_mail_flg': '1',
                'link_url1': self.link_url1,
            }, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And send mail.", "code": "30"}',
                         response.content)

        # post data send_mail_flg diffs pattern5
        response = self.client.post(
            self.url.format(self.main_org.id, self.main_contract.id,
                            self.main_user.email), **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And not send mail.", "code": "31"}',
                         response.content)

    def test_method_post_exception_error(self):
        # method POST
        with patch('biz.djangoapps.gx_register_api.views.CourseEnrollment.enroll',
                   side_effect=Exception):
            response = self.client.post(
                self.url.format(self.main_org.id, self.main_contract.id,
                                self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "ERROR: Did not register main_user@example.com", "code": "17"}',
                         response.content)

    def test_method_delete_exception_error(self):
        # method DELETE
        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email),
                                    self.param, **self.header)
        self.assertEqual(200, response.status_code)
        self.assertEqual('{"message": "You got success! student: main_user@example.com register. And send mail.", "code": "30"}', response.content)

        with patch('biz.djangoapps.gx_register_api.views.ContractRegister.objects.get',
                   side_effect=Exception):
            response = self.client.delete(
                self.url.format(self.main_org.id, self.main_contract.id,
                                self.main_user.email), **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "ERROR: Did not unregister main_user@example.com", "code": "18"}',
                         response.content)

    def test_contract_detail_not_settings(self):
        self.assertTrue(ContractDetail.objects.filter(contract_id=self.main_contract.id))
        ContractDetail.objects.all().delete()
        self.assertFalse(ContractDetail.objects.filter(contract_id=self.main_contract.id))
        response = self.client.post(
            self.url.format(self.main_org.id, self.main_contract.id,
                            self.main_user.email), self.param, **self.header)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error contract not settings contract details.", "code": "13"}', response.content)

    def test_header_none_or_mismatch(self):
        # method POST header None
        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email),
                                    self.param)
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "not enough url", "code": "21"}', response.content)

        # method POST header mismatch
        response = self.client.post(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email),
                                    self.param, **{'HTTP_X_API_KEY': 'differ'})
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error organization. not exists org_id", "code": "11"}', response.content)

        # method DELETE header None
        response = self.client.delete(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email))
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "not enough url", "code": "21"}', response.content)

        # method DELETE header mismatch
        response = self.client.delete(self.url.format(self.main_org.id, self.main_contract.id, self.main_user.email), **{'HTTP_X_API_KEY': 'differ'})
        self.assertHttpBadRequest(response)
        self.assertEqual('{"message": "parameter error organization. not exists org_id", "code": "11"}', response.content)
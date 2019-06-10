"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import os
import re
import csv
import json
import codecs
from boto import connect_s3
from boto.s3.key import Key
from datetime import datetime
from dateutil.tz import tzutc
from mock import patch
from moto import mock_s3
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test.utils import override_settings
from django.utils import translation
from django.utils.translation import ugettext as _

from opaque_keys.edx.locator import CourseLocator
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from openedx.core.djangoapps.ga_task.models import Task

from student.models import CourseEnrollment
from student.tests.factories import UserFactory

from biz.djangoapps.ga_contract.models import AdditionalInfo
from biz.djangoapps.ga_contract.tests.factories import ContractAuthFactory, AdditionalInfoFactory
from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory
from biz.djangoapps.ga_invitation.models import ContractRegister, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE, AdditionalInfoSetting

from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from biz.djangoapps.gx_register_api.tests.factories import APIGatewayKeyFactory, APIContractMailFactory
from biz.djangoapps.gx_register_api.models import APIContractMail
from biz.djangoapps.gx_reservation_mail.models import ReservationMail
from biz.djangoapps.gx_sso_config.tests.factories import SsoConfigFactory
from biz.djangoapps.gx_username_rule.tests.factories import OrgUsernameRuleFactory
from biz.djangoapps.gx_students_register_batch.tests.factories import BatchSendMailFlagFactory, S3BucketNameFactory
from biz.djangoapps.gx_students_register_batch.models import (
    StudentsRegisterBatchHistory, StudentsRegisterBatchTarget
)
from biz.djangoapps.util.tests.testcase import BizViewTestBase




@override_settings(AWS_ACCESS_KEY_ID='contractregister', AWS_SECRET_ACCESS_KEY='test')
class TestStudentRegisterBatchRootAPI(BizViewTestBase, ModuleStoreTestCase):
    """
    This test naming convention is [bra_, bra-, Bra, BRA]
    bra == contract register batch
    example:
    self.bra_bra_main_org
    self.bra_main_contract
    self.bra_user
    """
    def setUp(self):
        super(TestStudentRegisterBatchRootAPI, self).setUp()
        translation.activate('ja')
        CourseGlobalSettingFactory.create(course_id=CourseFactory.create().id)
        self.bucket_name = S3BucketNameFactory.create(bucket_name='bra-test-bucket', type='student_register_batch')
        self.bra_main_org = self._create_organization(org_name='bra_main_org_name',
                                                      org_code='bra_main_org_code')
        self.bra_main_user = UserFactory.create(username='abc-bra_main_user', email='bra_main_user@test.co.jp')
        self.bra_sub_user = UserFactory.create(username='abc-bra_sub_user', email='bra_sub_user@test.co.jp')
        self.bra_irregular_user = UserFactory.create(username='abc-bra_irregular_user', email='bra_irregular_user@test.co.jp')
        self.bra_other_user = UserFactory.create(username='bra_other_user', email='bra_other_user@test.co.jp')
        self.bra_main_username_rule = OrgUsernameRuleFactory.create(prefix='abc-', org=self.bra_main_org)
        self.bra_main_sso = SsoConfigFactory.create(idp_slug='abcde', org=self.bra_main_org)
        self.bra_api_key = APIGatewayKeyFactory.create(api_key='api_key12345', org_id=self.bra_main_org)
        self.bra_main_course = CourseFactory.create(
            org=self.bra_main_org.org_code, number='bra_main_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            individual_end_days=10,
        )
        self.bra_main_contract = self._create_contract(
            contract_name='test main contract',
            contractor_organization=self.bra_main_org,
            detail_courses=[self.bra_main_course.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        # Settings when using tasks one line
        self.bra_main_contract_auth = ContractAuthFactory.create(contract=self.bra_main_contract, send_mail=False)
        self.bra_main_mail_flg = BatchSendMailFlagFactory.create(contract=self.bra_main_contract,
                                                                 send_mail=True)
        self.bra_main_mail = APIContractMailFactory.create(
            contract=self.bra_main_contract,
            mail_type=APIContractMail.API_MAIL_TYPE_REGISTER_NEW_USER,
            mail_subject='Test Subject API student register',
            mail_body='Test Body API student register\n{username}\n{fullname}\n{link_url1}\n{link_url2}\n{contract_name}\n{course_name}\n',
        )
        self.bra_admin_mail = APIContractMailFactory.create(
            contract=self.bra_main_contract,
            mail_type=APIContractMail.API_MAIL_TYPE_ADMINISTRATOR,
            mail_subject='Test Subject API student register',
            mail_body='Test Body API student register\n{current_time}\n{total}\n{succeeded}\n{failed}\n{target_file}\n',
        )
        self.bra_main_group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='bra_main_group_name', org=self.bra_main_org,
            created_by=self.user, modified_by=self.user
        )
        self.bra_main_member = MemberFactory.create(
            org=self.bra_main_org,
            group=self.bra_main_group,
            user=self.bra_main_user,
            code='00001',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        self.bra_sub_member = MemberFactory.create(
            org=self.bra_main_org,
            group=self.bra_main_group,
            user=self.bra_sub_user,
            code='00002',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        self.bra_irregular_member = MemberFactory.create(
            org=self.bra_main_org,
            group=self.bra_main_group,
            user=self.bra_irregular_user,
            code='00003',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )
        display_names = ['additional_' + str(i) for i in range(3, 11)]
        for display_name in display_names:
            AdditionalInfoFactory.create(
                contract=self.bra_main_contract,
                display_name=display_name,
            )

        # other data
        self.bra_other_org = self._create_organization(org_name='bra_other_org_name',
                                                       org_code='bra_other_org_code')
        self.bra_other_course = CourseFactory.create(
            org=self.bra_other_org.org_code, number='bra_other_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            individual_end_days=10,
        )
        self.bra_other_contract = self._create_contract(
            contract_name='test other contract',
            contractor_organization=self.bra_other_org,
            detail_courses=[self.bra_other_course.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        self.bra_other_key = APIGatewayKeyFactory.create(api_key='api_key6789', org_id=self.bra_other_org)
        self.bra_other_mail_flg = BatchSendMailFlagFactory.create(contract=self.bra_other_contract,
                                                                  send_mail=True)
        self.bra_other_group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='11111', group_name='bra_other_group_name', org=self.bra_other_org,
            created_by=self.user, modified_by=self.user
        )
        self.bra_other_member = MemberFactory.create(
            org=self.bra_other_org,
            group=self.bra_other_group,
            user=self.bra_other_user,
            code='11111',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='org1',
        )

        self.error_line = _("Line {line_number}:{message}")

        self.user_data = {}
        self.user_data['main_username'] = 'bra_main_user'
        self.user_data['main_email'] = 'bra_main_user@test.co.jp'
        self.user_data['sub_username'] = 'bra_sub_user'
        self.user_data['sub_email'] = 'bra_sub_user@test.co.jp'
        self.user_data['irregular_username'] = 'bra_irregular_user'
        self.user_data['irregular_email'] = 'bra_irregular_user@test.co.jp'

        self.filename_all_1 = 'student_register_all_POST_201801011001111_1.csv'
        self.filename_all_0 = 'student_register_all_POST_2018010110011112_0.csv'
        self.filename_all_DELETE = 'student_register_all_DELETE_201801011001113_0.csv'
        self.filename_group_1 = 'student_register_group_POST_201801011001114_1.csv'
        self.filename_group_0 = 'student_register_group_POST_201801011001115_0.csv'
        self.filename_all_irregular1 = 'student_register_all_DELETE_201801011001116_1.csv'
        self.filename_group_irregular0 = 'student_register_group_DELETE_201801011001117_0.csv'
        self.filename_group_irregular1 = 'student_register_group_DELETE_201801011001118_1.csv'

        self.filename_order1 = 'student_register_all_POST_201801011001111_1.csv'
        self.filename_order2 = 'student_register_all_DELETE_201801011001112_0.csv'
        self.filename_order3 = 'student_register_all_POST_201801011001113_1.csv'
        self.filename_order4 = 'student_register_all_DELETE_201801011001115_0.csv'

        self.filename_other = 'student_register_other_POST_201801011001111_1.csv'
        self.filename_tsv = 'student_register_all_POST_201801011001111_1.tsv'

        self.header = "Email Address,add_1,add_2,add_3,add_4,add_5,add_6,add_7,add_8,add_9,add_10,link_url1,link_url2".split(',')
        self.min_header = "Email Address,add_1,add_2,add_3,add_4,add_5,link_url1,link_url2".split(',')
        self.utf_header = "\uD867\uDE3D,add_1,add_2,add_3,add_4,add_5,add_6,add_7,add_8,add_9,add_10,link_url1,link_url2".split(',')
        self.value = 'value_1,value_2,value_3,value_4,value_5,value_6,value_7,value_8,value_9,value_10,value_url1,value_url2'.split(',')
        self.main_data = ['bra_main_user@test.co.jp'] + self.value
        self.main_data_sub = ['bra_sub_user@test.co.jp'] + self.value
        self.main_data_irregular = ['bra_irregular_user@test.co.jp'] + self.value

        self.min_data = ['bra_main_user@test.co.jp'] + 'value_1,value_2,value_3,value_4,value_5,value_url1,value_url2'.split(',')
        self.miss_data_email = ['bra_sub_user'] + self.value
        self.miss_data_other_email = ['bra_other_user@test.co.jp'] + self.value
        self.miss_data_not_email = [''] + self.value

        self.data_not_add = 'bra_irregular_user@test.co.jp,,,,,,,,,,,value_url1,value_url2'.split(',')
        self.data_mixed_add = 'bra_irregular_user@test.co.jp,value_1, ,value_3,, ,value_6,,value_8,value_9,value_10,value_url1,value_url2'.split(',')

        self.data_not_link_url1 = 'bra_irregular_user@test.co.jp,value_1,value_2,value_3,value_4,value_5,value_6,value_7,value_8,value_9,value_10,,value_url2'.split(',')
        self.data_not_link_url2 = 'bra_irregular_user@test.co.jp,value_1,value_2,value_3,value_4,value_5,value_6,value_7,value_8,value_9,value_10,value_url1,'.split(',')
        self.data_link_url_not_both = 'bra_irregular_user@test.co.jp,value_1,value_2,value_3,value_4,value_5,value_6,value_7,value_8,value_9,value_10,,'.split(',')

        self.miss_data_not_param = 'bra_irregular_user@test.co.jp,,,,,,,,,,,,'.split(',')

    def tearDown(self):
        try:
            for curDir, dirs, files in os.walk('/tmp/'):
                for file in files:
                    if 'student_register' in file:
                        os.remove('/tmp/' + file)
        except:
            pass
        translation.deactivate_all()

    def _create_s3_key(self, header, rows, files=[], org_id=0, contract_id=0, key='<Key: bra-test-bucket,{}/{}/input_data/>', encode='SJIS'):
        org_id = self.bra_main_org.id if org_id == 0 else org_id
        contract_id = self.bra_main_contract.id if contract_id == 0 else contract_id
        split_key = self._key_split(key.format(str(org_id), str(contract_id)))
        conn = connect_s3('contractregister', 'test')
        try:
            conn.create_bucket(split_key[1])
        except:
            pass
        for file in files:
            with codecs.open('/tmp/' + file, 'w', encode) as f:
                c = csv.writer(f)
                c.writerow(header)
                c.writerows(rows)
            bucket = conn.get_bucket(split_key[1])
            s3key = Key(bucket)
            s3key.key = split_key[2] + '/' + split_key[3] + '/' + split_key[4] + '/' + file
            s3key.set_contents_from_filename('/tmp/' + file)
        return bucket, key

    def _create_bucket(self):
        conn = connect_s3('contractregister', 'test')
        try:
            conn.create_bucket(self.bucket_name.bucket_name)
        except:
            pass

    def _upload_s3_one(self, header, rows, file='', org_id=0, contract_id=0, key='<Key: bra-test-bucket,{}/{}/input_data/>', encode='SJIS'):
        org_id = self.bra_main_org.id if org_id == 0 else org_id
        contract_id = self.bra_main_contract.id if contract_id == 0 else contract_id
        split_key = self._key_split(key.format(str(org_id), str(contract_id)))
        with codecs.open('/tmp/' + file, 'w', encode) as f:
            c = csv.writer(f)
            c.writerow(header)
            c.writerows(rows)
        conn = connect_s3('contractregister', 'test')
        bucket = conn.get_bucket(split_key[1])
        s3key = Key(bucket)
        s3key.key = split_key[2] + '/' + split_key[3] + '/' + split_key[4] + '/' + file
        s3key.set_contents_from_filename('/tmp/' + file)
        return s3key

    def _key_split(self, target_key):
        return re.split(re.compile(r'[.,\s/]'), re.sub(re.compile(r'[<>:]'), '', str(target_key)))

    def _assert_batch_history(self, message=None, delete_flg=True):
        history = StudentsRegisterBatchHistory.objects.filter(message=message).first()
        return True if history else False

    def _assert_task_output_helper(self, contract=None, skipped=0, task_type='student_register_batch', succeeded=0, attempted=0, failed=0, total=0):
        task_histories = ContractTaskHistory.objects.filter(contract=contract)
        for task_history in task_histories:
            task = Task.objects.filter(task_type=task_type, task_id=task_history.task_id).first()
            output = json.loads(task.task_output.decode())
            self.assertEqual(output['skipped'], skipped)
            self.assertEqual(output['succeeded'], succeeded)
            self.assertEqual(output['attempted'], attempted)
            self.assertEqual(output['failed'], failed)
            self.assertEqual(output['total'], total)
        return True

    def _assert_batch_target(self, message='', num=1):
        target = StudentsRegisterBatchTarget.objects.filter(message=message)
        self.assertEqual(len(target), num)

    @mock_s3
    def test_zero_s3_path_record(self):
        conn = connect_s3('contractregister', 'test')
        try:
            conn.create_bucket('test_error_bucketname')
        except:
            pass
        with self.assertRaises(CommandError) as e:
            call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(e.exception.args[0], 'Bucket name is different')
        self.assertTrue(self._assert_batch_history(message='Bucket name is different'))

    @mock_s3
    def test_success_all_POST_1(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_all_1])

        call_command('student_register_batch', '-api_flg=1')

        self.assertTrue(self._assert_batch_history(message='Complete'))
        self._assert_task_output_helper(contract=self.bra_main_contract, succeeded=1, attempted=1, total=1)

        self.assertEqual(REGISTER_INVITATION_CODE, ContractRegister.objects.get(user=self.bra_main_user, contract=self.bra_main_contract).status)
        self.assertEqual(
            'Test Body API student register\n{username}\n{fullname}\n{link_url1}\n{link_url2}\n{contract_name}\n{course_name}\n'.format(
                username=self.bra_main_user.username, fullname=self.bra_main_user.profile.name, link_url1='value_url1',
                link_url2='value_url2', contract_name=self.bra_main_contract.contract_name,
                course_name=self.bra_main_course.display_name), ReservationMail.objects.get(user=self.bra_main_user).mail_body)
        self.assertEqual(1, AdditionalInfo.objects.filter(display_name='country', contract=self.bra_main_contract).count())
        self.assertEqual('value_1', AdditionalInfoSetting.objects.get(display_name='country', user=self.bra_main_user).value)
        self.assertEqual('value_3', AdditionalInfoSetting.objects.get(display_name='additional_3', user=self.bra_main_user).value)

    @mock_s3
    def test_success_all_POST_0(self):
        self.assertEqual(10, AdditionalInfo.objects.filter(contract=self.bra_main_contract).count())
        self._create_s3_key(self.header, [self.main_data], [self.filename_all_0])

        call_command('student_register_batch', '-api_flg=1')

        self.assertTrue(self._assert_batch_history(message='Complete'))
        self._assert_task_output_helper(contract=self.bra_main_contract, succeeded=1, attempted=1, total=1)
        self.assertEqual(0, len(ReservationMail.objects.filter(user=self.bra_main_user)))
        self.assertEqual(REGISTER_INVITATION_CODE, ContractRegister.objects.get(user=self.bra_main_user, contract=self.bra_main_contract).status)
        self.assertEqual(True,
                         CourseEnrollment.objects.get(user_id=self.bra_main_user.id,
                                                      course_id=CourseLocator.from_string(
                                                          u'bra_main_org_code/bra_main_course/run')).is_active)

    @mock_s3
    def test_success_all_DELETE(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_all_DELETE])

        call_command('student_register_batch', '-api_flg=1')
        self.assertTrue(self._assert_batch_history(message='Complete'))
        self._assert_task_output_helper(contract=self.bra_main_contract, task_type='student_unregister_batch', succeeded=1, attempted=1, total=1)

        self.assertEqual(0, len(ReservationMail.objects.filter(user=self.bra_main_user)))
        self.assertEqual(0,
                         ContractRegister.objects.filter(user=self.bra_main_user, contract=self.bra_main_contract, status=UNREGISTER_INVITATION_CODE).count())
        self.assertEqual(0,
                         CourseEnrollment.objects.filter(user_id=self.bra_main_user.id,
                                                      course_id=CourseLocator.from_string(
                                                          u'bra_main_org_code/bra_main_course/run')).count())
        self.assertEqual(0, AdditionalInfoSetting.objects.all().count())

    @mock_s3
    def test_success_group_POST_1(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_group_1])

        call_command('student_register_batch', '-api_flg=1')

        self.assertTrue(self._assert_batch_history(message='Complete'))
        self._assert_task_output_helper(contract=self.bra_main_contract, succeeded=1, attempted=1, total=1)
        self.assertEqual(REGISTER_INVITATION_CODE,
                         ContractRegister.objects.get(user=self.bra_main_user, contract=self.bra_main_contract).status)
        self.assertEqual(
            'Test Body API student register\n{username}\n{fullname}\n{link_url1}\n{link_url2}\n{contract_name}\n{course_name}\n'.format(
                username=self.bra_main_user.username, fullname=self.bra_main_user.profile.name, link_url1='value_url1',
                link_url2='value_url2', contract_name=self.bra_main_contract.contract_name,
                course_name=self.bra_main_course.display_name),
            ReservationMail.objects.get(user=self.bra_main_user).mail_body)

    @mock_s3
    def test_success_group_POST_0(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_group_0])

        call_command('student_register_batch', '-api_flg=1')

        self._assert_task_output_helper(contract=self.bra_main_contract, succeeded=1, attempted=1, total=1)
        self.assertEqual(REGISTER_INVITATION_CODE,
                         ContractRegister.objects.get(user=self.bra_main_user, contract=self.bra_main_contract).status)
        self.assertEqual(0, len(ReservationMail.objects.filter(user=self.bra_main_user)))

    @mock_s3
    def test_irregular_file_1(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_all_irregular1])

        call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(0,
                         ContractRegister.objects.filter(user=self.bra_main_user, contract=self.bra_main_contract).count())
        self.assertEqual(0, ReservationMail.objects.filter(user=self.bra_main_user).count())

    @mock_s3
    def test_irregular_file_2(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_group_irregular0])

        call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(0,
                         ContractRegister.objects.filter(user=self.bra_main_user, contract=self.bra_main_contract).count())
        self.assertEqual(0,
                         CourseEnrollment.objects.filter(user_id=self.bra_main_user.id,
                                                      course_id=CourseLocator.from_string(
                                                          u'bra_main_org_code/bra_main_course/run')).count())


    @mock_s3
    def test_irregular_file_3(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_group_irregular0])
        call_command('student_register_batch', '-api_flg=1')

    @mock_s3
    def test_filename_tsv(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_tsv])
        with self.assertRaises(CommandError) as e:
            call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(e.exception.args[0], 'There is no csv file.')
        self.assertTrue(self._assert_batch_history(message='There is no csv file.'))

    @mock_s3
    def test_s3_not_placed_anything_1(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_all_1], contract_id=100)
        with self.assertRaises(CommandError) as e:
            call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(e.exception.args[0], 'There is no csv file.')
        self.assertTrue(self._assert_batch_history(message='There is no csv file.'))

    @mock_s3
    def test_s3_not_placed_anything_2(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_all_1], org_id=100)
        with self.assertRaises(CommandError) as e:
            call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(e.exception.args[0], 'There is no csv file.')
        self.assertTrue(self._assert_batch_history(message='There is no csv file.'))

    @mock_s3
    def test_error_create_task_record(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_all_1])
        with self.assertRaises(CommandError) as e, patch(
                'biz.djangoapps.gx_students_register_batch.management.commands.student_register_batch.Command.do_create_task_targets_and_get_records',
                side_effect=Exception('error_test')):
            call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(e.exception.args[0], 'Task History create error: error_test')
        self.assertTrue(self._assert_batch_history(message='DB records create error: error_test'))

    @mock_s3
    def test_success_multiple_file(self):
        self._create_bucket()
        self._upload_s3_one(self.header, [self.main_data], self.filename_order1)
        self._upload_s3_one(self.header, [self.main_data], self.filename_order2)
        self._upload_s3_one(self.header, [self.main_data], self.filename_order3)
        self._upload_s3_one(self.header, [self.main_data], self.filename_order4)

        call_command('student_register_batch', '-api_flg=1')

        self.assertTrue(self._assert_batch_history(message='Complete'))
        self.assertEqual(UNREGISTER_INVITATION_CODE,
                         ContractRegister.objects.get(user=self.bra_main_user, contract=self.bra_main_contract).status)
        self.assertEqual(False,
                         CourseEnrollment.objects.get(user_id=self.bra_main_user.id,
                                                      course_id=CourseLocator.from_string(
                                                          u'bra_main_org_code/bra_main_course/run')).is_active)
        self.assertEqual(2, ReservationMail.objects.filter(user=self.bra_main_user).count())

    @mock_s3
    def test_filename_other(self):
        self._create_s3_key(self.header, [self.main_data], [self.filename_other])
        with self.assertRaises(CommandError) as e:
            call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(e.exception.args[0], 'There is no csv file.')
        self.assertTrue(self._assert_batch_history(message='There is no csv file.'))

    @mock_s3
    def test_email_error(self):
        self._create_s3_key(self.header, [self.miss_data_email], [self.filename_all_1])
        call_command('student_register_batch', '-api_flg=1')
        self._assert_batch_target(message=self.error_line.format(line_number=1,
                                                                 message=_("It is not registered as an employee master: {email}").format(email='bra_sub_user')))
        self.assertEqual(0,
                         ContractRegister.objects.filter(user=self.bra_other_user,
                                                         contract=self.bra_main_contract).count())
        self.assertEqual(0,
                         CourseEnrollment.objects.filter(user_id=self.bra_other_user.id,
                                                         course_id=CourseLocator.from_string(
                                                             u'bra_main_org_code/bra_main_course/run')).count())
        self.assertEqual(0, AdditionalInfoSetting.objects.filter(user=self.bra_sub_user).count())

    @mock_s3
    def test_email_error_not_data(self):
        self._create_s3_key(self.header, [self.miss_data_not_email], [self.filename_all_1])
        call_command('student_register_batch', '-api_flg=1')
        self._assert_batch_target(message=self.error_line.format(line_number=1,
                                                                 message=_("It is not registered as an employee master: {email}").format(
                                                                     email='')))
        self.assertEqual(0,
                         ContractRegister.objects.filter(user=self.bra_other_user,
                                                         contract=self.bra_main_contract).count())
        self.assertEqual(0,
                         CourseEnrollment.objects.filter(user_id=self.bra_other_user.id,
                                                         course_id=CourseLocator.from_string(
                                                             u'bra_main_org_code/bra_main_course/run')).count())

    @mock_s3
    def test_success_not_add(self):
        self._create_bucket()
        self._upload_s3_one(self.header, [self.data_not_add], self.filename_all_1)
        call_command('student_register_batch', '-api_flg=1')

        self.assertTrue(self._assert_batch_history(message='Complete'))
        self.assertEqual(1,
                         AdditionalInfo.objects.filter(display_name='country', contract=self.bra_main_contract).count())
        self.assertEqual(0,
                         AdditionalInfoSetting.objects.filter(display_name='country', user=self.bra_irregular_user).count())
        self.assertEqual(0,
                         AdditionalInfoSetting.objects.filter(display_name='additional_3', user=self.bra_irregular_user).count())

    @mock_s3
    def test_success_toothless_add(self):
        self._create_bucket()
        self._upload_s3_one(self.header, [self.main_data_irregular], self.filename_all_1)
        call_command('student_register_batch', '-api_flg=1')

        self.assertTrue(self._assert_batch_history(message='Complete'))
        self.assertEqual(10,
                         AdditionalInfo.objects.filter(contract=self.bra_main_contract).count())
        self.assertEqual('value_1',
                         AdditionalInfoSetting.objects.get(display_name='country',
                                                              user=self.bra_irregular_user).value)
        self.assertEqual('value_2',
                         AdditionalInfoSetting.objects.get(display_name='dept',
                                                              user=self.bra_irregular_user).value)
        self.assertEqual('value_3',
                         AdditionalInfoSetting.objects.get(display_name='additional_3',
                                                              user=self.bra_irregular_user).value)
        self.assertEqual('value_4',
                         AdditionalInfoSetting.objects.get(display_name='additional_4',
                                                           user=self.bra_irregular_user).value)

        self._upload_s3_one(self.header, [self.data_mixed_add], self.filename_all_1)
        call_command('student_register_batch', '-api_flg=1')
        self.assertTrue(self._assert_batch_history(message='Complete'))
        self.assertEqual(10,
                         AdditionalInfo.objects.filter(contract=self.bra_main_contract).count())
        self.assertEqual('value_1',
                         AdditionalInfoSetting.objects.get(display_name='country',
                                                           user=self.bra_irregular_user).value)
        self.assertEqual(' ',
                         AdditionalInfoSetting.objects.get(display_name='dept',
                                                           user=self.bra_irregular_user).value)
        self.assertEqual('value_3',
                         AdditionalInfoSetting.objects.get(display_name='additional_3',
                                                           user=self.bra_irregular_user).value)
        self.assertEqual('value_4',
                         AdditionalInfoSetting.objects.get(display_name='additional_4',
                                                           user=self.bra_irregular_user).value)

    @mock_s3
    def test_link_url(self):
        self._create_bucket()

        self._upload_s3_one(self.header, [self.data_not_link_url1], self.filename_all_1)
        call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(
            'Test Body API student register\n{username}\n{fullname}\n{link_url1}\n{link_url2}\n{contract_name}\n{course_name}\n'.format(
                username=self.bra_irregular_user.username, fullname=self.bra_irregular_user.profile.name, link_url1='',
                link_url2='value_url2', contract_name=self.bra_main_contract.contract_name,
                course_name=self.bra_main_course.display_name),
            ReservationMail.objects.get(id=1).mail_body)

        self._upload_s3_one(self.header, [self.data_not_link_url2], self.filename_all_1)
        call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(
            'Test Body API student register\n{username}\n{fullname}\n{link_url1}\n{link_url2}\n{contract_name}\n{course_name}\n'.format(
                username=self.bra_irregular_user.username, fullname=self.bra_irregular_user.profile.name, link_url1='value_url1',
                link_url2='', contract_name=self.bra_main_contract.contract_name,
                course_name=self.bra_main_course.display_name),
            ReservationMail.objects.get(id=2).mail_body)

        self._upload_s3_one(self.header, [self.data_link_url_not_both], self.filename_all_1)
        call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(
            'Test Body API student register\n{username}\n{fullname}\n{link_url1}\n{link_url2}\n{contract_name}\n{course_name}\n'.format(
                username=self.bra_irregular_user.username, fullname=self.bra_irregular_user.profile.name,
                link_url1='',
                link_url2='', contract_name=self.bra_main_contract.contract_name,
                course_name=self.bra_main_course.display_name),
            ReservationMail.objects.get(id=3).mail_body)

    @mock_s3
    def test_success_not_param(self):
        self._create_bucket()
        self._upload_s3_one(self.header, [self.miss_data_not_param], self.filename_all_1)
        call_command('student_register_batch', '-api_flg=1')

        self.assertTrue(self._assert_batch_history(message='Complete'))
        self.assertEqual(10,
                         AdditionalInfo.objects.filter(contract=self.bra_main_contract).count())
        self.assertEqual(0,
                         AdditionalInfoSetting.objects.filter(display_name='country',
                                                           user=self.bra_irregular_user).count())
        self.assertEqual(
            'Test Body API student register\n{username}\n{fullname}\n{link_url1}\n{link_url2}\n{contract_name}\n{course_name}\n'.format(
                username=self.bra_irregular_user.username, fullname=self.bra_irregular_user.profile.name,
                link_url1='',
                link_url2='', contract_name=self.bra_main_contract.contract_name,
                course_name=self.bra_main_course.display_name),
            ReservationMail.objects.get(id=1).mail_body)

    @mock_s3
    def test_encode_error_not_sjis(self):
        self._create_bucket()
        key = self._upload_s3_one(self.utf_header, [self.main_data], self.filename_all_1, encode='utf-16')
        call_command('student_register_batch', '-api_flg=1')
        self.assertEqual('Encoding specification is a file other than SJIS. s3_key:{}'.format(key.key),
                         StudentsRegisterBatchHistory.objects.get(id=1).message)

    @mock_s3
    def test_s3_upload__error(self):
        self._create_bucket()
        self._upload_s3_one(self.header, [self.main_data], self.filename_all_1)
        with patch(
                'biz.djangoapps.gx_students_register_batch.management.commands.student_register_batch.Command.upload_s3_bucket',
                side_effect=Exception('error_test')):
            call_command('student_register_batch', '-api_flg=1')
        self.assertTrue(self._assert_batch_history(
            message='Could not upload the file to s3, but registration related has been completed : error_test'))

    @mock_s3
    def test_create_additional_info(self):
        self.assertEqual(10, AdditionalInfo.objects.filter(contract=self.bra_main_contract).count())
        AdditionalInfo.objects.all().delete()
        self.assertEqual(0, AdditionalInfo.objects.filter(contract=self.bra_main_contract).count())
        self._create_bucket()
        self._upload_s3_one(self.header, [self.main_data], self.filename_all_1)
        call_command('student_register_batch', '-api_flg=1')

        self.assertTrue(self._assert_batch_history(message='Complete'))
        self.assertEqual(10,
                         AdditionalInfo.objects.filter(contract=self.bra_main_contract).count())
        self.assertEqual(_("Additional Info") + '1',
                         AdditionalInfo.objects.filter(contract=self.bra_main_contract).first().display_name)
        self.assertEqual('value_1',
                         AdditionalInfoSetting.objects.filter(display_name=_("Additional Info") + '1',
                                                              user=self.bra_main_user).first().value)

    @mock_s3
    def test_create_over_additional_info(self):
        self.assertEqual(10, AdditionalInfo.objects.filter(contract=self.bra_main_contract).count())
        AdditionalInfoFactory.create(
            contract=self.bra_main_contract,
            display_name='add_over')
        self.assertEqual(1, AdditionalInfo.objects.filter(contract=self.bra_main_contract, display_name='add_over').count())
        self._create_bucket()
        self._upload_s3_one(self.header, [self.main_data], self.filename_all_1)
        call_command('student_register_batch', '-api_flg=1')

        self.assertTrue(self._assert_batch_history(message='Complete'))
        self.assertEqual(11,
                         AdditionalInfo.objects.filter(contract=self.bra_main_contract).count())
        self.assertEqual(1,
                         AdditionalInfo.objects.filter(contract=self.bra_main_contract, display_name='add_over').count())
        self.assertEqual(10,
                         AdditionalInfoSetting.objects.filter(user=self.bra_main_user).count())
        self.assertEqual(0,
                         AdditionalInfoSetting.objects.filter(display_name='add_over',
                                                              user=self.bra_main_user).count())

    @mock_s3
    def test_email_error_group(self):
        self._create_s3_key(self.header, [self.miss_data_email], [self.filename_group_1])
        call_command('student_register_batch', '-api_flg=1')
        self._assert_batch_target(message=self.error_line.format(line_number=1,
                                                                 message=_(
                                                                     "It is not registered as an employee master: {email}").format(
                                                                     email='bra_sub_user')))
        self.assertEqual(0,
                         ContractRegister.objects.filter(user=self.bra_other_user,
                                                         contract=self.bra_main_contract).count())
        self.assertEqual(0,
                         CourseEnrollment.objects.filter(user_id=self.bra_other_user.id,
                                                         course_id=CourseLocator.from_string(
                                                             u'bra_main_org_code/bra_main_course/run')).count())
        self.assertEqual(0, AdditionalInfoSetting.objects.filter(user=self.bra_other_user).count())

    @mock_s3
    def test_column_length_miss(self):
        self._create_bucket()
        self._upload_s3_one(self.min_header, [self.min_data], self.filename_all_1)
        call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(1,
                         AdditionalInfoSetting.objects.filter(user=self.bra_main_user, value='value_5').count())
        self.assertEqual(0,
                         AdditionalInfoSetting.objects.filter(user=self.bra_main_user, value='value_6').count())
        self.assertEqual(1,
                         AdditionalInfoSetting.objects.filter(user=self.bra_main_user, value='value_url1').count())

    @mock_s3
    @patch('biz.djangoapps.gx_students_register_batch.management.commands.student_register_batch.send_mail')
    def test_administrator_mail(self, count):
        self._create_bucket()
        self._upload_s3_one(self.header, [self.miss_data_email], self.filename_order1)
        self._upload_s3_one(self.header, [self.miss_data_email], self.filename_order2)
        self._upload_s3_one(self.header, [self.miss_data_email], self.filename_order3)
        self._upload_s3_one(self.header, [self.miss_data_email], self.filename_order4)
        call_command('student_register_batch', '-api_flg=1')
        self.assertEqual(1, count.call_count)

    @mock_s3
    def test_error_not_register_admin_mail(self):
        self.bra_admin_mail.delete()
        self._create_bucket()
        self._upload_s3_one(self.header, [self.miss_data_email], self.filename_all_1)

        call_command('student_register_batch', '-api_flg=1')
        self.assertTrue(self._assert_batch_history(message='Processing is completed, but I could not send mail.'))

    @mock_s3
    def test_error_admin_exception(self):
        self._create_bucket()
        self._upload_s3_one(self.header, [self.miss_data_email], self.filename_all_1)
        with patch(
                'biz.djangoapps.gx_students_register_batch.management.commands.student_register_batch.Command.api_send_mail_administrator',
                side_effect=Exception()):
            call_command('student_register_batch', '-api_flg=1')
        self.assertTrue(self._assert_batch_history(
            message='Processing is completed, but I could not send mail.'))
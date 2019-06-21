"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import os
import re
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

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test.utils import override_settings
from django.utils import translation
from django.utils.translation import ugettext as _
from django.db import IntegrityError
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from openedx.core.djangoapps.ga_task.models import Task

from bulk_email.models import Optout
from student.models import CourseEnrollment
from student.tests.factories import UserFactory
from student.views import AccountValidationError

from biz.djangoapps.ga_contract.tests.factories import ContractAuthFactory
from biz.djangoapps.ga_contract.tests.factories import AdditionalInfoFactory
from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory, ContractMail
from biz.djangoapps.ga_contract_operation.tests.factories import ContractMailFactory
from biz.djangoapps.ga_invitation.models import ContractRegister
from biz.djangoapps.ga_login.models import BizUser

from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from biz.djangoapps.gx_register_api.tests.factories import APIGatewayKeyFactory
from biz.djangoapps.gx_reservation_mail.models import ReservationMail
from biz.djangoapps.gx_sso_config.tests.factories import SsoConfigFactory
from biz.djangoapps.gx_username_rule.tests.factories import OrgUsernameRuleFactory
from biz.djangoapps.gx_students_register_batch.tests.factories import BatchSendMailFlagFactory, S3BucketNameFactory
from biz.djangoapps.gx_students_register_batch.models import StudentsRegisterBatchHistory, StudentsRegisterBatchTarget
from biz.djangoapps.util.tests.testcase import BizViewTestBase


@override_settings(AWS_ACCESS_KEY_ID='contractregister', AWS_SECRET_ACCESS_KEY='test')
class TestStudentRegisterBatch(BizViewTestBase, ModuleStoreTestCase):
    """
    This test naming convention is [crb_, crb-, Crb, CRB]
    crb == contract register batch
    example:
    self.crb_crb_main_org
    self.crb_main_contract
    self.crb_user
    """
    def setUp(self):
        super(TestStudentRegisterBatch, self).setUp()

        translation.activate('ja')

        CourseGlobalSettingFactory.create(course_id=CourseFactory.create().id)
        self.bucket_name = S3BucketNameFactory.create(bucket_name='crb-test-bucket', type='student_register_batch')
        self.crb_main_org = self._create_organization(org_name='crb_main_org_name',
                                                      org_code='crb_main_org_code')
        self.crb_other_org = self._create_organization(org_name='crb_other_org_name',
                                                       org_code='crb_other_org_code')
        self.crb_api_org = self._create_organization(org_name='crb_other_org_name',
                                                       org_code='crb_other_org_code')
        self.crb_main_username_rule = OrgUsernameRuleFactory.create(prefix='crb_', org=self.crb_main_org)
        self.crb_main_sso = SsoConfigFactory.create(idp_slug='abcde', org=self.crb_main_org)
        self.crb_api_key = APIGatewayKeyFactory.create(api_key='api_key12345', org_id=self.crb_api_org)
        self.crb_main_course = CourseFactory.create(
            org=self.crb_main_org.org_code, number='crb_main_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            individual_end_days=10,
        )
        self.crb_main_contract = self._create_contract(
            contract_name='test main contract',
            contractor_organization=self.crb_main_org,
            detail_courses=[self.crb_main_course.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        # Settings when using tasks one line
        self.crb_main_contract_auth = ContractAuthFactory.create(contract=self.crb_main_contract, send_mail=False)
        self.crb_main_mail_flg = BatchSendMailFlagFactory.create(contract=self.crb_main_contract,
                                                                    send_mail=True)
        self.crb_other_course = CourseFactory.create(
            org=self.crb_other_org.org_code, number='crb_other_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            individual_end_days=10,
        )
        display_names = ['value' + str(i) for i in range(1, 11)]
        for display_name in display_names:
            AdditionalInfoFactory.create(
                contract=self.crb_main_contract,
                display_name=display_name,
            )
        self.crb_other_contract = self._create_contract(
            contract_name='test other contract',
            contractor_organization=self.crb_other_org,
            detail_courses=[self.crb_other_course.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        self.crb_other_mail_flg = BatchSendMailFlagFactory.create(contract=self.crb_other_contract,
                                                                    send_mail=True)
        # If you decide to use it
        self.crb_main_group = GroupFactory.create(
            parent_id=0, level_no=0, group_code='00001', group_name='crb_main_group_name', org=self.crb_main_org,
            created_by=self.user, modified_by=self.user
        )
        # default contract mail
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_NEW_USER,
            mail_subject='Test Subject New User Without Logincode',
            mail_body='Test Body New User Without Logincode',
        )
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER,
            mail_subject='Test Subject Exists User Without Logincode',
            mail_body='Test Body Exists User Without Logincode',
        )
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE,
            mail_subject='Test Subject New User With Logincode',
            mail_body='Test Body New User With Logincode',
        )
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE,
            mail_subject='Test Subject Exists User With Logincode',
            mail_body='Test Body Exists User With Logincode',
        )

        self.error_line = _("Line {line_number}:{message}")

        self.user_data = {}
        self.user_data['main_username'] = 'crb_main_user'
        self.user_data['main_email'] = 'crb_main_user@test.co.jp'
        self.user_data['main_login'] = 'login_codeCRB'
        self.user_data['sub_username'] = 'crb_sub_user'
        self.user_data['sub_email'] = 'crb_sub_user@test.co.jp'
        self.user_data['sub_login'] = 'login_codeCRB_sub'
        self.user_data['irregular_username'] = 'crb_irregular_user'
        self.user_data['irregular_email'] = 'crb_irregular_user@test.co.jp'
        self.user_data['irregular_login'] = 'login_codeCRB_irregular'

        # Contract have ContractAuth

        self.header = "Email Address,Username,Last Name,First Name,Login Code,Password,Organization Code,Member Code,"
        org_item_str = ''.join(['org' + str(i) + ',' for i in range(1, 11)]) + ''.join(['item' + str(i) + ',' if i < 10 else 'item' + str(i) for i in range(1, 11)]) + '\n\r'
        self.header += org_item_str

        self.main_data = 'crb_main_user@test.co.jp,crb_main_user,MAIN,CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB1,' + org_item_str
        self.append_data_sub = 'crb_sub_user@test.co.jp,crb_sub_user,SUB,CRB,login_codeCRB_sub,Crb123456,org_codeCRB,member_codeCRB2,' + org_item_str
        self.append_data_irregular = 'crb_irregular_user@test.co.jp,crb_irregular_user,IRREGULER,CRB,login_codeCRB_irreguler,Crb123456,org_codeCRB,member_codeCRB2,' + org_item_str


        self.miss_data_email = 'crb_irregular_user,crb_irregular_user,MISS,CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_max_length_first_name = 'crb_irregular_user@test.co.jp,crb_irregular_user,' + 'a' * 255 + 'a' + ',CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_max_length_last_name = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,' + 'a' * 255 + 'a' + ',login_codeCRB,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_max_length_username = 'crb_irregular_user@test.co.jp,' + 'aaa' * 10 + 'a' + ',MAIN,CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB1,' + org_item_str

        self.miss_data_min_length_password = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,CRB,login_codeCRB_irreguler,Crb1234,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_not_upper_password = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,CRB,login_codeCRB_irreguler,crb123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_not_lower_password = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,CRB,login_codeCRB_irreguler,CRB123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_not_digit_password = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,CRB,login_codeCRB_irreguler,CrbCrbCrb,org_codeCRB,member_codeCRB3,' + org_item_str

        self.miss_data_min_length_login_code = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,CRB,C,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_max_length_login_code = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,CRB,' + 'aaa' * 10 + 'a' + ',Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str

        self.miss_data_not_email = ',crb_irregular_user,MISS,CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_not_username = 'crb_irregular_user@test.co.jp,,MISS,CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_not_login_code = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,CRB,,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_not_password = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,CRB,login_codeCRB,,org_codeCRB,member_codeCRB3,' + org_item_str

        self.miss_data_column_over = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,CRB,login_codeCRB_irreguler,Crb123456,org_codeCRB,member_codeCRB3,,' + org_item_str
        self.miss_data_not_enough_column = 'crb_irregular_user@test.co.jp,crb_irregular_user,MISS,CRB,login_codeCRB_irreguler,Crb123456,org_codeCRB,' + org_item_str

        self.miss_data_username_error = 'not_exists_user@test.co.jp,not_exists_user,MISS,CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str

        self.miss_data_in_utf8 = '\u74\u65\u73\u74@test.co.jp,crb_irregular_user,MISS,CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.miss_data_in_utf16 = '\uD867\uDE3D@test.co.jp,crb_irregular_user,MISS,CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str

        self.diffs_data_username = 'crb_irregular_user@test.co.jp,crb_main_user,MISS,CRB,login_codeCRB_irreguler,Crb123456,org_codeCRB,member_codeCRB3,' + org_item_str
        self.diff_data_email_username = 'crb_main_user@test.co.jp,crb_sub_user,MAIN,CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB1,' + org_item_str
        self.diff_data_login_code = 'crb_main_user@test.co.jp,crb_main_user,MAIN,CRB,login_codeCRB_diff,Crb123456,org_codeCRB,member_codeCRB1,' + org_item_str
        self.overlap_data_login_code = 'crb_main_user@test.co.jp,crb_main_user,MAIN,CRB,login_codeCRB_sub,Crb123456,org_codeCRB,member_codeCRB1,' + org_item_str
        self.diff_data_password = 'crb_main_user@test.co.jp,crb_main_user,MAIN,CRB,login_codeCRB,Crb654321,org_codeCRB,member_codeCRB1,' + org_item_str

        self.miss_login_code_overlap = 'crb_sub_user@test.co.jp,crb_sub_user,SUB,CRB,login_codeCRB,Crb123456,org_codeCRB,member_codeCRB2,' + org_item_str
        # Contract doesn't have ContractAuth
        self.min_header = "Email Address,Username,Last Name,First Name,Organization Code,Member Code," + org_item_str
        self.min_data = 'ncrb_other_user@test.co.jp,ncrb_other_user,MAIN,CRB,org_codeCRB,member_codeCRB1,' + org_item_str
        self.min_data_username_error = 'ncrb_other_user@test.co.jp,crb_other_user,MAIN,CRB,org_codeCRB,member_codeCRB1,' + org_item_str

        self.min_header_utf = "\uD867\uDE3D,Username,Last Name,First Name,Organization Code,Member Code," + org_item_str

    def tearDown(self):
        translation.deactivate_all()

    def _create_s3_key(self, header, rows, org_id=0, contract_id=0, key='<Key: crb-test-bucket,{}/{}/input_data/>', file=u'contract_register_batch.csv', encode='SJIS'):
        org_id = self.crb_main_org.id if org_id == 0 else org_id
        contract_id = self.crb_main_contract.id if contract_id == 0 else contract_id
        split_key = self._key_split(key.format(str(org_id), str(contract_id)))
        with codecs.open('/tmp/' + file, 'w', encode) as f:
            f.write(header)
            f.write(rows)

        conn = connect_s3('contractregister', 'test')
        try:
            conn.create_bucket(split_key[1])
        except:
            pass
        bucket = conn.get_bucket(split_key[1])
        s3key = Key(bucket)
        s3key.key = split_key[2] + '/' + split_key[3] + '/' + split_key[4] + '/' + file
        s3key.set_contents_from_filename('/tmp/' + file)
        return bucket, s3key

    def _key_split(self, target_key):
        return re.split(re.compile(r'[.,\s/]'), re.sub(re.compile(r'[<>:]'), '', str(target_key)))

    def _assert_batch_history(self, message=None, delete_flg=True):
        history = StudentsRegisterBatchHistory.objects.filter(message=message).first()
        if history and delete_flg is True:
            history.delete()
            self.assertEqual(0, len(StudentsRegisterBatchHistory.objects.filter(message=message)))
        return True

    def _assert_db_records(self, contract, user_email='crb_main_user@test.co.jp', login_code='login_codeCRB', opt_num=1, biz_num=1, his_num=1, task_num=1, target_num=1, regist_num=1, course_num=1):
        check_user = User.objects.filter(email=user_email).first()
        self.assertEqual(opt_num, len(Optout.objects.filter(user=check_user)))
        self.assertEqual(biz_num, len(BizUser.objects.filter(login_code=login_code)))
        self.assertEqual(his_num,
                         len(ContractTaskHistory.objects.filter(contract=contract, requester=self.user)))
        self.assertEqual(task_num, len(Task.objects.all()))
        self.assertEqual(target_num, len(StudentsRegisterBatchTarget.objects.all()))
        self.assertEqual(regist_num, len(ContractRegister.objects.all()))
        self.assertEqual(course_num, len(CourseEnrollment.objects.all()))


    def _assert_task_output_helper(self, contract=None, skipped=0, succeeded=0, attempted=0, failed=0, total=0):
        task_history = ContractTaskHistory.objects.filter(contract=contract).first()
        task = Task.objects.filter(task_type='student_register_batch', task_id=task_history.task_id).first()
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
        with self.assertRaises(CommandError) as e:
            call_command('student_register_batch')
        self.assertEqual(e.exception.args[0], 'Bucket name is different')
        self.assertTrue(self._assert_batch_history(message='Bucket name is different'))

    @mock_s3
    def test_success_csv_upload_has_contract_auth(self):
        self._create_s3_key(self.header, self.main_data)

        call_command('student_register_batch')

        self._assert_db_records(self.crb_main_contract)
        self.assertTrue(self._assert_batch_history(message='Complete'))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=1, attempted=1, total=1)

    @mock_s3
    def test_success_csv_upload_has_not_contract_auth(self):
        self._create_s3_key(self.min_header, self.min_data, org_id=self.crb_other_org.id, contract_id=self.crb_other_contract.id)

        call_command('student_register_batch')

        self._assert_db_records(contract=self.crb_other_contract, user_email='ncrb_other_user@test.co.jp', opt_num=0, biz_num=0)
        self.assertTrue(self._assert_batch_history(message='Complete'))
        self._assert_task_output_helper(contract=self.crb_other_contract, succeeded=1, attempted=1, total=1)

    @mock_s3
    def test_s3_not_placed_anything(self):
        self._create_s3_key(self.header, self.main_data, contract_id=100)

        call_command('student_register_batch')
        self.assertTrue(self._assert_batch_history(
            message='Target is not exists records: org_id:{org_id} contract_id:{contract_id}'.format(
                        org_id=str(self.crb_main_org), contract_id=str(100)
            )))

    @mock_s3
    def test_s3_not_place_csv_file(self):
        self._create_s3_key(self.header, self.main_data, file='contract_register_batch.tsv')
        with self.assertRaises(CommandError) as e:
            call_command('student_register_batch')
        self.assertEqual(e.exception.args[0], 'There is no csv file.')
        self.assertTrue(self._assert_batch_history(message='There is no csv file.'))

    @mock_s3
    def test_error_create_task_record(self):
        self._create_s3_key(self.header, self.main_data)
        with self.assertRaises(CommandError) as e, patch(
                'biz.djangoapps.gx_students_register_batch.management.commands.student_register_batch.Command.do_create_task_targets_and_get_records',
                side_effect=Exception('error_test')):
            call_command('student_register_batch')
        self.assertEqual(e.exception.args[0], 'Task History create error: error_test')
        self.assertTrue(self._assert_batch_history(message='DB records create error: error_test'))

    @mock_s3
    def test_column_length_miss(self):
        # Have ContractAuth
        self._create_s3_key(self.min_header, self.min_data, org_id=self.crb_other_org.id, contract_id=self.crb_other_contract.id)
        call_command('student_register_batch')
        self.assertTrue(self._assert_batch_history(
            message='The format is wrong. This contract is 28 columns. The file is 26 columns.'))
        # Have'nt ContractAuth
        self._create_s3_key(self.header, self.main_data, org_id=self.crb_other_org.id, contract_id=self.crb_other_contract.id)
        call_command('student_register_batch')
        self.assertTrue(self._assert_batch_history(
            message='The format is wrong. This contract is 26 columns. The file is 28 columns.'))

    @mock_s3
    def test_email_error(self):
        self._create_s3_key(self.header, self.miss_data_email)
        call_command('student_register_batch')
        self._assert_batch_target(message=self.error_line.format(line_number=1,
                                                                 message=_("Invalid email {email}.").format(
                                                                     email='crb_irregular_user')))

    @mock_s3
    def test_name_error_first_and_last(self):
        self._create_s3_key(self.header, self.miss_data_max_length_first_name + self.miss_data_max_length_last_name)
        call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=1, message=_(
                "Name cannot be more than {name_max_length} characters long").format(
                name_max_length=User._meta.get_field('first_name').max_length)))
        self._assert_batch_target(
            message=self.error_line.format(line_number=2, message=_(
                "Name cannot be more than {name_max_length} characters long").format(
                name_max_length=User._meta.get_field('last_name').max_length)))

    @mock_s3
    def test_username_rule_error(self):
        self._create_s3_key(self.header, self.miss_data_username_error)
        call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=1,
                                           message=_("Username {user} already exists.").format(
                                               user='not_exists_user')))

    @mock_s3
    def test_username_error(self):
        self._create_s3_key(self.header, self.main_data + self.append_data_sub + self.append_data_irregular + \
                            self.miss_data_max_length_username + self.diffs_data_username)
        call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=4,
                                           message=_("Username cannot be more than %(limit_value)s characters long") % {
                                               'limit_value': User._meta.get_field('username').max_length}))
        self._assert_batch_target(
            message=self.error_line.format(line_number=5,
                                           message=_(
                                               "Warning, an account with the e-mail {email} exists but the registered username {username} is different.").format(
                                               email=self.user_data['irregular_email'],
                                               username=self.user_data['irregular_username'])))

    @mock_s3
    def test_login_code_overlap_error(self):
        self._create_s3_key(self.header, self.main_data + self.append_data_sub + self.append_data_irregular + \
                            self.diff_data_email_username + self.diff_data_login_code + self.overlap_data_login_code)
        call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=4, message=_(
                    "Warning, an account with the e-mail {email} exists but the registered username {username} is different."
                ).format(email=self.user_data['main_email'], username=self.user_data['main_username'])))
        self._assert_batch_target(
            message=self.error_line.format(line_number=5, message=_(
                "Warning, an account with the e-mail {email} exists but the registered login code {login_code} is different."
            ).format(email=self.user_data['main_email'], login_code=self.user_data['main_login'])))

        self._assert_batch_target(
            message=self.error_line.format(line_number=6, message=_("Login code {login_code} already exists.").format(
                login_code=self.user_data['sub_login'])))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=5, attempted=6, failed=1, total=6)

    @mock_s3
    def test_password_error(self):
        self._create_s3_key(self.header,
                            self.append_data_irregular + \
                            self.miss_data_min_length_password + self.miss_data_not_upper_password + \
                            self.miss_data_not_lower_password + self.miss_data_not_digit_password)
        call_command('student_register_batch')

        self._assert_batch_target(
            message=self.error_line.format(line_number=2, message=_(
                "It includes single-byte uppercase and lowercase letters, numbers, one or more characters")))
        self._assert_batch_target(
            message=self.error_line.format(line_number=3, message=_(
                "It includes single-byte uppercase and lowercase letters, numbers, one or more characters")))
        self._assert_batch_target(
            message=self.error_line.format(line_number=4, message=_(
                "It includes single-byte uppercase and lowercase letters, numbers, one or more characters")))
        self._assert_batch_target(
            message=self.error_line.format(line_number=5, message=_(
                "It includes single-byte uppercase and lowercase letters, numbers, one or more characters")))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=1, attempted=5, failed=4, total=5)


    @mock_s3
    def test_login_code_length(self):
        self._create_s3_key(self.header,
                            self.append_data_irregular + \
                            self.miss_data_min_length_login_code + self.miss_data_max_length_login_code)
        call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=2, message=_("Invalid login code {login_code}.").format(
                        login_code='C')))
        self._assert_batch_target(
            message=self.error_line.format(line_number=3, message=_("Invalid login code {login_code}.").format(
                login_code='aaa' * 10 + 'a')))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=1, attempted=3, failed=2, total=3)

    @mock_s3
    def test_not_enough_data_email(self):
        self._create_s3_key(self.header,
                            self.append_data_irregular + self.miss_data_not_email)
        call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=2, message=_("Invalid email {email}.").format(
                                                                     email=u'')))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=1, attempted=2, failed=1, total=2)
    @mock_s3
    def test_not_enough_data_username(self):
        self._create_s3_key(self.header,
                            self.append_data_irregular + self.miss_data_not_username)
        call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=2,
                                           message=_("Username cannot be more than %(limit_value)s characters long") % {
                                               'limit_value': User._meta.get_field('username').max_length}))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=1, attempted=2, failed=1, total=2)

    @mock_s3
    def test_not_enough_data_login_code(self):
        self._create_s3_key(self.header,
                            self.append_data_irregular + self.miss_data_not_login_code)
        call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=2, message=_("Invalid login code {login_code}.").format(
                        login_code='')))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=1, attempted=2, failed=1, total=2)

    @mock_s3
    def test_not_enough_data_password(self):
        self._create_s3_key(self.header,
                            self.append_data_irregular + self.miss_data_not_password)
        call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=2, message=_(
                "It includes single-byte uppercase and lowercase letters, numbers, one or more characters")))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=1, attempted=2, failed=1, total=2)

    @mock_s3
    def test_over_data_and_min_data(self):
        self._create_s3_key(self.header,
                            self.append_data_irregular + self.miss_data_column_over + self.miss_data_not_enough_column)
        call_command('student_register_batch')

        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=3, attempted=3, failed=0, total=3)

    @mock_s3
    def test_unicode_inclusion(self):
        self._create_s3_key(self.header,
                            self.append_data_irregular + self.miss_data_in_utf8 + self.miss_data_in_utf16)
        call_command('student_register_batch')
        self._assert_batch_target(message=self.error_line.format(line_number=2,
                                                                 message=_("Invalid email {email}.").format(
                                                                     email='\u74\u65\u73\u74@test.co.jp')))
        self._assert_batch_target(message=self.error_line.format(line_number=3,
                                                                 message=_("Invalid email {email}.").format(
                                                                     email='\uD867\uDE3D@test.co.jp')))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=1, attempted=3, failed=2, total=3)

    @mock_s3
    def test_not_exists_user_login_code_error(self):
        self._create_s3_key(self.header,
                            self.main_data + self.miss_login_code_overlap)
        call_command('student_register_batch')
        self._assert_batch_target(message=self.error_line.format(line_number=2,
                                                                 message=_(
                                                                     "Login code {login_code} already exists.").format(
                                                                     login_code=self.user_data['main_login'])))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=1, attempted=2, failed=1, total=2)

    @mock_s3
    def test_encode_error_not_sjis(self):
        __, key = self._create_s3_key(self.min_header_utf,
                            self.min_data, encode='utf-16', org_id=self.crb_other_org.id, contract_id=self.crb_other_contract.id)
        call_command('student_register_batch')
        self.assertEqual('Encoding specification is a file other than SJIS. s3_key:{}'.format(key.key),
                         StudentsRegisterBatchHistory.objects.get(id=1).message)

    @mock_s3
    def test_not_exists_user_username_rule_error(self):
        self._create_s3_key(self.min_header,
                            self.min_data_username_error, org_id=self.crb_other_org.id, contract_id=self.crb_other_contract.id)
        call_command('student_register_batch')
        self._assert_batch_target(message=self.error_line.format(line_number=1,
                                                                 message=_("Username {user} already exists.").format(
                                                                     user='crb_other_user')))
        self._assert_task_output_helper(contract=self.crb_other_contract, succeeded=0, attempted=1, failed=1, total=1)

    @mock_s3
    def test_password_diff_error(self):
        self._create_s3_key(self.header,
                            self.main_data + self.diff_data_password)
        call_command('student_register_batch')
        self._assert_batch_target(message=self.error_line.format(line_number=2,
                                                                 message=_(
                        "Warning, an account with the e-mail {email} exists but the registered password is different.").format(
                        email=self.user_data['main_email'])))
        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=2, attempted=2, failed=0, total=2)

    @mock_s3
    def test_account_validation_error(self):
        self._create_s3_key(self.header, self.main_data)
        with patch(
                'biz.djangoapps.gx_students_register_batch.management.commands.student_register_batch.Command.do_create_auth_user') as mock:
            mock.side_effect = AccountValidationError('error', ValidationError('error_test'))
            call_command('student_register_batch')

        self._assert_batch_target(
            message=self.error_line.format(line_number=1,
                                           message=_("Username {user} already exists.").format(
                                               user=self.user_data['main_username'])))

    @mock_s3
    def test_integrity_error(self):
        self._create_s3_key(self.header, self.main_data)
        with patch(
                'biz.djangoapps.gx_students_register_batch.management.commands.student_register_batch.Command.do_create_auth_user') as mock:
            mock.side_effect=IntegrityError()
            call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=1,
                                           message=_("Username {user} already exists.").format(
                                               user=self.user_data['main_username'])))

    @mock_s3
    def test_validation_error(self):
        self._create_s3_key(self.header, self.main_data)
        with patch(
                'biz.djangoapps.gx_students_register_batch.management.commands.student_register_batch.Command.do_create_auth_user') as mock:
            mock.side_effect=ValidationError('error_test')
            call_command('student_register_batch')
        self._assert_batch_target(
            message=self.error_line.format(line_number=1,
                                           message='error_test'))

    @mock_s3
    def test_register_error(self):
        self._create_s3_key(self.header, self.main_data)
        with patch(
                'biz.djangoapps.gx_students_register_batch.management.commands.student_register_batch.Command.do_register_contract_register',
                side_effect=Exception('error_test')):
            call_command('student_register_batch')
        self.assertTrue(self._assert_batch_history(message='Registration related error: error_test'))
        self._assert_task_output_helper(contract=self.crb_main_contract, skipped=1, succeeded=0, attempted=1, failed=0, total=1)

    @mock_s3
    def test_s3_upload__error(self):
        self._create_s3_key(self.header, self.main_data)
        # with self.assertRaises(CommandError), patch(
        with patch(
                'biz.djangoapps.gx_students_register_batch.management.commands.student_register_batch.Command.upload_s3_bucket',
                side_effect=Exception('error_test')):
            call_command('student_register_batch')
        self.assertTrue(self._assert_batch_history(message='Could not upload the file to s3, but registration related has been completed : error_test'))

    @mock_s3
    def test_not_data_error(self):
        self._create_s3_key('', '')
        call_command('student_register_batch')
        self.assertTrue(
            self._assert_batch_history(message='There is no header line or there is no data.'))

    @mock_s3
    def test_success_has_not_contract_auth(self):
        other_user = UserFactory.create(username='ncrb_other_user', email='ncrb_other_user@test.co.jp')
        self._create_s3_key(self.min_header, self.min_data, org_id=self.crb_other_org.id, contract_id=self.crb_other_contract.id)
        call_command('student_register_batch')
        self.assertTrue(
            self._assert_batch_history(message='Complete'))

    @mock_s3
    def test_not_create_reserve_mail(self):
        self.crb_main_mail_flg.send_mail = False
        self.crb_main_mail_flg.save()
        self.assertEqual(False, self.crb_main_mail_flg.send_mail)
        self._create_s3_key(self.header, self.main_data)

        call_command('student_register_batch')

        self._assert_task_output_helper(contract=self.crb_main_contract, succeeded=1, attempted=1, failed=0, total=1)
        self.assertEqual(0, ReservationMail.objects.all().count())

"""
Management command to student register batch from cron.
"""
import re
import math
import time
import codecs
import logging
import string
import charade
import unicodedata
from boto import connect_s3
from boto.s3.key import Key
from celery.states import SUCCESS
from collections import OrderedDict
from datetime import datetime
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from openedx.core.lib.ga_mail_utils import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction, IntegrityError
from django.utils.translation import ugettext as _
from django.utils import translation

from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress

from bulk_email.models import Optout
from instructor.views.api import generate_unique_password
from student.models import CourseEnrollment
from student.forms import AccountCreationForm
from student.views import _do_create_account, AccountValidationError

from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.task_utils import get_task_key

from biz.djangoapps.ga_contract.models import Contract, ContractDetail, AdditionalInfo
from biz.djangoapps.ga_contract_operation.models import ContractMail, ContractTaskHistory
from biz.djangoapps.ga_invitation.models import ContractRegister, AdditionalInfoSetting, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE
from biz.djangoapps.ga_login.models import BizUser, LOGIN_CODE_MIN_LENGTH, LOGIN_CODE_MAX_LENGTH
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_register_api.models import APIContractMail, APIGatewayKey
from biz.djangoapps.gx_reservation_mail.models import ReservationMail
from biz.djangoapps.gx_students_register_batch.models import (
    BatchSendMailFlag, StudentsRegisterBatchHistory, StudentsRegisterBatchTarget, STUDENT_REGISTER_BATCH, S3BucketName, STUDENT_UNREGISTER_BATCH
)
from biz.djangoapps.gx_username_rule.models import OrgUsernameRule



log = logging.getLogger(__name__)

TARGET_PATH = 'input_data'
BACKUP_PATH = 'backup_data'
LOCAL_DIR = '/tmp/'

FIELD_GROUP_CODE = 'group_code'
FIELD_CODE = 'code'
FIELD_EMAIL = 'email'
FIELD_FIRST_NAME = 'first_name'
FIELD_LAST_NAME = 'last_name'
FIELD_PASSWORD = 'password'
FIELD_USERNAME = 'username'
FIELD_LOGIN_CODE = 'login_code'
FIELD_ORG_NUMBER = 'org'
FIELD_ITEM_NUMBER = 'item'


class Command(BaseCommand):
    help = """
    Usage: python manage.py lms --settings=aws student_register_batch -api_flg=0 or -api_flg=1 -user 
    """
    def add_arguments(self, parser):
        parser.add_argument('-api_flg', required=False, default=0)
        parser.add_argument('-user', required=False, default=1)


    def handle(self, *args, **options):
        translation.activate('ja')
        log.info(u"Command student_register_batch started at {}.".format(datetime_utils.timezone_now()))
        api_flg = options['api_flg']
        requester = options['user']
        sum_mail_body = ''
        try:
            bucket_name = S3BucketName.objects.get(type='student_register_batch').bucket_name
        except Exception as e:
            log.info(e)
            bucket_name = ''
        keys_list, message = self.get_match_to_bucket_records(api_flg, bucket_name)
        if not bool(keys_list):
            self.do_register_batch_report(message=message)
            raise CommandError(message)
        if api_flg == '1':
            keys_list = self._sort_keys_list(keys_list)
        split_keys_str_list = self._get_split_multiple_key(keys_list)

        for key, split_str_key in zip(keys_list, split_keys_str_list):
            date_now = datetime.now().strftime('%Y%m%d%H%M%S%f')[:-5]
            org_id, contract_id = int(split_str_key[2]), int(split_str_key[3])
            split_str_key[-1] = split_str_key[-1].decode('utf-8')
            header, students_list, message = self.download_and_create_student_list(bucket_name, key, date_now)
            if bool(message):
                self.do_register_batch_report(message=message, key=key, org_id=org_id, contract_id=contract_id)
                self.upload_s3_bucket(split_str_key, bucket_name, date_now)
                self._delete_s3_file(split_str_key, bucket_name)
                continue
            if api_flg == '1':
                result = self.check_filename(split_str_key[-1])
                if not result:
                    self.do_register_batch_report(
                        message=u'This file name is not defined:{filename}'.format(filename=split_str_key[-1]), key=key)
                    self.upload_s3_bucket(split_str_key, bucket_name, date_now)
                    self._delete_s3_file(split_str_key, bucket_name)
                    continue

            contract = self.check_db_record(org_id, contract_id)
            if api_flg == '1':
                org = Organization.objects.filter(id=org_id).first()
                member = [x.user.email for x in Member.objects.filter(org=org, is_active=True) if x.user.username.startswith(OrgUsernameRule.objects.filter(org_id=org).first().prefix)]
            if contract is None:
                self.do_register_batch_report(
                    message=u'Target is not exists records: org_id:{org_id} contract_id:{contract_id}'.format(
                        org_id=str(org_id), contract_id=str(contract_id)), key=key)
                self.upload_s3_bucket(split_str_key, bucket_name, date_now)
                self._delete_s3_file(split_str_key, bucket_name)
                continue

            column_length, message = self.validate_header_length(header, contract, api_flg)
            if bool(message):
                self.do_register_batch_report(message=message, key=key, org_id=org_id, contract_id=contract_id)
                self.upload_s3_bucket(split_str_key, bucket_name, date_now)
                self._delete_s3_file(split_str_key, bucket_name)
                continue
            try:
                history, targets = self.do_create_task_targets_and_get_records(contract, api_flg, split_str_key[-1], requester, students_list)
                task = self.do_create_task_record(contract, history, api_flg, split_str_key[-1], requester)
            except Exception as e:
                self.do_register_batch_report(message=u'DB records create error: {}'.format(e), key=key, org_id=org_id, contract_id=contract_id)
                self.upload_s3_bucket(split_str_key, bucket_name, date_now)
                self._delete_s3_file(split_str_key, bucket_name)
                raise CommandError('Task History create error: {}'.format(e))
            task_progress = TaskProgress(STUDENT_REGISTER_BATCH, len(targets), time.time())
            for num, target in enumerate(targets, start=1):
                with transaction.atomic():
                    try:
                        task_progress.attempt()
                        student_dict = self.get_change_list_to_dict(target.student, column_length, api_flg)
                        if api_flg == '1':
                            message, user, contract_mail, replace_dict = self.root_api_validate(contract, split_str_key[-1], member, **student_dict)
                        else:
                            message, user, contract_mail, replace_dict = self.do_validate(contract, **student_dict)
                        if user is None:
                            task_progress.fail()
                            target.complete(_("Line {line_number}:{message}").format(line_number=num,
                                                                                     message=message))
                        else:
                            self.do_register_contract_register(user, contract, split_str_key[-1], api_flg)
                            self.do_register_student_enrollment(user, contract, split_str_key[-1], api_flg)

                            if api_flg == '1' and 'POST' in split_str_key[-1]:
                                self.do_register_additional_info(contract)
                                self.do_register_additional_info_setting(contract, user, **student_dict)
                            self.do_register_reservation_send_mail(user, contract, contract_mail, api_flg, split_str_key[-1], replace_dict)
                            task_progress.success()
                            target.complete(_("Line {line_number}:{message}").format(line_number=num,
                                                                                     message=message) if message else '')
                    except Exception as e:
                        log.info(e)
                        task_progress.skip()
                        self.do_register_batch_report(message=u'Registration related error: {}'.format(e), key=key, org_id=org_id, contract_id=contract_id)
                        target.incomplete(_("Line {line_number}:{message}").format(
                            line_number=num,
                            message=_("The Server Encountered an Error")
                        ))
                log.info(_("Line {line_number}:{message}").format(line_number=num,
                                                                  message=message) if message else '')
            # Task update SUCCESS
            self.do_update_success_current_task(task, task_progress)
            if api_flg == '1':
                try:
                    sum_mail_body = self._create_administrator_mail(task_progress, split_str_key, contract, sum_mail_body)
                except Exception as e:
                    log.info(e)
                    self.do_register_batch_report(message=u'Processing is completed, but I could not send mail.', key=key, org_id=org_id,
                                                  contract_id=contract_id)

            try:
                self.upload_s3_bucket(split_str_key, bucket_name, date_now)
                self._delete_s3_file(split_str_key, bucket_name)
                self.do_register_batch_report(message='Complete', key=key, org_id=org_id, contract_id=contract_id)

            except Exception as e:
                log.info(e)
                self.do_register_batch_report(message=u'Could not upload the file to s3, but registration related has been completed : {}'.format(e), key=key, org_id=org_id, contract_id=contract_id)
            log.info(u"Complete file:{}, {}.".format(key, datetime_utils.timezone_now()))
        if api_flg == '1' and sum_mail_body != '':
            try:
                self.api_send_mail_administrator(sum_mail_body)
            except Exception as e:
                log.info(e)
                self.do_register_batch_report(message='Processing is completed, but I could not send mail.')
        translation.deactivate_all()
        log.info(u"Command student_register_batch completed at {}.".format(datetime_utils.timezone_now()))

    def _fail(self, message):
        return (message, None, None, None)

    def _get_split_multiple_key(self, keys_list):
        """
        Absolutely only a list of csv files, only a list of tsv files
        example:
        keys=[<Key: test,aaa.csv >, <Key: test,bbb.csv >, <Key: test,aaa.jpeg >]
        if keys_to_csv_or_tsv == 'csv':
            return [['test', 'aaa', 'csv'], ['test', 'bbb', 'csv']]
        if keys_to_csv_or_tsv == 'tsv':
            return [['test', 'aaa', 'tsv'], ['test', 'bbb', 'tsv']]
        :return: type: list(list(str()))
        """
        return [['', ''] + re.split(re.compile(r'[/]'), key.encode('utf-8')) for key in keys_list]

    def _get_split_only_key(self, key):
        return ['', ''] + re.split(re.compile(r'[/]'), key.encode('utf-8'))

    def _sort_keys_list(self, keys_list):
        str_times_list = sorted([x[-21:-6] for x in keys_list])
        return [key for str_time in str_times_list for key in keys_list if str_time in key]

    def get_match_to_bucket_records(self, api_flg, bucket_name):
        """
        It is a function to get a key list by matching.
        and Register for attending api In order to use it even for all registration, we make branches and use it

        :return:
        exists_bucket_key_list -> type: list, element type: <class 'boto.resultset.ResultSet'>
        not_exists_buckets -> type: list, element type: <class 'django.db.models.query.QuerySet'>
        # """
        conn = connect_s3(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
        # conn = connect_s3()
        key_list = []
        try:
            for key in conn.get_bucket(bucket_name).get_all_keys():
                split_key = self._get_split_only_key(key.name)
                if api_flg == '1':
                    if len(split_key) == 6 and split_key[2].isdigit() and split_key[3].isdigit() and split_key[4] == TARGET_PATH and split_key[-1].endswith('csv'):
                        if 'all' in split_key[-1] or 'group' in split_key[-1]:
                            api_object = APIGatewayKey.objects.filter(org_id=Organization.objects.filter(id=int(split_key[2])).first()).first()
                            contract_ids = [int(x['id']) for x in Contract.objects.filter(contractor_organization=api_object.org_id).values('id')] if bool(api_object) else []
                            if int(split_key[3]) in contract_ids:
                                key_list += [key.name]
                else:
                    if len(split_key) == 6 and split_key[2].isdigit() and split_key[3].isdigit() and split_key[4] == TARGET_PATH and split_key[-1].endswith('csv'):
                        if not APIGatewayKey.objects.filter(org_id=Organization.objects.filter(id=split_key[2]).first()).exists():
                            key_list += [key.name]
        except Exception as e:
            log.info(e)
            return [], 'Bucket name is different'
        return key_list, 'There is no csv file.'

    def upload_s3_bucket(self, split_str_key, bucket_name, date_now):
        conn = connect_s3(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
        # conn = connect_s3()
        bucket = conn.get_bucket(bucket_name)
        upload_key = Key(bucket)
        upload_key.key = split_str_key[2] + '/' + split_str_key[3] + '/' + BACKUP_PATH + '/' + split_str_key[-1]

        upload_key.set_contents_from_filename('/tmp/batch_student_ja_change' + date_now + '.csv')
        return u'{} file uploading is complete'.format(split_str_key[-1])

    def _delete_s3_file(self, split_str_key, bucket_name):
        conn = connect_s3(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
        # conn = connect_s3()
        bucket = conn.get_bucket(bucket_name)
        key = Key(bucket)
        key.key = split_str_key[2] + '/' + split_str_key[3] + '/' + split_str_key[4] + '/' + split_str_key[-1]
        if key.exists():
            key.delete()
        return True

    def download_and_create_student_list(self, bucket_name, key_name, date_now):
        students_list = []
        conn = connect_s3(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
        # conn = connect_s3()
        bucket = conn.get_bucket(bucket_name)
        key = Key(bucket)
        key.key = key_name
        key.get_contents_to_filename('/tmp/batch_student_ja_change' + date_now + '.csv')
        try:
            f = open('/tmp/batch_student_ja_change' + date_now + '.csv', 'r')
            check_str = f.read()
            f.close()
            if 'UTF' in charade.detect(check_str).get('encoding', '').upper():
                log.info(u'Encoding specification is a file other than SJIS. s3_key:{}'.format(key_name))
                return [], [], u'Encoding specification is a file other than SJIS. s3_key:{key}'.format(key=key_name)

            with codecs.open('/tmp/batch_student_ja_change' + date_now + '.csv', 'r', 'SJIS') as fin:
                for line in fin:
                    students_list.append(line.replace('\r', '').replace('\n', '').replace('"', ''))
        except Exception as e:
            log.info(e)
            log.error(u'Encoding specification is a file other than SJIS. s3_key:{}'.format(key_name))
            return [], [], u'Encoding specification is a file other than SJIS. s3_key:{key}'.format(key=key_name)

        students_list = [x for x in students_list if x]

        if students_list and len(students_list) >= 2:
            return students_list[0].rstrip(',') if students_list[0].endswith(',') else students_list[0], students_list[1:], ''
        else:
            return [], [], u'There is no header line or there is no data.'

    def check_filename(self, filename):
        if 'DELETE' in filename and filename.endswith('_1.csv'):
            return False
        if 'group' in filename and 'DELETE' in filename:
            return False
        return True

    def check_db_record(self, org_id, contract_id):
        try:
            return Contract.objects.get(id=contract_id, contractor_organization_id=org_id)
        except Exception as e:
            log.info(e)
            return None

    def validate_header_length(self, header, contract, api_flg):
        if api_flg == '1':
            return [len(header.split()), '']
        else:
            if contract.has_auth:
                return [28, ''] if len(header.split(',')) == 28 else [0, u'The format is wrong. This contract is 28 columns. The file is {} columns.'.format(len(header.split(',')))]
            else:
                return [26, ''] if len(header.split(',')) == 26 else [0, u'The format is wrong. This contract is 26 columns. The file is {} columns.'.format(len(header.split(',')))]

    def do_register_batch_report(self, key=u'', org_id=None, contract_id=None, message=u''):

        history = StudentsRegisterBatchHistory.objects.create(
            key=key,
            message=message,
            org_id=org_id,
            contract_id=contract_id,
        )
        history.save()
        return True

    def get_change_list_to_dict(self, student, column_length, api_flg):
        student = [x for x in student.split(',') if x != '\n']
        student_dict = {}
        if api_flg == '1':
            student_dict[FIELD_EMAIL] = student[1]
            try:
                for i in range(1, 11):
                    if len(student) <= i + 1:
                        break
                    student_dict['add_' + str(i)] = student[i + 1]
            except Exception as e:
                log.info(e)
                pass
            student_dict['link_url1'] = student[-2]
            student_dict['link_url2'] = student[-1]
            return student_dict
        if column_length == 26:
            student[5:5] = [u'', u'']
        student_dict[FIELD_EMAIL] = student[1]
        student_dict[FIELD_USERNAME] = student[2]
        student_dict[FIELD_LAST_NAME] = student[3]
        student_dict[FIELD_FIRST_NAME] = student[4]
        student_dict[FIELD_LOGIN_CODE] = student[5]
        student_dict[FIELD_PASSWORD] = student[6]
        student_dict[FIELD_GROUP_CODE] = student[7]
        student_dict[FIELD_CODE] = student[8]
        try:
            for i in range(1, 11):
                student_dict[FIELD_ORG_NUMBER + str(i)] = student[i + 8]
            for i in range(1, 11):
                student_dict[FIELD_ITEM_NUMBER + str(i)] = student[i + 18]
        except Exception as e:
            log.info(e)
            pass
        return student_dict

    def do_validate(self, contract, **student_dict):
        messages = []
        password = ''
        contract_register_same_login_code = None
        # validate email
        try:
            validate_email(student_dict[FIELD_EMAIL])
        except Exception as e:
            log.info(e)
            return self._fail(_("Invalid email {email}.").format(email=student_dict[FIELD_EMAIL]))

        # validate first_name and last_name
        name_max_length = User._meta.get_field('first_name').max_length
        if len(student_dict[FIELD_LAST_NAME]) > name_max_length or len(
                student_dict[FIELD_FIRST_NAME]) > name_max_length:
            return self._fail(_(
                "Name cannot be more than {name_max_length} characters long").format(
                name_max_length=name_max_length))

        # validate username
        if student_dict[FIELD_USERNAME] == u'' or len(student_dict[FIELD_USERNAME]) > User._meta.get_field('username').max_length:
            return self._fail(_("Username cannot be more than %(limit_value)s characters long") % {'limit_value': name_max_length})

        if contract.has_auth:
            # validate login_code
            if not re.match(r'^[-\w]{{{min_length},{max_length}}}$'.format(
                    min_length=LOGIN_CODE_MIN_LENGTH, max_length=LOGIN_CODE_MAX_LENGTH),
                    student_dict[FIELD_LOGIN_CODE]):
                return self._fail(_("Invalid login code {login_code}.").format(
                    login_code=student_dict[FIELD_LOGIN_CODE]))

            # Get contract register by login code for after-validate.
            contract_register_same_login_code = ContractRegister.get_by_login_code_contract(
                student_dict[FIELD_LOGIN_CODE], contract)

        if User.objects.filter(email=student_dict[FIELD_EMAIL]).exists():
            user = User.objects.get(email=student_dict[FIELD_EMAIL])
            if user.username != student_dict[FIELD_USERNAME]:
                messages.append(_(
                    "Warning, an account with the e-mail {email} exists but the registered username {username} is different."
                ).format(email=student_dict[FIELD_EMAIL], username=user.username))
                log.warning(u'email {email} already exist, but username is different.'.format(email=student_dict[FIELD_EMAIL]))
            if contract.has_auth:
                # validate password
                if self._password_validate_origin(student_dict[FIELD_PASSWORD]) is False:
                    return self._fail(
                        _("It includes single-byte uppercase and lowercase letters, numbers, one or more characters"))
                password = student_dict[FIELD_PASSWORD]

            # Create BizUser?
            if contract.has_auth:
                # validate duplicate login_code in contract
                if contract_register_same_login_code and contract_register_same_login_code.user.id != user.id:
                    return self._fail(_("Login code {login_code} already exists.").format(login_code=student_dict[FIELD_LOGIN_CODE]))

                biz_user, __ = BizUser.objects.get_or_create(user=user, defaults={'login_code': student_dict[FIELD_LOGIN_CODE]})
                if biz_user.login_code != student_dict[FIELD_LOGIN_CODE]:
                    log.warning(u'email {email} already exist, but login code is different.'.format(email=student_dict[FIELD_EMAIL]))
                    messages.append(_("Warning, an account with the e-mail {email} exists but the registered login code {login_code} is different.").format(
                        email=student_dict[FIELD_EMAIL], login_code=biz_user.login_code))
                if authenticate(username=user.username, password=student_dict[FIELD_PASSWORD]) is None:
                    log.warning(u'email {email} already exist, but password is different.'.format(email=student_dict[FIELD_EMAIL]))
                    messages.append(_(
                        "Warning, an account with the e-mail {email} exists but the registered password is different.").format(
                        email=student_dict[FIELD_EMAIL]))

                contract_mail = ContractMail.get_register_existing_user_logincode(contract)
            else:
                contract_mail = ContractMail.get_register_existing_user(contract)
        else:
            # validate duplicate login_code in contract
            if FIELD_LOGIN_CODE in student_dict and contract_register_same_login_code:
                return self._fail(_("Login code {login_code} already exists.").format(login_code=student_dict[FIELD_LOGIN_CODE]))
            if not OrgUsernameRule.exists_org_prefix(org=contract.contractor_organization.id, str=student_dict[FIELD_USERNAME]):
                return self._fail(_("Username {user} already exists.").format(user=student_dict[FIELD_USERNAME]))
            try:
                user, password = self.do_create_auth_user(student_dict)
                # Create BizUser?
                if contract.has_auth:
                    BizUser.objects.create(user=user, login_code=student_dict[FIELD_LOGIN_CODE])
                    # Optout of bulk email(Global Courses) for only new user.
                    for global_course_id in CourseGlobalSetting.all_course_id():
                        Optout.objects.get_or_create(user=user, course_id=global_course_id)
            except (IntegrityError, AccountValidationError):
                return self._fail(_("Username {user} already exists.").format(user=student_dict[FIELD_USERNAME]))
            except ValidationError as ex:
                return self._fail(' '.join(ex.messages))

            if contract.has_auth:
                contract_mail = ContractMail.get_register_new_user_logincode(contract)
            else:
                contract_mail = ContractMail.get_register_new_user(contract)



        return (
            ''.join(messages),
            user,
            contract_mail,
            ContractMail.register_replace_dict(user, contract, password, student_dict[FIELD_LOGIN_CODE])
        )

    def _get_replaced_progress_dict(self, task_progress):
        return OrderedDict({
            'skipped': task_progress.skipped,
            'succeeded': task_progress.succeeded,
            'attempted': task_progress.attempted,
            'action_name': task_progress.action_name,
            'failed': task_progress.failed,
            'duration_ms': int((time.time() - task_progress.start_time) * 1000),
            'total': task_progress.total,
        })

    def do_update_success_current_task(self, task, task_progress):
        task.task_output = task.create_output_for_success(self._get_replaced_progress_dict(task_progress))
        task.task_state = SUCCESS
        task.save_now()
        return True

    def do_register_contract_register(self, user, contract, filename, api_flg):
        if api_flg == '1' and not bool(ContractRegister.objects.filter(user=user, contract=contract)) and 'DELETE' in filename:
            return False
        register, __ = ContractRegister.objects.get_or_create(user=user, contract=contract)
        register.status = REGISTER_INVITATION_CODE if 'DELETE' not in filename else UNREGISTER_INVITATION_CODE
        register.save()
        return True

    def do_register_student_enrollment(self, user, contract, filename, api_flg):
        for detail in ContractDetail.objects.filter(contract=contract):
            if api_flg == '1' and 'DELETE' in filename:
                if not bool(CourseEnrollment.objects.filter(course_id=detail.course_id, user=user)):
                    continue
                CourseEnrollment.unenroll(user, detail.course_id)
            else:
                CourseEnrollment.enroll(user, detail.course_id)

    def do_register_additional_info(self, contract):
        info_length = len(AdditionalInfo.objects.filter(contract=contract))
        for i in range(1 + info_length, 11):
            additional_info, created = AdditionalInfo.objects.get_or_create(contract=contract, display_name=_("Additional Info") + str(i))
            additional_info.save()

    def do_register_additional_info_setting(self, contract, user, **student_dict):
        additional_info = AdditionalInfo.objects.filter(contract=contract)
        for i in range(0, len(additional_info)):
            if i + 1 == 11:
                break
            if student_dict['add_' + str(i + 1)] != '':
                additional_info_setting, __ = AdditionalInfoSetting.objects.get_or_create(
                    contract=contract,
                    display_name=additional_info[i].display_name,
                    user=user,
                )

                additional_info_setting.value = student_dict['add_' + str(i + 1)]
                additional_info_setting.save()

    def do_register_reservation_send_mail(self, user, contract, contract_mail, api_flg, filename, replace_dict):
        if api_flg == '1':
            if 'POST' not in filename or filename.endswith('_0.csv') or not bool(contract_mail):
                return False
        else:
            if not BatchSendMailFlag.objects.filter(contract=contract, send_mail=True).exists():
                return False
        mail_body = contract_mail.mail_body
        for k, v in replace_dict.iteritems():
            mail_body = mail_body.replace('{{{0}}}'.format(k), str(v).decode('utf-8'))
        ReservationMail.objects.create(
            user=user,
            org=contract.contractor_organization,
            mail_subject=contract_mail.mail_subject,
            mail_body=mail_body
        )
        return True

    def do_create_task_targets_and_get_records(self, contract, api_flg, filename, requester, students):
        big_to_print = []
        for student in students:
            big_to_print += [student + ',\n']
        if api_flg == '1' and 'DELETE' in filename:
            targets = [u'{},{}'.format(UNREGISTER_INVITATION_CODE, s) for s in big_to_print]
        else:
            targets = [u'{},{}'.format(REGISTER_INVITATION_CODE, s) for s in big_to_print]
        history = ContractTaskHistory.create(contract, User.objects.get(id=requester))
        history.save()
        task_target_max_num = 1000
        for i in range(1, int(math.ceil(float(len(targets)) / task_target_max_num)) + 1):
            StudentsRegisterBatchTarget.bulk_create(
                history, targets[(i - 1) * task_target_max_num:i * task_target_max_num])
        log.info('register_students_batch_csv_ajax_:task_id' + str(history.id))
        registered_targets = StudentsRegisterBatchTarget.objects.filter(history_id=history.id)
        return history, registered_targets

    def do_create_task_record(self, contract, history, api_flg, filename, requester):
        task_input = OrderedDict({
            'contract_id': str(contract.id),
            'history_id': history.id,
        })
        if api_flg == '1' and 'DELETE' in filename:
            task = Task.create(task_type=STUDENT_UNREGISTER_BATCH,
                               task_key=get_task_key(contract),
                               task_input=task_input,
                               requester=User.objects.filter(id=requester).first())
        else:
            task = Task.create(task_type=STUDENT_REGISTER_BATCH,
                               task_key=get_task_key(contract),
                               task_input=task_input,
                               requester=User.objects.filter(id=requester).first())
        task.save()
        history.link_to_task(task)
        return task

    def do_create_auth_user(self, student_dict):
        password = student_dict[FIELD_PASSWORD] or generate_unique_password([])

        form = AccountCreationForm(
            data={
                'username': student_dict[FIELD_USERNAME],
                'email': student_dict[FIELD_EMAIL],
                'password': password,
                'name': student_dict[FIELD_LAST_NAME] + student_dict[FIELD_FIRST_NAME],
            },
            tos_required=False
        )
        user, __, registration = _do_create_account(form)

        user.first_name = student_dict[FIELD_FIRST_NAME]
        user.last_name = student_dict[FIELD_LAST_NAME]
        user.save()
        registration.activate()

        return user, password

    def check_japanese(self, string):
        for ch in string:
            name = unicodedata.name(unicode(ch))
            if "CJK UNIFIED" in name or "HIRAGANA" in name or "KATAKANA" in name:
                return True
        return False

    def _password_validate_origin(self, password):
        if len(password) < 8 or self.check_japanese(password):
            return False
        upper = [p for p in password if p in string.ascii_lowercase]
        lower = [p for p in password if p in string.ascii_uppercase]
        digit = [p for p in password if p in string.digits]
        return True if upper and lower and digit else False

    def root_api_validate(self, contract, filename, member, **student_dict):
        if not student_dict[FIELD_EMAIL]:
            return self._fail(
                _("It is not registered as an employee master: {email}").format(email=student_dict[FIELD_EMAIL]))
        message, replace_dict = '', None
        if 'group' in filename and 'POST' in filename:
            if student_dict[FIELD_EMAIL] not in member:
                return self._fail(_("It is not registered as an employee master: {email}").format(email=student_dict[FIELD_EMAIL]))
            else:
                user = User.objects.filter(email=student_dict[FIELD_EMAIL]).first()
        else:
            user = User.objects.filter(email=student_dict[FIELD_EMAIL]).first()
        if not bool(user):
            return self._fail(
                _("It is not registered as an employee master: {email}").format(email=student_dict[FIELD_EMAIL]))
        contract_mail = APIContractMail.get_register_mail(contract)
        if bool(contract_mail):
            course = CourseOverview.get_from_id(contract.details.first().course_id)
            replace_dict = APIContractMail.register_replace_dict(
                                user=user,
                                fullname=user.profile.name,
                                link_url1=student_dict['link_url1'],
                                link_url2=student_dict['link_url2'],
                                contract_name=contract.contract_name,
                                course_name=course.display_name
                            )
        return message, user, contract_mail, replace_dict

    def api_send_mail_administrator(self, sum_mail_body):
        admin_mail = APIContractMail.objects.filter(mail_type='API_ADM').first()
        send_mail(
            admin_mail.user,
            admin_mail.mail_subject,
            sum_mail_body,
        )

    def _create_administrator_mail(self, result, file_path, contract, sum_mail_body):
        error_file = file_path[2] + '/' + file_path[3] + '/' + BACKUP_PATH + '/' + file_path[-1]
        if result.failed > 0:
            admin_mail = APIContractMail.objects.filter(mail_type='API_ADM').first()
            replace_dict = APIContractMail.register_replace_dict_admin(
                result,
                error_file,
                contract.id
            )
            mail_body = admin_mail.mail_body
            for k, v in replace_dict.iteritems():
                mail_body = mail_body.replace('{{{0}}}'.format(k), str(v).decode('utf-8'))
            sum_mail_body += mail_body
        return sum_mail_body

"""
Management command to register member data from cron.
"""
from django.core.management.base import BaseCommand, CommandError
from binascii import Error
from bulk_email.models import Optout
from django.db import transaction
from django.conf import settings
from django.contrib.auth.models import User
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_member.forms import MemberUserCreateForm
from biz.djangoapps.gx_username_rule.models import OrgUsernameRule
from biz.djangoapps.gx_sso_config.models import SsoConfig
from biz.djangoapps.gx_org_group.models import Group
from lms.djangoapps.instructor.views.api import generate_unique_password
from social.apps.django_app.default.models import UserSocialAuth
from student.forms import AccountCreationForm
from student.views import _do_create_account
from student.models import UserProfile, CourseEnrollment
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from boto import connect_s3
from boto.s3.key import Key
from zipfile import ZipFile
import codecs
import logging
import re
import os

log = logging.getLogger(__name__)
s3_directory = 'input_data/01_member/'
s3_report_directory = 'output_data/01_member/'


class Command(BaseCommand):
    help = """
    Usage: python manage.py lms --settings=aws auto_member_register [--debug]
    """
    s3_bucket_name, sso_prefix, non_sso_prefix, register_superuser_id, register_org_id = '', '', '', 0, 0

    def add_arguments(self, parser):
        parser.add_argument('-bucket', required=True)
        parser.add_argument('-prefix', required=True)
        parser.add_argument('-prefix2', required=True)
        parser.add_argument('-user', required=True)
        parser.add_argument('-org', required=True)

    def handle(self, *args, **options):
        start_time = datetime_utils.timezone_now()
        log.info(u"Command auto_member_register started at {}.".format(start_time))
        s3_bucket_name = options['bucket']
        sso_prefix = options['prefix']
        non_sso_prefix = options['prefix2']
        register_superuser_id = int(options['user'])
        register_org_id = int(options['org'])

        def _s3bucket_connection():
            try:
                conn = connect_s3()
                # conn = connect_s3(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
                bucket = conn.get_bucket(s3_bucket_name)
            except Exception as e:
                log.error(e)
                raise CommandError("Could not establish a connection to S3 for file download. Check your credentials.")
            return bucket

        def _s3file_list_get(non_sso=False):
            # S3 Connect
            bucket = _s3bucket_connection()
            # S3 Latest CsvFile Check
            if non_sso:
                s3items = [s3item.name.replace(s3_directory, '') for s3item in
                           bucket.list(s3_directory + non_sso_prefix + '_')]
                s3items = [s3item for s3item in s3items if
                           re.match(non_sso_prefix + '_\d{4}-\d{1,2}-\d{1,2}-\d{4}_\d{2}.zip', s3item)]
            else:
                s3items = [s3item.name.replace(s3_directory, '') for s3item in
                           bucket.list(s3_directory + sso_prefix + '_')]
                s3items = [s3item for s3item in s3items if
                           re.match(sso_prefix + '_\d{4}-\d{1,2}-\d{1,2}-\d{4}_\d{2}.zip', s3item)]
            s3items.reverse()
            s3items = [s3item for s3item in s3items if re.match(s3items[0][:-6], s3item)]
            s3items.sort()

            s3target = []
            for s3item in s3items:
                s3key = Key(bucket)
                s3key.key = s3_report_directory + '01_success/' + s3item[:-4] + '.csv'
                if not s3key.exists():
                    s3target.append(s3item)

            return s3target

        def _s3file_download_read(def_s3item):
            csv_list = []
            # S3 Connect
            bucket = _s3bucket_connection()
            # S3 CsvFile Read
            s3key = Key(bucket)
            s3key.key = s3_directory + def_s3item
            s3key.get_contents_to_filename('/tmp/' + def_s3item)
            with ZipFile('/tmp/' + def_s3item, 'r') as existing_zip:
                existing_zip.extract(def_s3item[:-4] + '.csv', '/tmp/')
            with codecs.open('/tmp/' + def_s3item[:-4] + '.csv', 'r', 'utf8') as fin:
                for line in fin:
                    csv_list.append(line.replace("\r", "").replace("\n", ""))
            if os.path.exists('/tmp/' + def_s3item):
                os.remove('/tmp/' + def_s3item)
            if os.path.exists('/tmp/' + def_s3item[:-4] + '.csv'):
                os.remove('/tmp/' + def_s3item[:-4] + '.csv')

            csv_list = [x for x in csv_list if x]
            return csv_list[1:]

        def _member_validate(def_csv_records, non_sso=False):
            organization = Organization.objects.get(id=register_org_id)
            prefix_username = OrgUsernameRule.objects.filter(org=organization).first()
            prefix_username = getattr(prefix_username, "prefix", "")
            success, errors = [], []
            for csv_record_str in def_csv_records:
                csv_record = csv_record_str.split(',')
                member_one = dict()
                member_one['group_code'] = csv_record[0]
                member_one['code'] = csv_record[1]
                member_one['email'] = csv_record[2]
                member_one['first_name'] = csv_record[3]
                member_one['last_name'] = csv_record[4]
                member_one['username'] = csv_record[5]
                if not member_one['first_name']:
                    errors.append({'username': member_one['username'], 'email': member_one['email']})
                    continue
                if not member_one['last_name']:
                    errors.append({'username': member_one['username'], 'email': member_one['email']})
                    continue
                if prefix_username and not re.match(r'^'+prefix_username, member_one['username']):
                    errors.append({'username': member_one['username'], 'email': member_one['email']})
                    continue
                if member_one['group_code']:
                    if not Group.objects.filter(org=organization, group_code=member_one['group_code']).exists():
                        errors.append({'username': member_one['username'], 'email': member_one['email']})
                        continue
                if member_one['code'] and len(member_one['code']) > 60:
                    errors.append({'username': member_one['username'], 'email': member_one['email']})
                    continue

                if non_sso:
                    member_one['password'] = csv_record[6]
                    if not member_one['password']:
                        errors.append({'username': member_one['username'], 'email': member_one['email']})
                        continue
                    for i in range(1, 11):
                        member_one['org' + str(i)] = csv_record[i + 6]
                    for i in range(1, 11):
                        member_one['item' + str(i)] = csv_record[i + 16]
                else:
                    member_one['password'] = generate_unique_password(generated_passwords=[])
                    for i in range(1, 11):
                        member_one['org' + str(i)] = csv_record[i + 5]
                    for i in range(1, 11):
                        member_one['item' + str(i)] = csv_record[i + 15]

                form = MemberUserCreateForm(member_one)
                if form.is_valid():
                    success.append(form.cleaned_data)
                else:
                    errors.append({'username': member_one['username'], 'email': member_one['email']})
            return success, errors

        def _member_create_or_update(def_register_list):
            success, errors = [], []
            organization = Organization.objects.get(id=register_org_id)
            superuser = User.objects.get(id=register_superuser_id)
            prefix_uid = SsoConfig.objects.filter(org=organization).first()
            prefix_uid = getattr(prefix_uid, "idp_slug", "")
            for register_data in def_register_list:
                try:
                    with transaction.atomic():
                        # auth_user create or update
                        user = User.objects.filter(username=register_data['username'])
                        if user.exists():
                            # user exist
                            user = user.first()
                            user.email = register_data['email']
                        else:
                            # user not exist
                            user, __, __ = _simple_create_user(register_data['email'], register_data['username'],
                                                               register_data['password'], register_data['first_name'],
                                                               register_data['last_name'])
                        user.first_name = register_data['first_name']
                        user.last_name = register_data['last_name']
                        user.save()

                        # gx_member_member create or update
                        member = Member.objects.filter(user=user, is_active=True, org=organization)
                        if member.exists():
                            # member exist
                            member = member.first()
                            member.code = register_data['code']
                        else:
                            # member not exist
                            member = Member.objects.create(org=organization, user=user,
                                                           code=register_data['code'], created_by=superuser,
                                                           creator_org=organization)
                        if register_data['group_code']:
                            member.group = Group.objects.filter(org=organization,
                                                                group_code=register_data['group_code']).first()
                        member.updated_by = superuser
                        member.updated_org = organization
                        for i in range(1, 11):
                            setattr(member, 'org'+str(i), register_data['org'+str(i)])
                        for i in range(1, 11):
                            setattr(member, 'item'+str(i), register_data['item'+str(i)])

                        member.save()

                        # auth_userprofile create or update
                        profile = UserProfile.objects.filter(user=user)
                        if profile.exists():
                            # profile exist
                            profile = profile.first()
                            profile.name = User(first_name=register_data['first_name'],
                                                last_name=register_data['last_name']).get_full_name()
                            profile.save()

                        # social_auth_usersocialauth create
                        if prefix_uid:
                            UserSocialAuth.objects.filter(provider='tpa-saml',
                                                          uid=prefix_uid + ':' + register_data['code']).exclude(
                                user=user).delete()
                            UserSocialAuth.objects.get_or_create(user=user, provider='tpa-saml',
                                                                 uid=prefix_uid + ':' + register_data['code'])
                        # bulk_email_optout create
                        for global_course_id in CourseGlobalSetting.all_course_id():
                            Optout.objects.get_or_create(user=user, course_id=global_course_id)
                            CourseEnrollment.enroll(user, global_course_id)
                            CourseEnrollment.unenroll(user, global_course_id)
                        success.append(register_data['username'])
                except Exception as e:
                    log.error(e)
                    errors.append({'username': register_data['username'], 'email': register_data['email']})
            return success, errors

        def _s3report_upload(def_s3item, total_cnt, success_cnt, errors):
            report_path_success = '/tmp/' + def_s3item[:-4] + '_success.csv'
            # with open(report_path_success, mode='w') as f:
            with codecs.open(report_path_success, 'w', 'utf8') as f:
                f.write("Total :  " + str(total_cnt) + "\r\n")
                f.write("Successful :  " + str(success_cnt) + "\r\n")
                f.write("Failed :  " + str(len(errors)) + "\r\n")
            report_path_error = '/tmp/' + def_s3item[:-4] + '_errors.csv'
            # with open(report_path_error, mode='w') as f:
            with codecs.open(report_path_error, 'w', 'utf8') as f:
                f.write("username,email\r\n")
                for error in errors:
                    f.write(error['username'] + "," + error['email'] + "\r\n")

            # S3 Connect
            bucket = _s3bucket_connection()
            s3key = Key(bucket)
            # success report upload
            s3key.key = s3_report_directory + '01_success/' + def_s3item[:-4] + '.csv'
            s3key.set_contents_from_filename(report_path_success)
            # error report upload
            if errors:
                s3key.key = s3_report_directory + '02_error/' + def_s3item[:-4] + '.csv'
                s3key.set_contents_from_filename(report_path_error)
            # local report delete
            if os.path.exists(report_path_success):
                os.remove(report_path_success)
            if os.path.exists(report_path_error):
                os.remove(report_path_error)

            result_report = "File:" + def_s3item + "(Total:" + str(total_cnt) + " Successful:" + str(
                success_cnt) + " Failed:" + str(len(errors)) + ")\\n"
            return result_report

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
            return user, profile, registration

        result = "Auto Member Register Batch: Complete(Started at {0:%Y/%m/%d %H:%M:%S}) \\n".format(start_time)
        # SSO csv register
        try:
            s3items = _s3file_list_get()
            for s3item in s3items:
                csv_records = _s3file_download_read(s3item)
                register_list, errors_list = _member_validate(csv_records)
                success_list, errors_list2 = _member_create_or_update(register_list)
                result += _s3report_upload(s3item, len(csv_records), len(success_list), errors_list + errors_list2)
        except Exception as ex:
            result += str(ex) + "\\n"
        # Non SSO csv register
        try:
            s3items = _s3file_list_get(non_sso=True)
            for s3item in s3items:
                csv_records = _s3file_download_read(s3item)
                register_list, errors_list = _member_validate(csv_records, non_sso=True)
                success_list, errors_list2 = _member_create_or_update(register_list)
                result += _s3report_upload(s3item, len(csv_records), len(success_list), errors_list + errors_list2)
        except Exception as ex:
            result += str(ex) + "\\n"

        end_time = datetime_utils.timezone_now()
        log.info(u"Command auto_member_register completed at {}.".format(end_time))
        return result


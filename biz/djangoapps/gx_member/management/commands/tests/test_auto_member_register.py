"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_sso_config.models import SsoConfig
from biz.djangoapps.gx_username_rule.models import OrgUsernameRule
from biz.djangoapps.util.tests.testcase import BizViewTestBase
from boto import connect_s3
from boto.s3.key import Key
from bulk_email.models import Optout
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test.utils import override_settings
from moto import mock_s3
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from social.apps.django_app.default.models import UserSocialAuth
from student.models import UserProfile, CourseEnrollment
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
import codecs
import os
from zipfile import ZipFile, ZIP_DEFLATED
from StringIO import StringIO


class TestArgParsing(BizViewTestBase, ModuleStoreTestCase):
    def setUp(self):
        super(BizViewTestBase, self).setUp()
        self.gacco_organization = Organization(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,  # It means the first of Organization
            created_by=UserFactory.create(),
        )
        self.gacco_organization.save()
        self.username_rule = OrgUsernameRule.objects.create(org=self.gacco_organization, prefix='PRE-')
        self.username_rule.save()
        self.sso_config = SsoConfig.objects.create(org=self.gacco_organization, idp_slug="TES")
        self.sso_config.save()
        CourseGlobalSettingFactory.create(course_id=CourseFactory.create().id)

    @override_settings(AWS_ACCESS_KEY_ID='foobar', AWS_SECRET_ACCESS_KEY='bizbaz')
    def test_command_non_arguments(self):
        with self.assertRaises(CommandError) as ce:
            call_command('auto_member_register')
        raise_except = ce.exception
        self.assertEqual(raise_except.args[0], "Error: argument -bucket is required")

    @mock_s3
    @override_settings(AWS_ACCESS_KEY_ID='foobar', AWS_SECRET_ACCESS_KEY='bizbaz')
    def test_command_insert_success(self):
        conn = connect_s3('foobar', 'bizbaz')
        conn.create_bucket('test-bucket')
        bucket = conn.get_bucket('test-bucket')
        s3key = Key(bucket)

        member_csv = "sso_member_2000-01-01-0000_01.csv"
        with codecs.open('/tmp/' + member_csv, 'w', 'utf8') as fou:
            fou.write("[Header],MemberCode,eMail.LastName,FirstName,Username,org1,,,,,,,,,item1,,,,,,,,,\r\n")
            fou.write(
                ",MemberCode1,hoge1@mail.com,Lname1,Fname1,PRE-username1,"
                "org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
        with ZipFile('/tmp/' + member_csv[:-4] + '.zip', 'w', ZIP_DEFLATED) as create_zip:
            create_zip.write('/tmp/' + member_csv, member_csv)
        s3key.key = "input_data/01_member/" + member_csv[:-4] + '.zip'
        s3key.set_contents_from_filename("/tmp/" + member_csv[:-4] + '.zip')
        if os.path.exists("/tmp/" + member_csv):
            os.remove("/tmp/" + member_csv)
        if os.path.exists("/tmp/" + member_csv[:-4] + '.zip'):
            os.remove("/tmp/" + member_csv[:-4] + '.zip')

        member_csv = "no_sso_member_2000-01-01-0000_01.csv"
        with codecs.open('/tmp/' + member_csv, 'w', 'utf8') as fou:
            fou.write("[Header],MemberCode,eMail.LastName,FirstName,Username,pwd,org1,,,,,,,,,item1,,,,,,,,,\r\n")
            fou.write(",MemberCode2,hoge2@mail.com,Lname2,Fname2,PRE-username2,Password"
                      ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
        with ZipFile('/tmp/' + member_csv[:-4] + '.zip', 'w', ZIP_DEFLATED) as create_zip:
            create_zip.write('/tmp/' + member_csv, member_csv)
        s3key.key = "input_data/01_member/" + member_csv[:-4] + '.zip'
        s3key.set_contents_from_filename("/tmp/" + member_csv[:-4] + '.zip')
        if os.path.exists("/tmp/" + member_csv):
            os.remove("/tmp/" + member_csv)
        if os.path.exists("/tmp/" + member_csv[:-4] + '.zip'):
            os.remove("/tmp/" + member_csv[:-4] + '.zip')

        call_command('auto_member_register', '-bucket=test-bucket', '-prefix=sso_member',
                     '-prefix2=no_sso_member', '-user=1', '-org='+str(self.gacco_organization.id))

        # SSO target
        reg_user = User.objects.filter(username="PRE-username1").first()
        self.assertEqual(reg_user.email, "hoge1@mail.com")
        reg_userprofile = UserProfile.objects.filter(user=reg_user).first()
        self.assertEqual(reg_userprofile.name, "Lname1 Fname1")
        reg_member = Member.objects.filter(user=reg_user).first()
        self.assertEqual(reg_member.code, "MemberCode1")
        reg_socialauth = UserSocialAuth.objects.filter(user=reg_user).first()
        self.assertEqual(reg_socialauth.uid, "TES:MemberCode1")
        reg_optout = Optout.objects.filter(user=reg_user).first()
        self.assertEqual(reg_optout.user_id, reg_user.id)
        reg_success_data = bucket.lookup(
            key_name="output_data/01_member/01_success/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_success_data, "Total :  1\r\nSuccessful :  1\r\nFailed :  0\r\n")

        # Non SSO target
        reg_user = User.objects.filter(username="PRE-username2").first()
        self.assertEqual(reg_user.email, "hoge2@mail.com")
        reg_userprofile = UserProfile.objects.filter(user=reg_user).first()
        self.assertEqual(reg_userprofile.name, "Lname2 Fname2")
        reg_member = Member.objects.filter(user=reg_user).first()
        self.assertEqual(reg_member.code, "MemberCode2")
        reg_socialauth = UserSocialAuth.objects.filter(user=reg_user).first()
        self.assertEqual(reg_socialauth.uid, "TES:MemberCode2")
        reg_optout = Optout.objects.filter(user=reg_user).first()
        self.assertEqual(reg_optout.user_id, reg_user.id)
        reg_unenrollment = CourseEnrollment.objects.filter(user=reg_user, mode="audit", is_active=0).first()
        self.assertEqual(reg_unenrollment.user_id, reg_user.id)
        reg_success_data = bucket.lookup(
            key_name="output_data/01_member/01_success/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_success_data, "Total :  1\r\nSuccessful :  1\r\nFailed :  0\r\n")

    @mock_s3
    @override_settings(AWS_ACCESS_KEY_ID='foobar', AWS_SECRET_ACCESS_KEY='bizbaz')
    def test_command_update_success(self):
        user = User.objects.create_user("PRE-username1", "edx1@mail.com", "pwd1")
        Member.objects.create(org=self.gacco_organization, org1="abc1", item1="def1", user=user, code="Code1",
                              created_by=user, creator_org=self.gacco_organization)
        UserProfile.objects.create(user=user)
        UserSocialAuth.objects.get_or_create(user=user, provider='tpa-saml',
                                             uid="TEST:PRE-username1")
        user = User.objects.create_user("PRE-username2", "edx2@mail.com", "pwd2")
        Member.objects.create(org=self.gacco_organization, org1="abc2", item1="def2", user=user, code="Code2",
                              created_by=user, creator_org=self.gacco_organization)
        UserProfile.objects.create(user=user)
        UserSocialAuth.objects.get_or_create(user=user, provider='tpa-saml',
                                             uid="TEST:PRE-username2")
        Group.objects.create(
            parent_id=-1, level_no=-1,
            group_code='0001', group_name='hoge',
            notes='hoge', org=self.gacco_organization, created_by=user
        )

        conn = connect_s3('foobar', 'bizbaz')
        conn.create_bucket('test-bucket')
        bucket = conn.get_bucket('test-bucket')
        s3key = Key(bucket)

        member_csv = "sso_member_2000-01-01-0000_01.csv"
        with codecs.open('/tmp/' + member_csv, 'w', 'utf8') as fou:
            fou.write("[Header],MemberCode,eMail.LastName,FirstName,Username,org1,,,,,,,,,item1,,,,,,,,,\r\n")
            fou.write(
                ",MemberCode1,hoge1@mail.com,Lname1,Fname1,PRE-username1,"
                "org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
        with ZipFile('/tmp/' + member_csv[:-4] + '.zip', 'w', ZIP_DEFLATED) as create_zip:
            create_zip.write('/tmp/' + member_csv, member_csv)
        s3key.key = "input_data/01_member/" + member_csv[:-4] + '.zip'
        s3key.set_contents_from_filename("/tmp/" + member_csv[:-4] + '.zip')
        if os.path.exists("/tmp/" + member_csv):
            os.remove("/tmp/" + member_csv)
        if os.path.exists("/tmp/" + member_csv[:-4] + '.zip'):
            os.remove("/tmp/" + member_csv[:-4] + '.zip')

        member_csv = "no_sso_member_2000-01-01-0000_01.csv"
        with codecs.open('/tmp/' + member_csv, 'w', 'utf8') as fou:
            fou.write("[Header],MemberCode,eMail.LastName,FirstName,Username,pwd,org1,,,,,,,,,item1,,,,,,,,,\r\n")
            fou.write("0001,MemberCode2,hoge2@mail.com,Lname2,Fname2,PRE-username2,Password"
                      ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
        with ZipFile('/tmp/' + member_csv[:-4] + '.zip', 'w', ZIP_DEFLATED) as create_zip:
            create_zip.write('/tmp/' + member_csv, member_csv)
        s3key.key = "input_data/01_member/" + member_csv[:-4] + '.zip'
        s3key.set_contents_from_filename("/tmp/" + member_csv[:-4] + '.zip')
        if os.path.exists("/tmp/" + member_csv):
            os.remove("/tmp/" + member_csv)
        if os.path.exists("/tmp/" + member_csv[:-4] + '.zip'):
            os.remove("/tmp/" + member_csv[:-4] + '.zip')

        reg_user = User.objects.filter(username="PRE-username1").first()
        self.assertEqual(reg_user.email, "edx1@mail.com")
        reg_member = Member.objects.filter(user=reg_user).first()
        self.assertEqual(reg_member.org1, "abc1")

        reg_user = User.objects.filter(username="PRE-username2").first()
        self.assertEqual(reg_user.email, "edx2@mail.com")
        reg_member = Member.objects.filter(user=reg_user).first()
        self.assertEqual(reg_member.org1, "abc2")

        call_command('auto_member_register', '-bucket=test-bucket', '-prefix=sso_member',
                     '-prefix2=no_sso_member', '-user=1', '-org='+str(self.gacco_organization.id))

        # SSO target
        reg_user = User.objects.filter(username="PRE-username1").first()
        self.assertEqual(reg_user.email, "hoge1@mail.com")
        reg_userprofile = UserProfile.objects.filter(user=reg_user).first()
        self.assertEqual(reg_userprofile.name, "Lname1 Fname1")
        reg_member = Member.objects.filter(user=reg_user).first()
        self.assertEqual(reg_member.code, "MemberCode1")
        self.assertEqual(reg_member.org1, "org1")
        self.assertEqual(reg_member.item1, "item1")
        reg_socialauth = UserSocialAuth.objects.filter(user=reg_user, provider='tpa-saml',
                                                       uid="TES:MemberCode1").exists()
        self.assertTrue(reg_socialauth)
        reg_optout = Optout.objects.filter(user=reg_user).first()
        self.assertEqual(reg_optout.user_id, reg_user.id)
        reg_success_data = bucket.lookup(
            key_name="output_data/01_member/01_success/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_success_data, "Total :  1\r\nSuccessful :  1\r\nFailed :  0\r\n")

        # Non SSO target
        reg_user = User.objects.filter(username="PRE-username2").first()
        self.assertEqual(reg_user.email, "hoge2@mail.com")
        reg_userprofile = UserProfile.objects.filter(user=reg_user).first()
        self.assertEqual(reg_userprofile.name, "Lname2 Fname2")
        reg_member = Member.objects.filter(user=reg_user).first()
        self.assertEqual(reg_member.code, "MemberCode2")
        self.assertEqual(reg_member.org1, "org1")
        self.assertEqual(reg_member.item1, "item1")
        reg_socialauth = UserSocialAuth.objects.filter(user=reg_user, provider='tpa-saml',
                                                       uid="TES:MemberCode2").exists()
        self.assertTrue(reg_socialauth)
        reg_optout = Optout.objects.filter(user=reg_user).first()
        self.assertEqual(reg_optout.user_id, reg_user.id)
        reg_success_data = bucket.lookup(
            key_name="output_data/01_member/01_success/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_success_data, "Total :  1\r\nSuccessful :  1\r\nFailed :  0\r\n")

    @mock_s3
    @override_settings(AWS_ACCESS_KEY_ID='foobar', AWS_SECRET_ACCESS_KEY='bizbaz')
    def test_command_error_s3_disconnect(self):
        out = StringIO()
        call_command('auto_member_register', '-bucket=test-bucket', '-prefix=sso_member',
                     '-prefix2=no_sso_member', '-user=1', '-org=' + str(self.gacco_organization.id), stdout=out)
        self.assertTrue(out.getvalue())

    @mock_s3
    @override_settings(AWS_ACCESS_KEY_ID='foobar', AWS_SECRET_ACCESS_KEY='bizbaz')
    def test_command_error_member_code_blank(self):
        conn = connect_s3('foobar', 'bizbaz')
        conn.create_bucket('test-bucket')
        bucket = conn.get_bucket('test-bucket')
        s3key = Key(bucket)

        member_csv = "sso_member_2000-01-01-0000_01.csv"
        with codecs.open('/tmp/' + member_csv, 'w', 'utf8') as fou:
            fou.write("[Header],MemberCode,eMail.LastName,FirstName,Username,org1,,,,,,,,,item1,,,,,,,,,\r\n")
            fou.write(
                ",,hoge1@mail.com,Lname1,Fname1,PRE-username1"
                ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
        with ZipFile('/tmp/' + member_csv[:-4] + '.zip', 'w', ZIP_DEFLATED) as create_zip:
            create_zip.write('/tmp/' + member_csv, member_csv)
        s3key.key = "input_data/01_member/" + member_csv[:-4] + '.zip'
        s3key.set_contents_from_filename("/tmp/" + member_csv[:-4] + '.zip')
        if os.path.exists("/tmp/" + member_csv):
            os.remove("/tmp/" + member_csv)
        if os.path.exists("/tmp/" + member_csv[:-4] + '.zip'):
            os.remove("/tmp/" + member_csv[:-4] + '.zip')

        member_csv = "no_sso_member_2000-01-01-0000_01.csv"
        with codecs.open('/tmp/' + member_csv, 'w', 'utf8') as fou:
            fou.write("[Header],MemberCode,eMail.LastName,FirstName,Username,pwd,org1,,,,,,,,,item1,,,,,,,,,\r\n")
            fou.write(",,hoge2@mail.com,Lname2,Fname2,PRE-username2,Password"
                      ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
        with ZipFile('/tmp/' + member_csv[:-4] + '.zip', 'w', ZIP_DEFLATED) as create_zip:
            create_zip.write('/tmp/' + member_csv, member_csv)
        s3key.key = "input_data/01_member/" + member_csv[:-4] + '.zip'
        s3key.set_contents_from_filename("/tmp/" + member_csv[:-4] + '.zip')
        if os.path.exists("/tmp/" + member_csv):
            os.remove("/tmp/" + member_csv)
        if os.path.exists("/tmp/" + member_csv[:-4] + '.zip'):
            os.remove("/tmp/" + member_csv[:-4] + '.zip')

        call_command('auto_member_register', '-bucket=test-bucket', '-prefix=sso_member',
                     '-prefix2=no_sso_member', '-user=1', '-org='+str(self.gacco_organization.id))

        # SSO target
        reg_user = User.objects.filter(username="PRE-username1")
        self.assertFalse(reg_user.exists())

        member_csv = "sso_member_2000-01-01-0000_01.csv"
        reg_success_data = bucket.lookup(
            key_name="output_data/01_member/01_success/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_success_data, "Total :  1\r\nSuccessful :  0\r\nFailed :  1\r\n")
        reg_error_data = bucket.lookup(
            key_name="output_data/01_member/02_error/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_error_data, "username,email\r\nPRE-username1,hoge1@mail.com\r\n")

        # Non SSO target
        reg_user = User.objects.filter(username="PRE-username2")
        self.assertFalse(reg_user.exists())

        member_csv = "no_sso_member_2000-01-01-0000_01.csv"
        reg_success_data = bucket.lookup(
            key_name="output_data/01_member/01_success/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_success_data, "Total :  1\r\nSuccessful :  0\r\nFailed :  1\r\n")
        reg_error_data = bucket.lookup(
            key_name="output_data/01_member/02_error/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_error_data, "username,email\r\nPRE-username2,hoge2@mail.com\r\n")

    @mock_s3
    @override_settings(AWS_ACCESS_KEY_ID='foobar', AWS_SECRET_ACCESS_KEY='bizbaz')
    def test_command_error_shortage(self):
        conn = connect_s3('foobar', 'bizbaz')
        conn.create_bucket('test-bucket')
        bucket = conn.get_bucket('test-bucket')
        s3key = Key(bucket)

        member_csv = "sso_member_2000-01-01-0000_01.csv"
        with codecs.open('/tmp/' + member_csv, 'w', 'utf8') as fou:
            fou.write("[Header],MemberCode,eMail.LastName,FirstName,Username,org1,,,,,,,,,item1,,,,,,,,,\r\n")
            fou.write(
                ",MemberCode1,hoge1@mail.com,,Fname1,PRE-username1a"
                ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write(
                ",MemberCode1,hoge1@mail.com,Lname1,,PRE-username1b"
                ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write(
                ",MemberCode1,hoge1@mail.com,Lname1,,username1"
                ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write(
                "Code1,MemberCode1,hoge1@mail.com,Lname1,Fname1,PRE-username1c"
                ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write(
                ",MemberCode1"+"a"*70+",hoge1@mail.com,Lname1,Fname1,PRE-username1d"
                ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write(
                ",MemberCode1,hoge1"+"a"*70+"@mail.com,Lname1,Fname1,PRE-username1e"
                ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
        with ZipFile('/tmp/' + member_csv[:-4] + '.zip', 'w', ZIP_DEFLATED) as create_zip:
            create_zip.write('/tmp/' + member_csv, member_csv)
        s3key.key = "input_data/01_member/" + member_csv[:-4] + '.zip'
        s3key.set_contents_from_filename("/tmp/" + member_csv[:-4] + '.zip')
        if os.path.exists("/tmp/" + member_csv):
            os.remove("/tmp/" + member_csv)
        if os.path.exists("/tmp/" + member_csv[:-4] + '.zip'):
            os.remove("/tmp/" + member_csv[:-4] + '.zip')

        member_csv = "no_sso_member_2000-01-01-0000_01.csv"
        with codecs.open('/tmp/' + member_csv, 'w', 'utf8') as fou:
            fou.write("[Header],MemberCode,eMail.LastName,FirstName,Username,pwd,org1,,,,,,,,,item1,,,,,,,,,\r\n")
            fou.write(",MemberCode2,hoge2@mail.com,,Fname2,PRE-username2a,Password"
                      ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write(",MemberCode2,hoge2@mail.com,Lname2,,PRE-username2b,Password"
                      ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write(",MemberCode2,hoge2@mail.com,Lname2,Fname2,PRE-username2c,"
                      ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write(",MemberCode2,hoge2@mail.com,Lname2,Fname2,username2,Password"
                      ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write("Code,MemberCode2,hoge2@mail.com,Lname2,Fname2,PRE-username2d,Password"
                      ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write(",MemberCode2"+"a"*70+",hoge2@mail.com,Lname2,Fname2,PRE-username2e,Password"
                      ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
            fou.write(",MemberCode2,hoge2"+"a"*70+"@mail.com,Lname2,Fname2,PRE-username2f,Password"
                      ",org1,,,,,,,,,org10,item1,,,,,,,,,item10\r\n")
        with ZipFile('/tmp/' + member_csv[:-4] + '.zip', 'w', ZIP_DEFLATED) as create_zip:
            create_zip.write('/tmp/' + member_csv, member_csv)
        s3key.key = "input_data/01_member/" + member_csv[:-4] + '.zip'
        s3key.set_contents_from_filename("/tmp/" + member_csv[:-4] + '.zip')
        if os.path.exists("/tmp/" + member_csv):
            os.remove("/tmp/" + member_csv)
        if os.path.exists("/tmp/" + member_csv[:-4] + '.zip'):
            os.remove("/tmp/" + member_csv[:-4] + '.zip')

        call_command('auto_member_register', '-bucket=test-bucket', '-prefix=sso_member',
                     '-prefix2=no_sso_member', '-user=1', '-org='+str(self.gacco_organization.id))

        # SSO target
        reg_user = User.objects.filter(username="PRE-username1")
        self.assertFalse(reg_user.exists())

        member_csv = "sso_member_2000-01-01-0000_01.csv"
        reg_success_data = bucket.lookup(
            key_name="output_data/01_member/01_success/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_success_data, "Total :  6\r\nSuccessful :  0\r\nFailed :  6\r\n")
        reg_error_data = bucket.lookup(
            key_name="output_data/01_member/02_error/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_error_data, "username,email\r\nPRE-username1a,hoge1@mail.com\r\n"
                                         "PRE-username1b,hoge1@mail.com\r\nusername1,hoge1@mail.com\r\n"
                                         "PRE-username1c,hoge1@mail.com\r\nPRE-username1d,hoge1@mail.com\r\n"
                                         "PRE-username1e,hoge1"+"a"*70+"@mail.com\r\n")

        # Non SSO target
        reg_user = User.objects.filter(username="PRE-username2")
        self.assertFalse(reg_user.exists())

        member_csv = "no_sso_member_2000-01-01-0000_01.csv"
        reg_success_data = bucket.lookup(
            key_name="output_data/01_member/01_success/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_success_data, "Total :  7\r\nSuccessful :  0\r\nFailed :  7\r\n")
        reg_error_data = bucket.lookup(
            key_name="output_data/01_member/02_error/" + member_csv).get_contents_as_string(encoding='sjis')
        self.assertEqual(reg_error_data, "username,email\r\nPRE-username2a,hoge2@mail.com\r\n"
                                         "PRE-username2b,hoge2@mail.com\r\nPRE-username2c,hoge2@mail.com\r\n"
                                         "username2,hoge2@mail.com\r\nPRE-username2d,hoge2@mail.com\r\n"
                                         "PRE-username2e,hoge2@mail.com\r\nPRE-username2f,hoge2"+"a"*70+"@mail.com\r\n")

    @mock_s3
    @override_settings(AWS_ACCESS_KEY_ID='foobar', AWS_SECRET_ACCESS_KEY='bizbaz')
    def test_command_error_except_test(self):
        conn = connect_s3('foobar', 'bizbaz')
        conn.create_bucket('test-bucket')
        bucket = conn.get_bucket('test-bucket')
        s3key = Key(bucket)

        member_csv = "sso_member_2000-01-01-0000_01.csv"
        member_zip = "sso_member_2000-01-01-0001_01.zip"
        with codecs.open('/tmp/' + member_csv, 'w', 'utf8') as fou:
            fou.write("[Header],MemberCode,eMail.LastName,FirstName,Username,org1,,,,,,,,,item1,,,,,,,,,\r\n")
        with ZipFile('/tmp/' + member_zip[:-4] + '.zip', 'w', ZIP_DEFLATED) as create_zip:
            create_zip.write('/tmp/' + member_csv, member_csv)
        s3key.key = "input_data/01_member/" + member_zip[:-4] + '.zip'
        s3key.set_contents_from_filename("/tmp/" + member_zip[:-4] + '.zip')
        if os.path.exists("/tmp/" + member_csv):
            os.remove("/tmp/" + member_csv)
        if os.path.exists("/tmp/" + member_zip[:-4] + '.zip'):
            os.remove("/tmp/" + member_zip[:-4] + '.zip')

        member_csv = "no_sso_member_2000-01-01-0000_01.csv"
        member_zip = "no_sso_member_2000-01-01-0001_01.zip"
        with codecs.open('/tmp/' + member_csv, 'w', 'utf8') as fou:
            fou.write("[Header],MemberCode,eMail.LastName,FirstName,Username,pwd,org1,,,,,,,,,item1,,,,,,,,,\r\n")
        with ZipFile('/tmp/' + member_zip[:-4] + '.zip', 'w', ZIP_DEFLATED) as create_zip:
            create_zip.write('/tmp/' + member_csv, member_csv)
        s3key.key = "input_data/01_member/" + member_zip[:-4] + '.zip'
        s3key.set_contents_from_filename("/tmp/" + member_zip[:-4] + '.zip')
        if os.path.exists("/tmp/" + member_csv):
            os.remove("/tmp/" + member_csv)
        if os.path.exists("/tmp/" + member_zip[:-4] + '.zip'):
            os.remove("/tmp/" + member_zip[:-4] + '.zip')

        call_command('auto_member_register', '-bucket=test-bucket', '-prefix=sso_member',
                     '-prefix2=no_sso_member', '-user=1', '-org='+str(self.gacco_organization.id))

        # SSO target
        reg_user = User.objects.filter(username="PRE-username1")
        self.assertFalse(reg_user.exists())

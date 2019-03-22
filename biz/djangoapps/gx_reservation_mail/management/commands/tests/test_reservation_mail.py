"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from biz.djangoapps.ga_organization.models import Organization, OrganizationOption
from biz.djangoapps.gx_reservation_mail.models import ReservationMail
from biz.djangoapps.util.tests.testcase import BizViewTestBase
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from django.test.utils import override_settings
from student.tests.factories import UserFactory
import freezegun
import datetime
import pytz
import mock


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

    def test_command_one_success(self):
        user = UserFactory.create(username='student01', email='student01@test.com')

        mocked = datetime.datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user)
        with freezegun.freeze_time('2019-01-02 07:00:00'):
            call_command('reservation_mail')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['student01@test.com'])
        self.assertEqual(mail.outbox[0].subject, 'subject001')
        self.assertEqual(mail.outbox[0].body, 'body001')
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertTrue(res_mail.sent_flag)

    def test_command_one_success_specified(self):
        user = UserFactory.create(username='student01', email='student01@test.com')
        OrganizationOption.objects.create(org=self.gacco_organization, reservation_mail_date="6:00:00",
                                          modified_by=user)

        mocked = datetime.datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user)
        with freezegun.freeze_time('2019-01-02 07:00:00'):
            call_command('reservation_mail')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['student01@test.com'])
        self.assertEqual(mail.outbox[0].subject, 'subject001')
        self.assertEqual(mail.outbox[0].body, 'body001')
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertTrue(res_mail.sent_flag)

    def test_command_one_error_batch_time_before(self):
        user = UserFactory.create(username='student01', email='student01@test.com')

        mocked = datetime.datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user)
        with freezegun.freeze_time('2019-01-02 6:00:00'):
            call_command('reservation_mail')

        self.assertEqual(len(mail.outbox), 0)
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertFalse(res_mail.sent_flag)

    def test_command_one_error_specified_batch_time_before(self):
        user = UserFactory.create(username='student01', email='student01@test.com')
        OrganizationOption.objects.create(org=self.gacco_organization, reservation_mail_date="11:00:00",
                                          modified_by=user)

        mocked = datetime.datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user)
        with freezegun.freeze_time('2019-01-02 7:00:00'):
            call_command('reservation_mail')

        self.assertEqual(len(mail.outbox), 0)
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertFalse(res_mail.sent_flag)

    def test_command_one_error_mail_time_new(self):
        user = UserFactory.create(username='student01', email='student01@test.com')

        mocked = datetime.datetime(2019, 1, 2, 8, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user)
        with freezegun.freeze_time('2019-01-02 7:00:00'):
            call_command('reservation_mail')

        self.assertEqual(len(mail.outbox), 0)
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertFalse(res_mail.sent_flag)

    def test_command_one_error_specified_mail_time_new(self):
        user = UserFactory.create(username='student01', email='student01@test.com')
        OrganizationOption.objects.create(org=self.gacco_organization, reservation_mail_date="6:00:00",
                                          modified_by=user)

        mocked = datetime.datetime(2019, 1, 2, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user)
        with freezegun.freeze_time('2019-01-02 7:00:00'):
            call_command('reservation_mail')

        self.assertEqual(len(mail.outbox), 0)
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertFalse(res_mail.sent_flag)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_command_one_error_mail_server(self):
        user = UserFactory.create(username='student01', email='')

        mocked = datetime.datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user)
        with freezegun.freeze_time('2019-01-02 07:00:00'):
            call_command('reservation_mail')

        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertFalse(res_mail.sent_flag)

    def test_command_one_success_target(self):
        user = UserFactory.create(username='student01', email='student01@test.com')
        user2 = UserFactory.create(username='student02', email='student02@test.com')

        mocked = datetime.datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user)
            res_mail2 = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject002",
                                                       mail_body="body002", user=user2)
        with freezegun.freeze_time('2019-01-02 07:00:00'):
            call_command('reservation_mail', '-id=2')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['student02@test.com'])
        self.assertEqual(mail.outbox[0].subject, 'subject002')
        self.assertEqual(mail.outbox[0].body, 'body002')
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertFalse(res_mail.sent_flag)
        res_mail2 = ReservationMail.objects.get(id=res_mail2.id)
        self.assertTrue(res_mail2.sent_flag)

    def test_command_two_success(self):
        user = UserFactory.create(username='student01', email='student01@test.com')
        user2 = UserFactory.create(username='student02', email='student02@test.com')

        mocked = datetime.datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user)
            res_mail2 = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject002",
                                                       mail_body="body002", user=user2)
        with freezegun.freeze_time('2019-01-02 07:00:00'):
            call_command('reservation_mail')

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['student01@test.com'])
        self.assertEqual(mail.outbox[0].subject, 'subject001')
        self.assertEqual(mail.outbox[0].body, 'body001')
        self.assertEqual(mail.outbox[1].to, ['student02@test.com'])
        self.assertEqual(mail.outbox[1].subject, 'subject002')
        self.assertEqual(mail.outbox[1].body, 'body002')
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertTrue(res_mail.sent_flag)
        res_mail2 = ReservationMail.objects.get(id=res_mail2.id)
        self.assertTrue(res_mail2.sent_flag)

    def test_command_two_success_specified(self):
        user = UserFactory.create(username='student01', email='student01@test.com')
        user2 = UserFactory.create(username='student02', email='student02@test.com')
        OrganizationOption.objects.create(org=self.gacco_organization, reservation_mail_date="6:00:00",
                                          modified_by=user)

        mocked = datetime.datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user)
            res_mail2 = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject002",
                                                       mail_body="body002", user=user2)
        with freezegun.freeze_time('2019-01-02 07:00:00'):
            call_command('reservation_mail')

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['student01@test.com'])
        self.assertEqual(mail.outbox[0].subject, 'subject001')
        self.assertEqual(mail.outbox[0].body, 'body001')
        self.assertEqual(mail.outbox[1].to, ['student02@test.com'])
        self.assertEqual(mail.outbox[1].subject, 'subject002')
        self.assertEqual(mail.outbox[1].body, 'body002')
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertTrue(res_mail.sent_flag)
        res_mail2 = ReservationMail.objects.get(id=res_mail2.id)
        self.assertTrue(res_mail2.sent_flag)

    def test_command_fail_success_mix(self):
        user = UserFactory.create(username='student01', email='student01@test.com')
        user2 = UserFactory.create(username='student02', email='student02@test.com')

        mocked = datetime.datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user, sent_flag=True)
            res_mail2 = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject002",
                                                       mail_body="body002", user=user2)
        with freezegun.freeze_time('2019-01-02 07:00:00'):
            call_command('reservation_mail')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['student02@test.com'])
        self.assertEqual(mail.outbox[0].subject, 'subject002')
        self.assertEqual(mail.outbox[0].body, 'body002')
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertTrue(res_mail.sent_flag)
        res_mail2 = ReservationMail.objects.get(id=res_mail2.id)
        self.assertTrue(res_mail2.sent_flag)

    def test_command_fail_success_mix_specified(self):
        user = UserFactory.create(username='student01', email='student01@test.com')
        user2 = UserFactory.create(username='student02', email='student02@test.com')
        OrganizationOption.objects.create(org=self.gacco_organization, reservation_mail_date="6:00:00",
                                          modified_by=user)

        mocked = datetime.datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc)
        with mock.patch('django.utils.timezone.now', mock.Mock(return_value=mocked)):
            res_mail = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject001",
                                                      mail_body="body001", user=user, sent_flag=True)
            res_mail2 = ReservationMail.objects.create(org=self.gacco_organization, mail_subject="subject002",
                                                       mail_body="body002", user=user2)
        with freezegun.freeze_time('2019-01-02 07:00:00'):
            call_command('reservation_mail')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['student02@test.com'])
        self.assertEqual(mail.outbox[0].subject, 'subject002')
        self.assertEqual(mail.outbox[0].body, 'body002')
        res_mail = ReservationMail.objects.get(id=res_mail.id)
        self.assertTrue(res_mail.sent_flag)
        res_mail2 = ReservationMail.objects.get(id=res_mail2.id)
        self.assertTrue(res_mail2.sent_flag)

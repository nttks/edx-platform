"""
These are tests for disabling and enabling student accounts, and for making sure
that students with disabled accounts are unable to access the courseware.
"""
import ddt
import json
import unittest

from student.tests.factories import CourseEnrollmentFactory, UserFactory, UserStandingFactory
from student.models import CourseEnrollment, UserStanding
from django.conf import settings
from django.test import TestCase, Client
from django.core.urlresolvers import reverse
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@ddt.ddt
class UserStandingTest(ModuleStoreTestCase):
    """test suite for user standing view for enabling and disabling accounts"""

    def setUp(self):
        super(UserStandingTest, self).setUp()
        # create users
        self.bad_user = UserFactory.create(
            username='bad_user',
            email='bad_user@example.com',
        )
        self.good_user = UserFactory.create(
            username='good_user',
            email='good_user@example.com',
        )
        self.non_staff = UserFactory.create(
            username='non_staff',
        )
        self.admin = UserFactory.create(
            username='admin',
            is_staff=True,
        )
        self.non_existent_username = 'nouser'

        # create clients
        self.bad_user_client = Client()
        self.good_user_client = Client()
        self.non_staff_client = Client()
        self.admin_client = Client()

        for user, client in [
            (self.bad_user, self.bad_user_client),
            (self.good_user, self.good_user_client),
            (self.non_staff, self.non_staff_client),
            (self.admin, self.admin_client),
        ]:
            client.login(username=user.username, password='test')

        UserStandingFactory.create(
            user=self.bad_user,
            account_status=UserStanding.ACCOUNT_DISABLED,
            changed_by=self.admin
        )

        # set stock url to test disabled accounts' access to site
        self.some_url = '/'

        # since it's only possible to disable accounts from lms, we're going
        # to skip tests for cms

    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_disable_account(self):
        self.assertEqual(
            UserStanding.objects.filter(user=self.good_user).count(), 0
        )
        response = self.admin_client.post(reverse('disable_account_ajax'), {
            'username_or_email': self.good_user.username,
            'account_action': 'disable',
        })
        self.assertEqual(
            UserStanding.objects.get(user=self.good_user).account_status,
            UserStanding.ACCOUNT_DISABLED
        )
        content = json.loads(response.content)
        self.assertEqual(content['user_name'], self.good_user.username)
        self.assertEqual(content['user_mail'], self.good_user.email)
        self.assertEqual(
            content['account_status'],
            UserStanding.ACCOUNT_DISABLED
        )

    def test_disabled_account_redirect_to_disabled_account_page(self):
        response = self.bad_user_client.get(self.some_url)
        self.assertRedirects(response, 'disabled_account')

    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_reenable_account(self):
        response = self.admin_client.post(reverse('disable_account_ajax'), {
            'username_or_email': self.bad_user.username,
            'account_action': 'reenable'
        })
        self.assertEqual(
            UserStanding.objects.get(user=self.bad_user).account_status,
            UserStanding.ACCOUNT_ENABLED
        )
        content = json.loads(response.content)
        self.assertEqual(content['user_name'], self.bad_user.username)
        self.assertEqual(content['user_mail'], self.bad_user.email)
        self.assertEqual(
            content['account_status'],
            UserStanding.ACCOUNT_ENABLED
        )

    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_non_staff_cant_access_disable_view(self):
        response = self.non_staff_client.get(reverse('manage_user_standing'), {
            'user': self.non_staff,
        })
        self.assertEqual(response.status_code, 404)

    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_non_staff_cant_disable_account(self):
        response = self.non_staff_client.post(reverse('disable_account_ajax'), {
            'username_or_email': self.good_user.username,
            'user': self.non_staff,
            'account_action': 'disable'
        })
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            UserStanding.objects.filter(user=self.good_user).count(), 0
        )

    @ddt.data(
        ('username', True),
        ('username', False),
        ('email', True),
        ('email', False),
    )
    @ddt.unpack
    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_view_student_course_enrollment(self, username_or_email, has_enrollment):
        if has_enrollment:
            for is_active in [True, False]:
                CourseEnrollmentFactory.create(
                    user=self.good_user,
                    course_id=CourseFactory.create().id,
                    is_active=is_active
                )

        conditions = self.good_user.username if username_or_email == 'username' else self.good_user.email
        response = self.admin_client.post(reverse('disable_account_ajax'), {
            'username_or_email': conditions,
            'account_action': 'view_course_enrollment',
        })
        content = json.loads(response.content)
        self.assertEqual(content['user_name'], self.good_user.username)
        self.assertEqual(content['user_mail'], self.good_user.email)
        expected_header = 'course_id,is_active,created'
        self.assertEqual(
            content['course_enrollment_header'],
            expected_header
        )
        expected_rows = [
            ','.join([str(e.course_id), str(e.is_active), str(e.created) + '(UTC)'])
            for e in CourseEnrollment.objects.filter(user=self.good_user).order_by('-created')
        ]
        self.assertListEqual(
            content['course_enrollment_rows'],
            expected_rows
        )

    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_view_student_course_enrollment_no_input_case(self):
        response = self.admin_client.post(reverse('disable_account_ajax'), {
            'account_action': 'view_course_enrollment',
        })
        content = json.loads(response.content)
        self.assertEqual(
            content['message'],
            'Please enter a username or email.'
        )

    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_view_student_course_enrollment_non_existent_account_case(self):
        response = self.admin_client.post(reverse('disable_account_ajax'), {
            'username_or_email': self.non_existent_username,
            'account_action': 'view_course_enrollment',
        })
        content = json.loads(response.content)
        self.assertEqual(
            content['message'],
            '{} does not exist'.format(self.non_existent_username)
        )

    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_view_account_status_enable_account_case(self):
        response = self.admin_client.post(reverse('disable_account_ajax'), {
            'username_or_email': self.good_user.username,
            'account_action': 'view_account_status',
        })
        content = json.loads(response.content)
        self.assertEqual(content['user_name'], self.good_user.username)
        self.assertEqual(content['user_mail'], self.good_user.email)
        self.assertEqual(
            content['account_status'],
            UserStanding.ACCOUNT_ENABLED
        )

    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_view_account_status_disable_account_case(self):
        self.bad_user.standing.account_status = UserStanding.ACCOUNT_DISABLED
        self.bad_user.standing.save()
        response = self.admin_client.post(reverse('disable_account_ajax'), {
            'username_or_email': self.bad_user.username,
            'account_action': 'view_account_status',
        })
        content = json.loads(response.content)
        self.assertEqual(content['user_name'], self.bad_user.username)
        self.assertEqual(content['user_mail'], self.bad_user.email)
        self.assertEqual(
            content['account_status'],
            UserStanding.ACCOUNT_DISABLED
        )

    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_view_account_status_user_activated_case(self):
        response = self.admin_client.post(reverse('disable_account_ajax'), {
            'username_or_email': self.good_user.username,
            'account_action': 'view_account_status',
        })
        content = json.loads(response.content)
        self.assertEqual(content['user_name'], self.good_user.username)
        self.assertEqual(content['user_mail'], self.good_user.email)
        self.assertEqual(
            content['is_active'],
            'activated'
        )

    @unittest.skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
    def test_view_account_status_user_not_activated_case(self):
        self.bad_user.is_active = False
        self.bad_user.save()
        response = self.admin_client.post(reverse('disable_account_ajax'), {
            'username_or_email': self.bad_user.username,
            'account_action': 'view_account_status',
        })
        content = json.loads(response.content)
        self.assertEqual(content['user_name'], self.bad_user.username)
        self.assertEqual(content['user_mail'], self.bad_user.email)
        self.assertEqual(
            content['is_active'],
            'not activated'
        )

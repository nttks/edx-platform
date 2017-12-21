"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".
Replace this with more appropriate tests for your application.
"""
import uuid

from mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command

from biz.djangoapps.util.tests.testcase import BizTestBase
from student.models import Registration, UserStanding
from student.tests.factories import UserFactory, RegistrationFactory, UserStandingFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


class MaskResignedUserTest(BizTestBase, ModuleStoreTestCase):
    def setUp(self):
        super(MaskResignedUserTest, self).setUp()

        self.random_value = 'test1'

        patcher = patch('biz.djangoapps.util.mask_utils.get_random_string')
        self.mock_get_random_string = patcher.start()
        self.mock_get_random_string.return_value = self.random_value
        self.addCleanup(patcher.stop)

    def test_mask_resigned_user(self):
        # create user
        resigned_user = UserFactory.create(
            email='resigned@example.com',
            is_active=True
        )
        enrollment_user = UserFactory.create(
            email='enrollment@example.com',
            is_active=True
        )
        RegistrationFactory.create(user=resigned_user, activation_key=uuid.uuid4().hex, masked=False)
        RegistrationFactory.create(user=enrollment_user, activation_key=uuid.uuid4().hex, masked=False)

        # resigned
        UserStandingFactory.create(
            user=resigned_user,
            account_status=UserStanding.ACCOUNT_DISABLED,
            changed_by=resigned_user,
        )

        call_command('mask_resigned_user', debug=False)

        masked_user = User.objects.get(pk=resigned_user.pk)
        self.assertTrue(masked_user.registration.masked)
        self.assertFalse('@' in masked_user.email)
        unmasked_user = User.objects.get(pk=enrollment_user.pk)
        self.assertFalse(unmasked_user.registration.masked)
        self.assertEquals('enrollment@example.com', unmasked_user.email)

    @patch('biz.djangoapps.ga_student.management.commands.mask_resigned_user.log.error')
    @patch('biz.djangoapps.ga_student.management.commands.mask_resigned_user.log.exception')
    @patch('biz.djangoapps.ga_student.management.commands.mask_resigned_user.log.info')
    def test_mask_resigned_user_failed(self, mock_log_info, mock_log_exception, mock_log_error):
        # create user
        error1_user = UserFactory.create(
            email='error1@example.com',
            username='b_error',
            is_active=True
        )
        error2_user = UserFactory.create(
            email='error2@example.com',
            username='d_error',
            is_active=True
        )
        resigned1_user = UserFactory.create(
            email='resigned1@example.com',
            username='a_resigned1',
            is_active=True
        )
        resigned2_user = UserFactory.create(
            email='resigned2@example.com',
            username='c_resigned2',
            is_active=True
        )
        target_users = [error1_user, error2_user, resigned1_user, resigned2_user]
        for user in target_users:
            RegistrationFactory.create(user=user, activation_key=uuid.uuid4().hex, masked=False)
            # resigned
            UserStandingFactory.create(
                user=user,
                account_status=UserStanding.ACCOUNT_DISABLED,
                changed_by=user,
            )

        # raise Exception
        self.mock_get_random_string.side_effect = [self.random_value, Exception, self.random_value, Exception]

        call_command('mask_resigned_user', debug=False)

        self.assertEqual(8, mock_log_info.call_count)
        self.assertEqual(2, mock_log_exception.call_count)
        self.assertEqual(1, mock_log_error.call_count)

        # masked user
        user = resigned1_user
        mock_log_info.assert_any_call(u"Masked start user_id, user_name : {}, {}.".format(user.id, user.username))
        mock_log_info.assert_any_call(u"Masked success user_id, user_name : {}, {}.".format(user.id, user.username))
        masked_user = User.objects.get(pk=user.pk)
        self.assertTrue(masked_user.registration.masked)
        self.assertFalse('@' in masked_user.email)

        # masked user but occured error
        user = error1_user
        mock_log_info.assert_any_call(u"Masked start user_id, user_name : {}, {}.".format(user.id, user.username))
        mock_log_exception.assert_any_call(u"Masked failed user_id, user_name : {}, {}.".format(user.id, user.username))
        unmasked_user = User.objects.get(pk=user.pk)
        self.assertFalse(unmasked_user.registration.masked)
        self.assertEquals('error1@example.com', unmasked_user.email)

        # masked user
        user = resigned2_user
        mock_log_info.assert_any_call(u"Masked start user_id, user_name : {}, {}.".format(user.id, user.username))
        mock_log_info.assert_any_call(u"Masked success user_id, user_name : {}, {}.".format(user.id, user.username))
        masked_user = User.objects.get(pk=user.pk)
        self.assertTrue(masked_user.registration.masked)
        self.assertFalse('@' in masked_user.email)

        # masked user but occured error
        user = error2_user
        mock_log_info.assert_any_call(u"Masked start user_id, user_name : {}, {}.".format(user.id, user.username))
        mock_log_exception.assert_any_call(u"Masked failed user_id, user_name : {}, {}.".format(user.id, user.username))
        unmasked_user = User.objects.get(pk=error2_user.pk)
        self.assertFalse(unmasked_user.registration.masked)
        self.assertEquals('error2@example.com', unmasked_user.email)

        failed_users = [
            str(error1_user.id) + u'-' + error1_user.username,
            str(error2_user.id) + u'-' + error2_user.username,
        ]
        mock_log_error.assert_called_once_with(u"Masked failed users : {}".format(failed_users))

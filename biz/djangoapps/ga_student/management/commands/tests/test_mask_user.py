"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import ddt
import uuid

from datetime import datetime, timedelta
from mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from social.apps.django_app.default.models import UserSocialAuth

from biz.djangoapps.util import mask_utils
from biz.djangoapps.util.tests.testcase import BizTestBase
from bulk_email.models import Optout
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from student.models import Registration
from student.tests.factories import UserFactory, RegistrationFactory, UserProfileFactory
from third_party_auth.tests.testutil import ThirdPartyAuthTestMixin
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@ddt.ddt
class MaskUserTest(BizTestBase, ModuleStoreTestCase, ThirdPartyAuthTestMixin):

    def _create_test_target(self, timedelta_days):
        user = UserFactory.create(is_active=False)
        UserSocialAuth.objects.create(user=user, provider='dummy', uid=user.email)
        RegistrationFactory.create(user=user, activation_key=uuid.uuid4().hex, masked=False)
        if timedelta_days is None:
            Registration.objects.filter(user=user).update(modified=None)
        else:
            Registration.objects.filter(user=user).update(modified=datetime.now() + timedelta(timedelta_days))
        return user, UserProfileFactory(user=user), Registration.objects.get(user=user)

    def _assert_masked(self, user, profile, registration):
        masked_user = User.objects.get(pk=user.id)

        for course in self.global_courses:
            self.assertTrue(Optout.objects.filter(user=masked_user, course_id=course.id, force_disabled=True).exists())

        self.assertEquals('', masked_user.first_name)
        self.assertEquals('', masked_user.last_name)
        self.assertEquals(mask_utils.hash(profile.name), masked_user.profile.name)

        self.assertEquals(mask_utils.hash(user.email + self.random_value), masked_user.email)

        self.assertFalse(UserSocialAuth.objects.filter(user=masked_user).exists())

        self.assertNotEquals(registration.modified, masked_user.registration.modified)
        self.assertTrue(masked_user.registration.masked)

    def _assert_unmasked(self, user, profile, registration):
        unmasked_user = User.objects.get(pk=user.id)

        for course in self.global_courses:
            self.assertFalse(Optout.objects.filter(user=unmasked_user, course_id=course.id).exists())

        self.assertEquals(user.first_name, unmasked_user.first_name)
        self.assertEquals(user.last_name, unmasked_user.last_name)
        self.assertEquals(profile.name, unmasked_user.profile.name)

        self.assertEquals(user.email, unmasked_user.email)

        self.assertTrue(UserSocialAuth.objects.filter(user=unmasked_user).exists())

        self.assertEquals(registration.modified, unmasked_user.registration.modified)
        self.assertFalse(unmasked_user.registration.masked)

    def setUp(self):
        super(MaskUserTest, self).setUp()

        self.random_value = 'test1'

        patcher = patch('biz.djangoapps.util.mask_utils.get_random_string')
        self.mock_get_random_string = patcher.start()
        self.mock_get_random_string.return_value = self.random_value
        self.addCleanup(patcher.stop)

        self.global_courses = [
            CourseFactory.create(org='global', course='course1', run='run'),
            CourseFactory.create(org='global', course='course2', run='run'),
        ]
        for course in self.global_courses:
            CourseGlobalSettingFactory.create(course_id=course.id)

        MaskUserTest.configure_oauth_provider(
            name="Dummy",
            backend_name="dummy",
            key="testkey",
            secret="testsecret",
            enabled=True
        )

    @patch('biz.djangoapps.ga_student.management.commands.mask_user.log.error')
    @patch('biz.djangoapps.ga_student.management.commands.mask_user.log.exception')
    @patch('biz.djangoapps.ga_student.management.commands.mask_user.log.info')
    @ddt.data(
        (-2, True, 4, 0, 0),
        (-1, False, 2, 0, 0),
        (0, False, 2, 0, 0),
        (None, False, 2, 0, 0),
    )
    @ddt.unpack
    def test_call_command_mask_user_single(self, timedelta_days, masked, call_count_log_info, call_count_log_error, call_count_log_exception, mock_log_info, mock_log_exception, mock_log_error):
        user, profile, registration = self._create_test_target(timedelta_days)

        call_command('mask_user')

        self.assertEqual(call_count_log_info, mock_log_info.call_count)
        self.assertEqual(call_count_log_exception, mock_log_exception.call_count)
        self.assertEqual(call_count_log_error, mock_log_error.call_count)

        if masked:
            mock_log_info.assert_any_call(u"Masked start user_id : {}.".format(user.id))
            mock_log_info.assert_any_call(u"Masked success user_id : {}.".format(user.id))
            self._assert_masked(user, profile, registration)
        else:
            self._assert_unmasked(user, profile, registration)

    @patch('biz.djangoapps.ga_student.management.commands.mask_user.log.error')
    @patch('biz.djangoapps.ga_student.management.commands.mask_user.log.exception')
    @patch('biz.djangoapps.ga_student.management.commands.mask_user.log.info')
    def test_call_command_mask_user_mixed(self, mock_log_info, mock_log_exception, mock_log_error):
        test_targets = [
            self._create_test_target(-2),
            self._create_test_target(-1),
            self._create_test_target(-3),
            self._create_test_target(None),
            self._create_test_target(-4),
        ]

        self.mock_get_random_string.side_effect = [Exception, self.random_value, Exception]

        call_command('mask_user')

        self.assertEqual(6, mock_log_info.call_count)
        self.assertEqual(2, mock_log_exception.call_count)
        self.assertEqual(1, mock_log_error.call_count)

        # masked user
        mock_log_info.assert_any_call(u"Masked start user_id : {}.".format(test_targets[2][0].id))
        mock_log_info.assert_any_call(u"Masked success user_id : {}.".format(test_targets[2][0].id))
        self._assert_masked(*test_targets[2])

        # unmasked user
        self._assert_unmasked(*test_targets[1])
        self._assert_unmasked(*test_targets[3])

        # masked user but occured error
        mock_log_info.assert_any_call(u"Masked start user_id : {}.".format(test_targets[0][0].id))
        mock_log_exception.assert_any_call(u"Masked failed user_id : {}.".format(test_targets[0][0].id))
        self._assert_unmasked(*test_targets[0])

        mock_log_info.assert_any_call(u"Masked start user_id : {}.".format(test_targets[4][0].id))
        mock_log_exception.assert_any_call(u"Masked failed user_id : {}.".format(test_targets[4][0].id))
        self._assert_unmasked(*test_targets[4])

        mock_log_error.assert_called_once_with(u"Masked failed user_ids : {}".format([test_targets[0][0].id, test_targets[4][0].id]))

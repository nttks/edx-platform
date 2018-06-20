# -*- coding: utf-8 -*-
"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import ddt
from datetime import datetime, timedelta
from dateutil.tz import tzutc
import logging
from mock import patch
import re
import tempfile
import uuid

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test.utils import override_settings
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule_django.models import CourseKeyField

from biz.djangoapps.ga_contract.tests.factories import ContractAuthFactory, ContractOptionFactory
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.util import datetime_utils, mask_utils
from biz.djangoapps.util.decorators import ExitWithWarning
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from courseware.tests.helpers import LoginEnrollmentTestCase
from ga_bulk_email.models import SelfPacedCourseClosureReminderBatchStatus, BATCH_STATUS_STARTED, \
    BATCH_STATUS_FINISHED, BATCH_STATUS_ERROR
from ga_bulk_email.models import SelfPacedCourseClosureReminderMail
from ga_bulk_email.management.commands import send_self_paced_course_closure_reminder_email
from ga_bulk_email.management.commands.tests.factories import SelfPacedCourseClosureReminderMailFactory
from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration, SELF_PACED_COURSE_CLOSURE_REMINDER_EMAIL_KEY
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from student.tests.factories import UserFactory, UserProfileFactory, CourseEnrollmentFactory

command_output_file = tempfile.NamedTemporaryFile()


class TestArgParsing(BizStoreTestBase, ModuleStoreTestCase):
    """
    Tests for parsing arguments of the `send_self_paced_course_closure_reminder_email` command
    """
    def setUp(self):
        super(TestArgParsing, self).setUp()
        self.course = self._create_course(self.gacco_organization.org_code, 'course', 'run', [])
        self.command = send_self_paced_course_closure_reminder_email.Command()

    def test_args_debug(self):
        self.command.execute(debug=True)
        self.assertEquals(send_self_paced_course_closure_reminder_email.log.level, logging.DEBUG)

    def test_excludes_as_empty_string(self):
        with patch('ga_bulk_email.management.commands.send_self_paced_course_closure_reminder_email.log.debug') as mock_exclude:
            self.command.execute(excludes='')
            mock_exclude.assert_any_call(u"exclude_ids={}".format([]))

    def test_excludes_as_course_key(self):
        with patch('ga_bulk_email.management.commands.send_self_paced_course_closure_reminder_email.log.debug') as mock_exclude:
            self.command.execute(excludes='course-v1:org+course+run')
            mock_exclude.assert_any_call(u"exclude_ids={}".format(['course-v1:org+course+run']))

    def test_excludes_as_comma_delimited_course_keys(self):
        with patch('ga_bulk_email.management.commands.send_self_paced_course_closure_reminder_email.log.debug') as mock_exclude:
            self.command.execute(excludes='org/course/run,course-v1:org+course+run')
            mock_exclude.assert_any_call(u"exclude_ids={}".format(['org/course/run', 'course-v1:org+course+run']))

    def test_invalid_excludes(self):
        errstring = re.escape("The exclude_ids is not of the right format. It should be like 'org/course/run' or 'course-v1:org+course+run'.")
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, excludes='a')

    def test_exclude_ids_and_course_key(self):
        errstring = re.escape("Cannot specify exclude_ids and course_id at the same time.")
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, 'course-v1:org+course+run', excludes='course-v1:org+course+run')

    def test_too_much_args(self):
        errstring = re.escape("This command requires one or no arguments: |<course_id>|")
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, 'org/course/run', 'course-v1:org+course+run')

    def test_invalid_course_key(self):
        course_id = 'a'
        errstring = re.escape("The specified course_id is not of the right format. It should be like 'org/course/run' or 'course-v1:org+course+run'.")
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, course_id)

    def test_invalid_not_found_course_key(self):
        course_id = 'course-v1:org+course+run'
        errstring = re.escape("No such course(id={}) was found.".format(course_id))
        with self.assertRaisesRegexp(ExitWithWarning, errstring):
            self.command.handle._original(self.command, course_id)

    def test_no_self_paced_course_key(self):
        errstring = re.escape("The specified course(id={}) was not self-paced.".format(str(self.course.id)))
        with self.assertRaisesRegexp(ExitWithWarning, errstring):
            self.command.handle._original(self.command, str(self.course.id))


@ddt.ddt
@override_settings(GA_BULK_EMAIL_SEND_SELF_PACED_COURSE_CLOSURE_REMINDER_EMAIL_COMMAND_OUTPUT=command_output_file.name)
class SendSelfPacedCourseClosureReminderEmailTest(BizStoreTestBase, ModuleStoreTestCase, LoginEnrollmentTestCase):

    def _profile(self, user):
        UserProfileFactory.create(user=user, name='profile_name')

    def _biz_user(self, user, contract, send_mail):
        BizUserFactory.create(user=user, login_code='test-login-code')
        ContractAuthFactory.create(contract=contract, url_code='test-url-code', send_mail=send_mail)

    def _create_contract_option(self, contract, send_submission_reminder=True):
        return ContractOptionFactory.create(contract=contract, send_submission_reminder=send_submission_reminder)

    def _create_course_option(self, user, course, enabled):
        return CourseOptionalConfiguration(
            id=1,
            change_date="2015-06-18 11:02:13",
            enabled=enabled,
            key=SELF_PACED_COURSE_CLOSURE_REMINDER_EMAIL_KEY,
            course_key=course.id,
            changed_by_id=user.id
        ).save()

    def _create_self_paced_course_closure_reminder_email_default(self, reminder_email_days):
        return SelfPacedCourseClosureReminderMailFactory.create(
                course_id=CourseKeyField.Empty,
                mail_type=SelfPacedCourseClosureReminderMail.MAIL_TYPE_SELF_PACED_COURSE_CLOSURE_REMINDER,
                mail_subject='Test Subject for Self-paced Course Closure Reminder Email {fullname} {course_id} {course_name} {terminate_date_jp} {terminate_date_en}',
                mail_body='Test Body for Self-paced Course Closure Reminder Email {fullname} {course_id} {course_name} {terminate_date_jp} {terminate_date_en}',
                reminder_email_days=reminder_email_days,
            )

    def _create_self_paced_course(self):
        return self._create_course(self.gacco_organization.org_code, 'course_{}'.format(uuid.uuid4().hex[:5]), 'run', [], {
                'display_name': 'test_course',
                'start': datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
                'self_paced': True,
                'individual_end_days': self.default_reminder_email_days,
            })

    def _create_spoc_course(self):
        course = self._create_self_paced_course()
        self.contract = self._create_contract(detail_courses=[course])
        self.contract_option = self._create_contract_option(self.contract)
        return course

    def _create_mooc_course(self):
        course = self._create_self_paced_course()
        return course

    def _create_global_course(self):
        course = self._create_self_paced_course()
        CourseGlobalSettingFactory.create(course_id=course.id)
        return course

    def setUp(self):
        super(SendSelfPacedCourseClosureReminderEmailTest, self).setUp()
        self.default_reminder_email_days = 3
        self.now = datetime_utils.timezone_now()
        self.yesterday = self.now - timedelta(days=1)
        self.target_datetime = self.now.replace(hour=20) + timedelta(days=self.default_reminder_email_days)
        self.non_target_datetime = self.now.replace(hour=20) + timedelta(days=self.default_reminder_email_days + 1)

        # Setup default mail template
        self.default_mail_template = self._create_self_paced_course_closure_reminder_email_default(self.default_reminder_email_days)

        # Setup mock
        patcher_send_mail = patch('ga_bulk_email.management.commands.send_self_paced_course_closure_reminder_email.send_mail')
        self.mock_send_mail = patcher_send_mail.start()
        self.addCleanup(patcher_send_mail.stop)

        patcher_log = patch('ga_bulk_email.management.commands.send_self_paced_course_closure_reminder_email.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

    def assert_not_started(self, course_id):
        self.assertFalse(SelfPacedCourseClosureReminderBatchStatus.objects.filter(course_id=course_id).exists())

    def assert_finished(self, success_count, failure_count, course_id):
        SelfPacedCourseClosureReminderBatchStatus.objects.get(course_id=course_id, status=BATCH_STATUS_STARTED)
        SelfPacedCourseClosureReminderBatchStatus.objects.get(course_id=course_id, status=BATCH_STATUS_FINISHED,
                                                  success_count=success_count, failure_count=failure_count)

    def assert_error(self, success_count, failure_count, course_id):
        SelfPacedCourseClosureReminderBatchStatus.objects.get(course_id=course_id, status=BATCH_STATUS_STARTED)
        SelfPacedCourseClosureReminderBatchStatus.objects.get(course_id=course_id, status=BATCH_STATUS_ERROR,
                                                  success_count=success_count, failure_count=failure_count)

    def test_success_spoc(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(1, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 1)

    def test_success_mooc(self):
        self._profile(self.user)
        self.course = self._create_mooc_course()
        self._create_course_option(self.user, self.course, True)
        CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(1, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 1)

    def test_success_using_debug_option(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id), debug=True)

        self.assert_finished(1, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)

    def test_success_with_multi_users(self):
        spoc = self._create_spoc_course()
        self._create_course_option(self.user, spoc, True)
        for _ in range(0, 50):
            user = UserFactory.create()
            self._profile(user)
            self._register_contract(self.contract, user)

        mooc = self._create_mooc_course()
        self._create_course_option(self.user, mooc, True)
        for _ in range(0, 50):
            user = UserFactory.create()
            self._profile(user)
            CourseEnrollmentFactory.create(user=user, course_id=mooc.id)

        call_command('send_self_paced_course_closure_reminder_email')

        self.assert_finished(50, 0, spoc.id)
        self.assert_finished(50, 0, mooc.id)
        self.assertEquals(self.mock_send_mail.call_count, 100)

    def test_skip_exclude_ids(self):
        self._profile(self.user)
        spoc = self._create_spoc_course()
        self._create_course_option(self.user, spoc, True)
        self._register_contract(self.contract, self.user)

        mooc = self._create_mooc_course()
        self._create_course_option(self.user, mooc, True)
        CourseEnrollmentFactory.create(user=self.user, course_id=mooc.id)

        excludes = '{},{}'.format(str(spoc.id), str(mooc.id))

        call_command('send_self_paced_course_closure_reminder_email', excludes=excludes)

        self.assert_not_started(spoc.id)
        self.assert_not_started(mooc.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)

    def test_skip_if_course_option_self_paced_course_reminder_email_not_available(self):
        self._profile(self.user)
        spoc = self._create_spoc_course()
        self._register_contract(self.contract, self.user)

        mooc = self._create_mooc_course()
        self._create_course_option(self.user, mooc, False)
        CourseEnrollmentFactory.create(user=self.user, course_id=mooc.id)

        call_command('send_self_paced_course_closure_reminder_email')

        self.assert_not_started(spoc.id)
        self.assert_not_started(mooc.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.warning.assert_any_call(u"Option for self-paced-course-closure-reminder-email is not available for the course(id={}), so skip.".format(spoc.id))
        self.mock_log.warning.assert_any_call(u"Option for self-paced-course-closure-reminder-email is not available for the course(id={}), so skip.".format(mooc.id))

    def test_skip_global_course(self):
        self._profile(self.user)
        spoc = self._create_spoc_course()
        self._create_course_option(self.user, spoc, True)
        self._register_contract(self.contract, self.user)

        mooc = self._create_mooc_course()
        self._create_course_option(self.user, mooc, True)
        CourseEnrollmentFactory.create(user=self.user, course_id=mooc.id)

        self.course = self._create_global_course()
        self._create_course_option(self.user, self.course, True)
        CourseEnrollmentFactory.create(user=self.user, course_id=self.course.id)

        call_command('send_self_paced_course_closure_reminder_email')

        self.assert_finished(1, 0, spoc.id)
        self.assert_finished(1, 0, mooc.id)
        self.assertEquals(self.mock_send_mail.call_count, 2)
        self.mock_log.warning.assert_called_with(u"Course(id={}) is global course, so skip.".format(self.course.id))

    def test_if_closure_reminder_email_template_not_found(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        self.default_mail_template.delete()

        call_command('send_self_paced_course_closure_reminder_email')

        self.assert_error(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.error.assert_called_once_with(u"Default email template record for self-paced course closure reminder email is not found.")

    def test_if_closure_reminder_email_days_min_is_invalid(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        self.default_mail_template.reminder_email_days = SelfPacedCourseClosureReminderMail.REMINDER_EMAIL_DAYS_MIN_VALUE - 1
        self.default_mail_template.save()

        call_command('send_self_paced_course_closure_reminder_email')

        self.assert_error(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.error.assert_called_once_with(u"The value of the reminder email days is invalid for the course(id={}).".format(str(self.course.id)))

    def test_if_closure_reminder_email_days_max_is_invalid(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        self.default_mail_template.reminder_email_days = SelfPacedCourseClosureReminderMail.REMINDER_EMAIL_DAYS_MAX_VALUE + 1
        self.default_mail_template.save()

        call_command('send_self_paced_course_closure_reminder_email')

        self.assert_error(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.error.assert_called_once_with(u"The value of the reminder email days is invalid for the course(id={}).".format(str(self.course.id)))

    def test_if_course_end_date_is_none(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        with patch('ga_bulk_email.management.commands.send_self_paced_course_closure_reminder_email.get_course_end_date', return_value=None):
            call_command('send_self_paced_course_closure_reminder_email')

        self.assert_finished(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.warning.assert_called_once_with(u"User(id={},name={}) could not get the course(id={}) end date and time.".format(self.user.id, self.user.username, str(self.course.id)))

    def test_error_by_send_email(self):
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        for _ in range(0, 50):
            user = UserFactory.create()
            self._profile(user)
            self._register_contract(self.contract, user)

        ex = Exception('test')
        self.mock_send_mail.side_effect = ex

        call_command('send_self_paced_course_closure_reminder_email')

        self.assert_error(0, 50, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 50)
        self.mock_log.error.assert_any_call(u"Error occurred while sending self-paced course closure reminder email: {}".format(ex))
        self.mock_log.error.assert_any_call(u"Error occurred while sending emails for the course(id={}).".format(self.course.id))

    def test_unexpected_error(self):
        self._profile(self.user)
        spoc = self._create_spoc_course()
        self._create_course_option(self.user, spoc, True)
        self._register_contract(self.contract, self.user)

        mooc = self._create_mooc_course()
        self._create_course_option(self.user, mooc, True)
        CourseEnrollmentFactory.create(user=self.user, course_id=mooc.id)

        ex = Exception('test')

        with patch.object(SelfPacedCourseClosureReminderMail, 'get_or_default', side_effect=ex):
            call_command('send_self_paced_course_closure_reminder_email')

        self.assert_error(0, 0, spoc.id)
        self.assert_error(0, 0, mooc.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.error.assert_called_with(u"Unexpected error occurred: {}".format(ex))

    def test_skip_contract_is_not_active(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        self.contract.end_date = self.yesterday
        self.contract.save()

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)

    def test_success_related_to_multiple_contracts_but_one_contract_is_active(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        not_active_contract = self._create_contract(detail_courses=[self.course], end_date=self.yesterday)
        self._create_contract_option(not_active_contract)
        self._register_contract(not_active_contract, self.user)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(1, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 1)

    def test_skip_related_to_multiple_active_contracts(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        active_contract = self._create_contract(detail_courses=[self.course])
        self._create_contract_option(active_contract)
        self._register_contract(active_contract, self.user)

        spoc_contracts = [self.contract, active_contract]

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.warning.assert_called_once_with(u"Course(id={}) is related to multiple active contracts(id:names[{}]=[{}]), so skip.".format(str(self.course.id), len(spoc_contracts), u",".join([u"{}{}{}".format(str(c.id), u":", c.contract_name) for c in spoc_contracts])))

    def test_skip_related_to_multiple_contracts_and_all_contracts_are_not_active(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)
        self.contract.end_date = self.yesterday
        self.contract.save()

        not_active_contract = self._create_contract(detail_courses=[self.course], end_date=self.yesterday)
        self._create_contract_option(not_active_contract)
        self._register_contract(not_active_contract, self.user)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)

    def test_success_if_biz_user_can_send_mail(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        self._biz_user(self.user, self.contract, send_mail=True)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(1, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 1)

    def test_skip_if_biz_user_can_not_send_mail(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        self._biz_user(self.user, self.contract, send_mail=False)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.warning.assert_called_with(u"The contract(id={},name={}) has contract-auth but send_mail option is False, so skip.".format(self.contract.id, self.contract.contract_name))

    def test_skip_if_user_has_not_enrolled_yet(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._input_contract(self.contract, self.user)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.warning.assert_called_with(u"No active enrollment of course(id={}).".format(str(self.course.id)))

    def test_skip_if_user_not_registered_in_the_invitation_code(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        self._unregister_contract(self.contract, self.user)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.debug.assert_called_with(u"The user(id={},name={}) is not registered in the invitation code of the contract(id={},name={}), so skip.".format(self.user.id, self.user.username, self.contract.id, self.contract.contract_name))

    def test_skip_if_user_already_resigned(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        self._account_disable(self.user)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.debug.assert_called_with(u"The user(id={},name={}) has already resigned, so skip.".format(self.user.id, self.user.username))

    def test_skip_if_user_already_masked(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        mask_utils.mask_email(self.user)

        call_command('send_self_paced_course_closure_reminder_email', str(self.course.id))

        self.assert_finished(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)
        self.mock_log.warning.assert_called_with(u"the user(id={},name={}) has been already masked, so skip.".format(self.user.id, self.user.username))

    def test_if_course_related_to_the_contract_of_gacco_service_are_treated_as_mooc(self):
        self._profile(self.user)
        self.course = self._create_self_paced_course()
        self.contract = self._create_contract(detail_courses=[self.course], contract_type='GS')
        self.contract_option = self._create_contract_option(self.contract)
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        with patch('ga_bulk_email.management.commands.send_self_paced_course_closure_reminder_email._get_target_enrollments', return_value=[]) as mock_get_target_enrollments_spoc:
            call_command('send_self_paced_course_closure_reminder_email')
            mock_get_target_enrollments_spoc.assert_called_once_with(self.course)

    def test_skip_if_course_end_date_non_target(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        with patch('ga_bulk_email.management.commands.send_self_paced_course_closure_reminder_email.get_course_end_date', return_value=self.non_target_datetime):
            call_command('send_self_paced_course_closure_reminder_email')

        self.assert_finished(0, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 0)

    def test_success_send_mail_subject_and_message_and_to_addresses(self):
        self._profile(self.user)
        self.course = self._create_spoc_course()
        self._create_course_option(self.user, self.course, True)
        self._register_contract(self.contract, self.user)

        terminate_date_jp = datetime_utils.to_jst(self.target_datetime).strftime('%Y年%-m月%-d日')  # ex. 2018年1月1日
        terminate_date_en = datetime_utils.to_jst(self.target_datetime).strftime('%d/%m/%Y')  # ex. 01/01/2018

        replace_dict = SelfPacedCourseClosureReminderMail.replace_dict(self.user.profile.name, str(self.course.id), self.course.display_name, terminate_date_jp, terminate_date_en)

        subject = 'Test Subject for Self-paced Course Closure Reminder Email {fullname} {course_id} {course_name} {terminate_date_jp} {terminate_date_en}'.format(**replace_dict)
        message = 'Test Body for Self-paced Course Closure Reminder Email {fullname} {course_id} {course_name} {terminate_date_jp} {terminate_date_en}'.format(**replace_dict)

        call_command('send_self_paced_course_closure_reminder_email')

        self.assert_finished(1, 0, self.course.id)
        self.assertEquals(self.mock_send_mail.call_count, 1)
        args, kwargs = self.mock_send_mail.call_args
        self.assertEquals(args[0], subject)  # subject
        self.assertEquals(args[1], message)  # message
        self.assertEquals(args[3][0], self.user.email)  # to_addresses

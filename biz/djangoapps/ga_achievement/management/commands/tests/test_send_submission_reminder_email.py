"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import logging
import tempfile
from collections import namedtuple

import ddt
from datetime import datetime, timedelta
from dateutil.tz import tzutc
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings
from mock import patch
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from biz.djangoapps.ga_achievement.achievement_store import ScoreStore
from biz.djangoapps.ga_achievement.management.commands import send_submission_reminder_email
from biz.djangoapps.ga_achievement.models import ScoreBatchStatus, SubmissionReminderBatchStatus, BATCH_STATUS_STARTED, \
    BATCH_STATUS_FINISHED, BATCH_STATUS_ERROR
from biz.djangoapps.ga_achievement.tests.factories import ScoreBatchStatusFactory
from biz.djangoapps.ga_contract.tests.factories import ContractAuthFactory, ContractOptionFactory
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from courseware import grades
from courseware.tests.helpers import LoginEnrollmentTestCase
from student.tests.factories import UserFactory, UserProfileFactory

command_output_file = tempfile.NamedTemporaryFile()

ADDITIONAL_DISPLAY_NAME1 = 'test_number'
ADDITIONAL_DISPLAY_NAME2 = 'test_section'
ADDITIONAL_SETTINGS_VALUE = 'test_value'
DEFAULT_KEY = [
    ScoreStore.FIELD_CONTRACT_ID,
    ScoreStore.FIELD_COURSE_ID,
    ScoreStore.FIELD_LOGIN_CODE,
    ScoreStore.FIELD_FULL_NAME,
    ScoreStore.FIELD_USERNAME,
    ScoreStore.FIELD_EMAIL,
    ScoreStore.FIELD_STUDENT_STATUS,
    ScoreStore.FIELD_CERTIFICATE_STATUS,
    ScoreStore.FIELD_ENROLL_DATE,
    ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE,
    ScoreStore.FIELD_TOTAL_SCORE,
    ADDITIONAL_DISPLAY_NAME1,
    ADDITIONAL_DISPLAY_NAME2,
]

BlockInfo = namedtuple('BlockInfo', 'block_id, category, fields, sub_tree')


class TestArgParsing(TestCase):
    """
    Tests for parsing arguments of the `send_submission_reminder_email` command
    """
    def setUp(self):
        super(TestArgParsing, self).setUp()
        self.command = send_submission_reminder_email.Command()

    def test_args_debug(self):
        self.command.execute(debug=True)
        self.assertEquals(send_submission_reminder_email.log.level, logging.DEBUG)

    def test_excludes_as_empty_string(self):
        with patch('django.db.models.query.QuerySet.exclude', return_value='[]') as mock_exclude:
            self.command.execute(excludes='')
            mock_exclude.assert_called_once_with(id__in=[])

    def test_excludes_as_integer(self):
        with patch('django.db.models.query.QuerySet.exclude', return_value='[]') as mock_exclude:
            self.command.execute(excludes='1')
            mock_exclude.assert_called_once_with(id__in=[1])

    def test_excludes_as_comma_delimited_integers(self):
        with patch('django.db.models.query.QuerySet.exclude', return_value='[]') as mock_exclude:
            self.command.execute(excludes='1,2')
            mock_exclude.assert_called_once_with(id__in=[1, 2])

    def test_invalid_excludes(self):
        errstring = "excludes should be specified as comma-delimited integers \(like 1 or 1,2\)."
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, excludes='a')

    def test_exclude_ids_and_contract_ids(self):
        errstring = "Cannot specify exclude_ids and contract_id at the same time."
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, 1, excludes='2')

    def test_too_much_args(self):
        """
        Tests for the case when too much args are specified
        """
        errstring = "This command requires one or no arguments: |<contract_id>|"
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, 1, 2)

    def test_invalid_contract_id(self):
        """
        Tests for the case when invalid contract_id is specified
        """
        errstring = "The specified contract does not exist or is not active."
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, 99999999)


@ddt.ddt
@override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=command_output_file.name)
class SendSubmissionReminderEmailTest(BizStoreTestBase, ModuleStoreTestCase, LoginEnrollmentTestCase):

    def _profile(self, user):
        UserProfileFactory.create(user=user, name='profile_name')

    def _biz_user(self, user, contract, send_mail):
        BizUserFactory.create(user=user, login_code='test-login-code')
        ContractAuthFactory.create(contract=contract, url_code='test-url-code', send_mail=send_mail)

    def _create_score_batch_status(self, contract, course, status, count=None):
        ScoreBatchStatusFactory.create(contract=contract,
                                       course_id=unicode(course.id),
                                       status=status,
                                       student_count=count)

    def _create_contract_option(self, contract, send_submission_reminder=True):
        return ContractOptionFactory.create(contract=contract, send_submission_reminder=send_submission_reminder)

    def setUp(self):
        super(SendSubmissionReminderEmailTest, self).setUp()
        self.now = datetime_utils.timezone_now()
        self.target_datetime = self.now.replace(hour=20) + timedelta(days=settings.INTERVAL_DAYS_TO_SEND_SUBMISSION_REMINDER_EMAIL)
        self.non_target_datetime = self.now.replace(hour=20) + timedelta(days=settings.INTERVAL_DAYS_TO_SEND_SUBMISSION_REMINDER_EMAIL + 1)

        self.course_blocks = [
            BlockInfo(
                'chapter_x', 'chapter', {'display_name': 'chapter_x'}, [
                    BlockInfo(
                        'sequential_x1', 'sequential', {'display_name': 'sequential_x1', 'due': self.target_datetime}, [
                            BlockInfo(
                                'vertical_x1a', 'vertical', {'display_name': 'vertical_x1a'}, [
                                    BlockInfo('component_x1a_1', 'problem', {'display_name': 'component_x1a_1'}, []),
                                ]
                            ),
                            BlockInfo(
                                'vertical_x1b', 'vertical', {'display_name': 'vertical_x1b'}, [
                                    BlockInfo('component_x1b_1', 'about', {'display_name': 'component_x1b_1'}, []),
                                ]
                            ),
                        ]
                    ),
                ]
            ),
            BlockInfo(
                'chapter_y', 'chapter', {'display_name': 'chapter_y'}, [
                    BlockInfo(
                        'sequential_y1', 'sequential', {'display_name': 'sequential_y1'}, [
                            BlockInfo(
                                'vertical_y1a', 'vertical', {'display_name': 'vertical_y1a'}, [
                                    BlockInfo('component_y1a_1', 'problem', {'display_name': 'component_y1a_1'}, []),
                                ]
                            ),
                        ]
                    ),
                    BlockInfo(
                        'sequential_y2', 'sequential', {'display_name': 'sequential_y2'}, [
                            BlockInfo(
                                'vertical_y2a', 'vertical', {'display_name': 'vertical_y2a'}, [
                                    BlockInfo('component_y2a_1', 'problem', {'display_name': 'component_y2a_1'}, []),
                                ]
                            ),
                        ]
                    ),
                ]
            ),
        ]
        self.course = self._create_course(self.gacco_organization.org_code, 'course', 'run', self.course_blocks)
        self.contract = self._create_contract(detail_courses=[self.course])
        # Contract option
        self.contract_option = self._create_contract_option(self.contract)

        # Setup mock
        patcher_grade = patch.object(grades, 'grade')
        self.mock_grade = patcher_grade.start()
        self.mock_grade.return_value = {
            'totaled_scores': {},
            'percent': 0,
        }
        self.addCleanup(patcher_grade.stop)

        patcher_exists_today = patch.object(ScoreBatchStatus, 'exists_today')
        self.mock_exists_today = patcher_exists_today.start()
        self.mock_exists_today.return_value = False
        self.addCleanup(patcher_exists_today.stop)

        patcher_send_mail = patch('biz.djangoapps.ga_achievement.management.commands.send_submission_reminder_email.send_mail')
        self.mock_send_mail = patcher_send_mail.start()
        self.addCleanup(patcher_send_mail.stop)

        patcher_log = patch('biz.djangoapps.ga_achievement.management.commands.send_submission_reminder_email.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

    def assert_not_started(self, contract):
        self.assertFalse(SubmissionReminderBatchStatus.objects.filter(contract=contract).exists())

    def assert_finished(self, success_count, failure_count, contract):
        SubmissionReminderBatchStatus.objects.get(contract=contract, status=BATCH_STATUS_STARTED)
        SubmissionReminderBatchStatus.objects.get(contract=contract, status=BATCH_STATUS_FINISHED,
                                                  success_count=success_count, failure_count=failure_count)

    def assert_error(self, success_count, failure_count, contract):
        SubmissionReminderBatchStatus.objects.get(contract=contract, status=BATCH_STATUS_STARTED)
        SubmissionReminderBatchStatus.objects.get(contract=contract, status=BATCH_STATUS_ERROR,
                                                  success_count=success_count, failure_count=failure_count)

    def test_success(self):
        self._profile(self.user)
        self._register_contract(self.contract, self.user)

        # Update score status (mark some sections as 'not attempted')
        call_command('update_biz_score_status', self.contract.id)

        call_command('send_submission_reminder_email', self.contract.id)
        self.assert_finished(1, 0, self.contract)
        self.assertEquals(self.mock_send_mail.call_count, 1)

    def test_success_using_debug_option(self):
        self._profile(self.user)
        self._register_contract(self.contract, self.user)

        # Update score status (mark some sections as 'not attempted')
        call_command('update_biz_score_status', self.contract.id)

        call_command('send_submission_reminder_email', self.contract.id, debug=True)
        self.assert_finished(1, 0, self.contract)
        self.assertEquals(self.mock_send_mail.call_count, 0)

    def test_success_with_multi_users(self):
        for _ in range(0, 50):
            user = UserFactory.create()
            self._profile(user)
            self._register_contract(self.contract, user)

        # Update score status (mark some sections as 'not attempted')
        call_command('update_biz_score_status', self.contract.id)

        call_command('send_submission_reminder_email', self.contract.id)
        self.assert_finished(50, 0, self.contract)
        self.assertEquals(self.mock_send_mail.call_count, 50)

    def test_skip_if_cannot_send_submission_reminder(self):
        """If contract option for send_submission_reminder is False, then skip"""
        self._profile(self.user)
        self._register_contract(self.contract, self.user)
        self.contract_option.send_submission_reminder = False
        self.contract_option.save()

        call_command('send_submission_reminder_email', self.contract.id)
        self.assert_not_started(self.contract)
        self.mock_log.warning.assert_called_with(
            u"Option for send_submission_reminder is not available for the contract(id={}), so skip.".format(self.contract.id))

    def test_skip_if_contract_auth_send_mail_is_false(self):
        """If contract has contract-auth and send_mail option is False, then skip"""
        self._profile(self.user)
        self._register_contract(self.contract, self.user)
        self._biz_user(self.user, self.contract, send_mail=False)

        call_command('send_submission_reminder_email', self.contract.id)
        self.assert_not_started(self.contract)
        self.mock_log.warning.assert_called_with(
            u"Contract(id={}) has contract-auth but send_mail option is False, so skip.".format(self.contract.id))

    def test_success_if_contract_auth_send_mail_is_true(self):
        """If contract has contract-auth and send_mail option is True, then success"""
        self._profile(self.user)
        self._register_contract(self.contract, self.user)
        self._biz_user(self.user, self.contract, send_mail=True)

        # Update score status (mark some sections as 'not attempted')
        call_command('update_biz_score_status', self.contract.id)

        call_command('send_submission_reminder_email', self.contract.id)
        self.assert_finished(1, 0, self.contract)

    def test_if_course_does_not_exist(self):
        not_exist_course_id = CourseKey.from_string('course-v1:not+exist+course')
        not_exist_course_contract = self._create_contract(
            detail_courses=[not_exist_course_id],
        )
        self._create_contract_option(not_exist_course_contract)
        self._profile(self.user)
        self._register_contract(not_exist_course_contract, self.user)

        call_command('send_submission_reminder_email', not_exist_course_contract.id)
        self.assert_finished(0, 0, not_exist_course_contract)
        warning_messages = [call[0][0] for call in self.mock_log.warning.call_args_list]
        self.assertEquals(warning_messages[0],
                          u"This course does not exist in modulestore. contract_id={}, course_id={}".format(
                              not_exist_course_contract.id, unicode(not_exist_course_id)))
        self.assertEquals(warning_messages[1],
                          u"Contract(id={}) has no target courses for submission reminder today, so skip.".format(
                              not_exist_course_contract.id))

    def test_if_self_paced(self):
        individual_end_days = 10
        self_paced_course = self._create_course(
            self.gacco_organization.org_code, 'self_paced_course', 'run',
            self.course_blocks,
            {
                'start': datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
                'self_paced': True,
                'individual_end_days': individual_end_days,
            }
        )
        self_paced_contract = self._create_contract(detail_courses=[self_paced_course])
        self._create_contract_option(self_paced_contract)
        self._profile(self.user)
        self._register_contract(self_paced_contract, self.user)

        call_command('send_submission_reminder_email', self_paced_contract.id)

        self.assert_finished(0, 0, self_paced_contract)
        warning_messages = [call[0][0] for call in self.mock_log.warning.call_args_list]
        self.assertEquals(warning_messages[0],
                          u"This course is self-paced. So, we exclude it from the target courses. contract_id={}, course_id={}".format(
                              self_paced_contract.id, unicode(self_paced_course.id)))
        self.assertEquals(warning_messages[1],
                          u"Contract(id={}) has no target courses for submission reminder today, so skip.".format(
                              self_paced_contract.id))

    def test_error_by_score_batch_not_finished(self):
        self._create_score_batch_status(self.contract, self.course, BATCH_STATUS_ERROR)

        self._profile(self.user)
        self._register_contract(self.contract, self.user)

        call_command('send_submission_reminder_email', self.contract.id)
        self.assert_error(0, 0, self.contract)
        self.mock_log.error.assert_called_once_with(
            u"Score batches for the contract(id={}) have not finished yet today.".format(self.contract.id))

    def test_if_user_already_resigned(self):
        self._profile(self.user)
        self._register_contract(self.contract, self.user)
        self._account_disable(self.user)

        # Update score status (mark some sections as 'not attempted')
        call_command('update_biz_score_status', self.contract.id)

        call_command('send_submission_reminder_email', self.contract.id)
        self.assert_finished(0, 0, self.contract)

    def test_if_user_has_not_enrolled_yet(self):
        self._profile(self.user)
        self._input_contract(self.contract, self.user)

        # Update score status (mark some sections as 'not attempted')
        call_command('update_biz_score_status', self.contract.id)

        call_command('send_submission_reminder_email', self.contract.id)
        self.assert_finished(0, 0, self.contract)

    def test_if_user_has_enrolled_after_score_batch_finished(self):
        self._profile(self.user)
        self._register_contract(self.contract, self.user)

        # Update score status (mark some sections as 'not attempted')
        call_command('update_biz_score_status', self.contract.id)

        # User enrolled after update_biz_score_status finished
        user = UserFactory.create()
        self._profile(user)
        self._register_contract(self.contract, user)

        call_command('send_submission_reminder_email', self.contract.id)
        self.assert_finished(2, 0, self.contract)
        self.assertEquals(self.mock_send_mail.call_count, 2)

    def test_error_by_send_email(self):
        self.mock_send_mail.side_effect = Exception()

        for _ in range(0, 50):
            user = UserFactory.create()
            self._profile(user)
            self._register_contract(self.contract, user)

        # Update score status (mark some sections as 'not attempted')
        call_command('update_biz_score_status', self.contract.id)

        call_command('send_submission_reminder_email', self.contract.id)
        self.assert_error(0, 50, self.contract)
        self.mock_log.error.assert_called_with(
            u"Error occurred while sending emails for the contract(id={}).".format(self.contract.id))

    def test_unexpected_error(self):
        self._profile(self.user)
        self._register_contract(self.contract, self.user)

        # Setup another contract
        another_course = self._create_course(self.gacco_organization.org_code, 'another_course', 'run', self.course_blocks)
        another_contract = self._create_contract(detail_courses=[another_course])
        self._create_contract_option(another_contract)
        self._register_contract(another_contract, self.user)

        # Update score status (mark some sections as 'not attempted')
        call_command('update_biz_score_status')

        ex = Exception('test')
        with patch.object(ScoreStore, 'get_record_document_by_username', side_effect=ex):
            call_command('send_submission_reminder_email')

        self.assert_error(0, 0, self.contract)
        self.assert_error(0, 0, another_contract)
        self.mock_log.error.assert_called_with(u"Unexpected error occurred: {}".format(ex))

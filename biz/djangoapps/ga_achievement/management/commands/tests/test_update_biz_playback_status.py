"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from collections import namedtuple
from datetime import datetime, timedelta
from dateutil.tz import tzutc
import ddt
import logging
from mock import patch
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore
from biz.djangoapps.ga_achievement.management.commands import update_biz_playback_status
from biz.djangoapps.ga_achievement.management.commands.update_biz_playback_status import (
    TargetVertical, GroupedTargetVerticals, get_grouped_target_verticals
)
from biz.djangoapps.ga_achievement.models import PlaybackBatchStatus, BATCH_STATUS_STARTED, BATCH_STATUS_FINISHED, BATCH_STATUS_ERROR
from biz.djangoapps.ga_achievement.tests.factories import PlaybackBatchStatusFactory
from biz.djangoapps.ga_contract.tests.factories import ContractAuthFactory
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.util.decorators import ExitWithWarning
from biz.djangoapps.util.hash_utils import to_target_id
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from lms.djangoapps.courseware.tests.helpers import LoginEnrollmentTestCase
from opaque_keys.edx.keys import CourseKey
from student.models import CourseEnrollment
from student.tests.factories import UserFactory, UserProfileFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory

command_output_file = tempfile.NamedTemporaryFile()

ADDITIONAL_DISPLAY_NAME1 = 'test_number'
ADDITIONAL_DISPLAY_NAME2 = 'test_section'
ADDITIONAL_SETTINGS_VALUE = 'test_value'
DEFAULT_KEY = [
    PlaybackStore.FIELD_FULL_NAME,
    PlaybackStore.FIELD_USERNAME,
    PlaybackStore.FIELD_EMAIL,
    PlaybackStore.FIELD_STUDENT_STATUS,
    ADDITIONAL_DISPLAY_NAME1,
    ADDITIONAL_DISPLAY_NAME2,
]

BlockInfo = namedtuple('BlockInfo', 'block_id, category, fields, sub_tree')  # pylint: disable=invalid-name
no_spoc_video_block = [  # pylint: disable=invalid-name
    BlockInfo(
        'chapter_x', 'chapter', {'display_name': 'chapter_x'}, [
            BlockInfo(
                'sequential_x1', 'sequential', {'display_name': 'sequential_x1'}, [
                    BlockInfo(
                        'vertical_x1a', 'vertical', {'display_name': 'vertical_x1a'}, [
                            BlockInfo('problem_x1a_1', 'problem', {'display_name': 'problem_x1a_1'}, []),
                        ]
                    ),
                ]
            ),
        ]
    ),
]
single_spoc_video_block = [  # pylint: disable=invalid-name
    BlockInfo(
        'chapter_x', 'chapter', {'display_name': 'chapter_x'}, [
            BlockInfo(
                'sequential_x1', 'sequential', {'display_name': 'sequential_x1'}, [
                    BlockInfo(
                        'vertical_x1a', 'vertical', {'display_name': 'vertical_x1a'}, [
                            BlockInfo('spoc_video_x1a_1', 'jwplayerxblock', {'display_name': 'spoc_video_x1a_1'}, []),
                        ]
                    ),
                ]
            ),
        ]
    ),
]
multiple_spoc_video_block = [  # pylint: disable=invalid-name
    BlockInfo(
        'chapter_x', 'chapter', {'display_name': 'chapter_x'}, [
            BlockInfo(
                'sequential_x1', 'sequential', {'display_name': 'sequential_x1'}, [
                    BlockInfo(
                        'vertical_x1a', 'vertical', {'display_name': 'vertical_x1a'}, [
                            BlockInfo('component_x1a_1', 'jwplayerxblock', {'display_name': 'component_x1a_1'}, []),
                        ]
                    ),
                    BlockInfo(
                        'vertical_x1b', 'vertical', {'display_name': 'vertical_x1b'}, [
                            BlockInfo('component_x1b_1', 'problem', {'display_name': 'component_x1b_1'}, []),
                        ]
                    ),
                    BlockInfo(
                        'vertical_x1c', 'vertical', {'display_name': 'vertical_x1c'}, [
                            BlockInfo('component_x1c_1', 'problem', {'display_name': 'component_x1c_1'}, []),
                            BlockInfo('component_x1c_2', 'jwplayerxblock', {'display_name': 'component_x1c_2'}, []),
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
                            BlockInfo('component_y1a_1', 'jwplayerxblock', {'display_name': 'component_y1a_1'}, []),
                        ]
                    ),
                ]
            ),
        ]
    ),
]


class TestArgParsing(TestCase):
    """
    Tests for parsing arguments of the `update_biz_playback_status` command
    """
    def setUp(self):
        super(TestArgParsing, self).setUp()
        self.command = update_biz_playback_status.Command()

    def test_args_debug(self):
        self.command.execute(debug=True)
        self.assertEquals(update_biz_playback_status.log.level, logging.DEBUG)

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
        contract_id = 99999999
        errstring = "The specified contract does not exist or is not active. contract_id={}".format(contract_id)
        with self.assertRaisesRegexp(ExitWithWarning, errstring):
            self.command.handle._original(self.command, contract_id)


@ddt.ddt
@override_settings(BIZ_SET_PLAYBACK_COMMAND_OUTPUT=command_output_file.name)
class UpdateBizPlaybackStatusTest(BizStoreTestBase, ModuleStoreTestCase, LoginEnrollmentTestCase):

    def setUp(self):
        super(UpdateBizPlaybackStatusTest, self).setUp()
        # Course
        self.no_spoc_video_course = self._create_course(self.gacco_organization.org_code, 'no_spoc_video_course', 'run', no_spoc_video_block)
        self.single_spoc_video_course = self._create_course(self.gacco_organization.org_code, 'single_spoc_video_course', 'run', single_spoc_video_block)
        self.multiple_spoc_video_course = self._create_course(self.gacco_organization.org_code, 'multiple_spoc_video_course', 'run', multiple_spoc_video_block)
        # Self-paced course
        self.individual_end_days = 10
        self.self_paced_course = self._create_course(self.gacco_organization.org_code, 'self_paced_course', 'run', no_spoc_video_block)
        self.self_paced_course.start = datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc())  # must be the past date
        self.self_paced_course.self_paced = True
        self.self_paced_course.individual_end_days = self.individual_end_days
        self.update_course(self.self_paced_course, self.user.id)

        # Contract with no SPOC video course
        self.no_spoc_video_contract = self._create_contract(
            detail_courses=[self.no_spoc_video_course],
            additional_display_names=[ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_DISPLAY_NAME2],
        )
        # Contract with no additional info
        self.no_additional_info_contract = self._create_contract(
            detail_courses=[self.no_spoc_video_course],
        )
        # Contract with single SPOC video course
        self.single_spoc_video_contract = self._create_contract(
            detail_courses=[self.single_spoc_video_course],
            additional_display_names=[ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_DISPLAY_NAME2],
        )
        # Contract with multiple SPOC video courses
        self.multiple_spoc_video_contract = self._create_contract(
            detail_courses=[self.multiple_spoc_video_course],
            additional_display_names=[ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_DISPLAY_NAME2],
        )
        # Contract with multiple courses
        self.multiple_courses_contract = self._create_contract(
            detail_courses=[self.single_spoc_video_course, self.multiple_spoc_video_course],
            additional_display_names=[ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_DISPLAY_NAME2],
        )
        # Contract with self-paced course
        self.self_paced_contract = self._create_contract(
            detail_courses=[self.self_paced_course],
            additional_display_names=[ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_DISPLAY_NAME2],
        )

        # Setup mock
        patcher_aggregate = patch.object(update_biz_playback_status.PlaybackLogStore, 'aggregate_sum')
        self.mock_aggregate = patcher_aggregate.start()
        self.mock_aggregate.return_value = {}
        self.addCleanup(patcher_aggregate.stop)

        patcher_log = patch('biz.djangoapps.ga_achievement.management.commands.update_biz_playback_status.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

    def _profile(self, user):
        UserProfileFactory.create(user=user, name='profile_name')

    def _unenroll(self, user, course):
        CourseEnrollment.unenroll(user, course.id)

    def _biz_user(self, user, login_code, contract):
        if login_code:
            BizUserFactory.create(user=user, login_code=login_code)
            ContractAuthFactory.create(contract=contract)

    def assert_finished(self, count, contract, course):
        PlaybackBatchStatus.objects.get(contract=contract, course_id=course.id, status=BATCH_STATUS_STARTED)
        PlaybackBatchStatus.objects.get(contract=contract, course_id=course.id, status=BATCH_STATUS_FINISHED, student_count=count)

        column_list = PlaybackStore(contract.id, unicode(course.id)).get_documents(
            conditions={PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN}
        )
        record_list = PlaybackStore(contract.id, unicode(course.id)).get_documents(
            conditions={PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD}
        )
        if count == 0:
            self.assertEquals(len(column_list), 0)
            self.assertEquals(len(record_list), 0)
        else:
            self.assertEquals(len(column_list), 1)
            self.assertEquals(len(record_list), count)
        return column_list, record_list

    def assert_error(self, contract, course_id):
        PlaybackBatchStatus.objects.get(contract=contract, course_id=course_id, status=BATCH_STATUS_STARTED)
        PlaybackBatchStatus.objects.get(contract=contract, course_id=course_id, status=BATCH_STATUS_ERROR, student_count=None)

        playback_list = PlaybackStore(contract.id, unicode(course_id)).get_documents()
        self.assertEquals(len(playback_list), 0)
        return playback_list

    def test_contract_with_no_user(self):
        call_command('update_biz_playback_status', self.no_spoc_video_contract.id)

        self.assert_finished(0, self.no_spoc_video_contract, self.no_spoc_video_course)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_not_enrolled_user(self, login_code):
        self._input_contract(self.no_spoc_video_contract, self.user)
        self._biz_user(self.user, login_code, self.no_spoc_video_contract)

        call_command('update_biz_playback_status', self.no_spoc_video_contract.id)

        def assert_playback(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)

            column_dict = column_list[0]
            column_items = column_dict.iteritems()
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN))
            if login_code:
                self.assertEquals(column_items.next(), (PlaybackStore.FIELD_LOGIN_CODE, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_FULL_NAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_USERNAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_EMAIL, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertRaises(StopIteration, column_items.next)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD))
            if login_code:
                self.assertEquals(record_items.next(), (PlaybackStore.FIELD_LOGIN_CODE, login_code))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_FULL_NAME, None))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, None))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, None))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__NOT_ENROLLED))
            self.assertRaises(StopIteration, record_items.next)

        assert_playback(self.no_spoc_video_contract, self.no_spoc_video_course)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_enrolled_user(self, login_code):
        self._profile(self.user)
        self._register_contract(self.no_spoc_video_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._biz_user(self.user, login_code, self.no_spoc_video_contract)

        call_command('update_biz_playback_status', self.no_spoc_video_contract.id)

        def assert_playback(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)

            column_dict = column_list[0]
            column_items = column_dict.iteritems()
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN))
            if login_code:
                self.assertEquals(column_items.next(), (PlaybackStore.FIELD_LOGIN_CODE, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_FULL_NAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_USERNAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_EMAIL, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertRaises(StopIteration, column_items.next)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD))
            if login_code:
                self.assertEquals(record_items.next(), (PlaybackStore.FIELD_LOGIN_CODE, login_code))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__ENROLLED))
            self.assertRaises(StopIteration, record_items.next)

        assert_playback(self.no_spoc_video_contract, self.no_spoc_video_course)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_unenrolled_user(self, login_code):
        self._profile(self.user)
        self._register_contract(self.no_spoc_video_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._unenroll(self.user, self.no_spoc_video_course)
        self._biz_user(self.user, login_code, self.no_spoc_video_contract)

        call_command('update_biz_playback_status', self.no_spoc_video_contract.id)

        def assert_playback(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)

            column_dict = column_list[0]
            column_items = column_dict.iteritems()
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN))
            if login_code:
                self.assertEquals(column_items.next(), (PlaybackStore.FIELD_LOGIN_CODE, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_FULL_NAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_USERNAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_EMAIL, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertRaises(StopIteration, column_items.next)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD))
            if login_code:
                self.assertEquals(record_items.next(), (PlaybackStore.FIELD_LOGIN_CODE, login_code))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__UNENROLLED))
            self.assertRaises(StopIteration, record_items.next)

        assert_playback(self.no_spoc_video_contract, self.no_spoc_video_course)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_disabled_user(self, login_code):
        self._profile(self.user)
        self._register_contract(self.no_spoc_video_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._account_disable(self.user)
        self._biz_user(self.user, login_code, self.no_spoc_video_contract)

        call_command('update_biz_playback_status', self.no_spoc_video_contract.id)

        def assert_playback(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)

            column_dict = column_list[0]
            column_items = column_dict.iteritems()
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN))
            if login_code:
                self.assertEquals(column_items.next(), (PlaybackStore.FIELD_LOGIN_CODE, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_FULL_NAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_USERNAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_EMAIL, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertRaises(StopIteration, column_items.next)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD))
            if login_code:
                self.assertEquals(record_items.next(), (PlaybackStore.FIELD_LOGIN_CODE, login_code))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__DISABLED))
            self.assertRaises(StopIteration, record_items.next)

        assert_playback(self.no_spoc_video_contract, self.no_spoc_video_course)

    def test_contract_with_no_additional_info(self):
        self._input_contract(self.no_additional_info_contract, self.user)

        call_command('update_biz_playback_status', self.no_additional_info_contract.id)

        def assert_playback(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)

            column_dict = column_list[0]
            column_items = column_dict.iteritems()
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_FULL_NAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_USERNAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_EMAIL, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertRaises(StopIteration, column_items.next)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_FULL_NAME, None))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__NOT_ENROLLED))
            self.assertRaises(StopIteration, record_items.next)

        assert_playback(self.no_additional_info_contract, self.no_spoc_video_course)

    def test_contract_with_single_spoc_video(self):
        self._profile(self.user)
        self._register_contract(self.single_spoc_video_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        target_id = to_target_id(self.user.id)
        self.mock_aggregate.return_value = {
            u'vertical_x1a___{}'.format(target_id): 100.0,
        }
        call_command('update_biz_playback_status', self.single_spoc_video_contract.id)

        def assert_playback(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)

            column_dict = column_list[0]
            column_items = column_dict.iteritems()
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_FULL_NAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_USERNAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_EMAIL, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME, PlaybackStore.COLUMN_TYPE__TIME))
            self.assertEquals(column_items.next(), ('chapter_x' + PlaybackStore.FIELD_DELIMITER + 'vertical_x1a', PlaybackStore.COLUMN_TYPE__TIME))
            self.assertEquals(column_items.next(), ('chapter_x' + PlaybackStore.FIELD_DELIMITER + PlaybackStore.FIELD_SECTION_PLAYBACK_TIME, PlaybackStore.COLUMN_TYPE__TIME))
            self.assertRaises(StopIteration, column_items.next)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__ENROLLED))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME, 100.0))
            self.assertEquals(record_items.next(), ('chapter_x' + PlaybackStore.FIELD_DELIMITER + 'vertical_x1a', 100.0))
            self.assertEquals(record_items.next(), ('chapter_x' + PlaybackStore.FIELD_DELIMITER + PlaybackStore.FIELD_SECTION_PLAYBACK_TIME, 100.0))
            self.assertRaises(StopIteration, record_items.next)

        assert_playback(self.single_spoc_video_contract, self.single_spoc_video_course)

    def test_contract_with_multiple_spoc_video(self):
        self._profile(self.user)
        self._register_contract(self.multiple_spoc_video_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        target_id = to_target_id(self.user.id)
        self.mock_aggregate.return_value = {
            u'vertical_x1a___{}'.format(target_id): 100.0,
            u'vertical_x1c___{}'.format(target_id): 200.0,
            u'vertical_y1a___{}'.format(target_id): 400.0,
        }
        call_command('update_biz_playback_status', self.multiple_spoc_video_contract.id)

        def assert_playback(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)

            column_dict = column_list[0]
            column_items = column_dict.iteritems()
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_FULL_NAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_USERNAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_EMAIL, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME, PlaybackStore.COLUMN_TYPE__TIME))
            self.assertEquals(column_items.next(), ('chapter_x' + PlaybackStore.FIELD_DELIMITER + 'vertical_x1a', PlaybackStore.COLUMN_TYPE__TIME))
            self.assertEquals(column_items.next(), ('chapter_x' + PlaybackStore.FIELD_DELIMITER + 'vertical_x1c', PlaybackStore.COLUMN_TYPE__TIME))
            self.assertEquals(column_items.next(), ('chapter_x' + PlaybackStore.FIELD_DELIMITER + PlaybackStore.FIELD_SECTION_PLAYBACK_TIME, PlaybackStore.COLUMN_TYPE__TIME))
            self.assertEquals(column_items.next(), ('chapter_y' + PlaybackStore.FIELD_DELIMITER + 'vertical_y1a', PlaybackStore.COLUMN_TYPE__TIME))
            self.assertEquals(column_items.next(), ('chapter_y' + PlaybackStore.FIELD_DELIMITER + PlaybackStore.FIELD_SECTION_PLAYBACK_TIME, PlaybackStore.COLUMN_TYPE__TIME))
            self.assertRaises(StopIteration, column_items.next)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__ENROLLED))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME, 700.0))
            self.assertEquals(record_items.next(), ('chapter_x' + PlaybackStore.FIELD_DELIMITER + 'vertical_x1a', 100.0))
            self.assertEquals(record_items.next(), ('chapter_x' + PlaybackStore.FIELD_DELIMITER + 'vertical_x1c', 200.0))
            self.assertEquals(record_items.next(), ('chapter_x' + PlaybackStore.FIELD_DELIMITER + PlaybackStore.FIELD_SECTION_PLAYBACK_TIME, 300.0))
            self.assertEquals(record_items.next(), ('chapter_y' + PlaybackStore.FIELD_DELIMITER + 'vertical_y1a', 400.0))
            self.assertEquals(record_items.next(), ('chapter_y' + PlaybackStore.FIELD_DELIMITER + PlaybackStore.FIELD_SECTION_PLAYBACK_TIME, 400.0))
            self.assertRaises(StopIteration, record_items.next)

        assert_playback(self.multiple_spoc_video_contract, self.multiple_spoc_video_course)

    def test_contract_with_expired_self_paced_course(self):
        """
        When:
            - The contract includes a self-paced course.
            - The self-paced course has already expired for the user (today is later than the end date).
        Then:
            - 'Student Status' is set to 'Expired'.
        """
        self._profile(self.user)
        self._register_contract(self.self_paced_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        # Update enrollment.created to simulate a scenario that the self-paced course has expired
        enrollment = CourseEnrollment.get_enrollment(self.user, self.self_paced_course.id)
        enrollment.created = enrollment.created - timedelta(days=self.individual_end_days + 1)
        enrollment.save()

        call_command('update_biz_playback_status', self.self_paced_contract.id)

        def assert_playback(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)

            column_dict = column_list[0]
            column_items = column_dict.iteritems()
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_FULL_NAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_USERNAME, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_EMAIL, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertEquals(column_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.COLUMN_TYPE__TEXT))
            self.assertRaises(StopIteration, column_items.next)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__EXPIRED))
            self.assertRaises(StopIteration, record_items.next)

        assert_playback(self.self_paced_contract, self.self_paced_course)

    def test_target_user_count(self):
        for var in range(0, 50):
            user = UserFactory.create()
            self._input_contract(self.multiple_courses_contract, user)
        for var in range(0, 50):
            user = UserFactory.create()
            self._register_contract(self.multiple_courses_contract, user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        for var in range(0, 50):
            user = UserFactory.create()
            self._unregister_contract(self.multiple_courses_contract, user)

        self.mock_aggregate.return_value = {}
        call_command('update_biz_playback_status', self.multiple_courses_contract.id)

        self.assert_finished(100, self.multiple_courses_contract, self.single_spoc_video_course)
        self.assert_finished(100, self.multiple_courses_contract, self.multiple_spoc_video_course)

    def test_course_does_not_exist(self):

        not_exist_course_id = CourseKey.from_string('course-v1:not+exist+course')
        not_exist_course_contract = self._create_contract(
            detail_courses=[not_exist_course_id],
        )

        call_command('update_biz_playback_status', not_exist_course_contract.id)

        self.assert_error(not_exist_course_contract, not_exist_course_id)
        self.mock_log.warning.assert_called_once()

    def test_error(self):
        self.mock_aggregate.side_effect = Exception()
        self._input_contract(self.single_spoc_video_contract, self.user)
        self._input_contract(self.multiple_spoc_video_contract, self.user)

        call_command('update_biz_playback_status')

        self.assert_error(self.single_spoc_video_contract, self.single_spoc_video_course.id)
        self.assert_error(self.multiple_spoc_video_contract, self.multiple_spoc_video_course.id)
        self.mock_log.error.assert_called_once()

    def _create_batch_status(self, contract, course, status, count=None):
        self.batch_status = PlaybackBatchStatusFactory.create(contract=contract,
                                                              course_id=unicode(course.id),
                                                              status=status,
                                                              student_count=count)

    def test_if_batch_status_exist_today(self):
        self._create_batch_status(self.multiple_courses_contract, self.single_spoc_video_course, BATCH_STATUS_ERROR)
        self._register_contract(self.multiple_courses_contract, self.user)

        call_command('update_biz_playback_status')

        def assert_not_started(contract, course):
            self.assertFalse(PlaybackBatchStatus.objects.filter(contract=contract, course_id=course.id,
                                                                status=BATCH_STATUS_STARTED).exists())
            self.assertFalse(PlaybackBatchStatus.objects.filter(contract=contract, course_id=course.id,
                                                                status=BATCH_STATUS_FINISHED).exists())
            self.assertEquals(len(PlaybackStore(contract.id, unicode(course.id)).get_documents()), 0)

        assert_not_started(self.multiple_courses_contract, self.single_spoc_video_course)
        assert_not_started(self.multiple_courses_contract, self.multiple_spoc_video_course)

    def test_force_if_batch_status_exist_today(self):
        self._create_batch_status(self.multiple_courses_contract, self.single_spoc_video_course, BATCH_STATUS_ERROR)
        self._register_contract(self.multiple_courses_contract, self.user)

        call_command('update_biz_playback_status', force=True)

        self.assert_finished(1, self.multiple_courses_contract, self.single_spoc_video_course)
        self.assert_finished(1, self.multiple_courses_contract, self.multiple_spoc_video_course)

    def test_success_log(self):
        for var in range(0, 50):
            user = UserFactory.create()
            self._input_contract(self.multiple_courses_contract, user)
        for var in range(0, 50):
            user = UserFactory.create()
            self._register_contract(self.multiple_courses_contract, user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        call_command('update_biz_playback_status', self.multiple_courses_contract.id)

        self.mock_log.info.assert_any_call(
            u'Removed PlaybackStore records. contract_id={} course_id={}'.format(
                self.multiple_courses_contract.id, self.single_spoc_video_course.id))
        self.mock_log.info.assert_any_call(
            u'Removed PlaybackStore records. contract_id={} course_id={}'.format(
                self.multiple_courses_contract.id, self.multiple_spoc_video_course.id))

        self.mock_log.info.assert_any_call(
            u'Stored PlaybackStore record count(100). contract_id={} course_id={}'.format(
                self.multiple_courses_contract.id, self.single_spoc_video_course.id))
        self.mock_log.info.assert_any_call(
            u'Stored PlaybackStore record count(100). contract_id={} course_id={}'.format(
                self.multiple_courses_contract.id, self.multiple_spoc_video_course.id))

        PlaybackBatchStatus.objects.get(contract=self.multiple_courses_contract, course_id=self.single_spoc_video_course.id, status=BATCH_STATUS_FINISHED, student_count=100)
        PlaybackBatchStatus.objects.get(contract=self.multiple_courses_contract, course_id=self.multiple_spoc_video_course.id, status=BATCH_STATUS_FINISHED, student_count=100)

    @override_settings(
        MAX_RETRY_REMOVE_DOCUMENTS=3,
        SLEEP_RETRY_REMOVE_DOCUMENTS=3,
        MAX_RETRY_SET_DOCUMENTS=3,
        SLEEP_RETRY_SET_DOCUMENTS=3,
    )
    @patch('biz.djangoapps.ga_achievement.management.commands.update_biz_playback_status.time.sleep')
    def test_error_log_can_not_remove_documents(self, mock_time_sleep):
        for var in range(0, 50):
            user = UserFactory.create()
            self._input_contract(self.multiple_courses_contract, user)
        for var in range(0, 50):
            user = UserFactory.create()
            self._register_contract(self.multiple_courses_contract, user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        with patch('biz.djangoapps.ga_achievement.management.commands.update_biz_playback_status.PlaybackStore.get_count', return_value=100):
            call_command('update_biz_playback_status', self.multiple_courses_contract.id)

        for i in range(3):
            self.mock_log.warning.assert_any_call(
                u'Can not remove(try:{},sleep:3) PlaybackStore record count(100). contract_id={} course_id={}'.format(
                    i + 1, self.multiple_courses_contract.id, self.single_spoc_video_course.id))
        for i in range(3):
            self.mock_log.warning.assert_any_call(
                u'Can not remove(try:{},sleep:3) PlaybackStore record count(100). contract_id={} course_id={}'.format(
                    i + 1, self.multiple_courses_contract.id, self.multiple_spoc_video_course.id))

        self.assertEqual(6, mock_time_sleep.call_count)
        mock_time_sleep.assert_any_call(3)

        self.mock_log.error.assert_any_call(
            u'Unexpected error occurred: Can not remove PlaybackStore record count(100). contract_id={} course_id={}'.format(
                self.multiple_courses_contract.id, self.single_spoc_video_course.id))
        self.mock_log.error.assert_any_call(
            u'Unexpected error occurred: Can not remove PlaybackStore record count(100). contract_id={} course_id={}'.format(
                self.multiple_courses_contract.id, self.multiple_spoc_video_course.id))

        PlaybackBatchStatus.objects.get(contract=self.multiple_courses_contract, course_id=self.single_spoc_video_course.id, status=BATCH_STATUS_ERROR, student_count=None)
        PlaybackBatchStatus.objects.get(contract=self.multiple_courses_contract, course_id=self.multiple_spoc_video_course.id, status=BATCH_STATUS_ERROR, student_count=None)

    @override_settings(
        MAX_RETRY_REMOVE_DOCUMENTS=3,
        SLEEP_RETRY_REMOVE_DOCUMENTS=0,
        MAX_RETRY_SET_DOCUMENTS=3,
        SLEEP_RETRY_SET_DOCUMENTS=0,
    )
    @patch('biz.djangoapps.ga_achievement.management.commands.update_biz_playback_status.time.sleep')
    def test_error_log_can_not_set_documents(self, mock_time_sleep):
        for var in range(0, 50):
            user = UserFactory.create()
            self._input_contract(self.multiple_courses_contract, user)
        for var in range(0, 50):
            user = UserFactory.create()
            self._register_contract(self.multiple_courses_contract, user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        with patch('biz.djangoapps.ga_achievement.management.commands.update_biz_playback_status.PlaybackStore.get_count', return_value=0):
            call_command('update_biz_playback_status', self.multiple_courses_contract.id)

        self.mock_log.info.assert_any_call(
            u'Removed PlaybackStore records. contract_id={} course_id={}'.format(
                self.multiple_courses_contract.id, self.single_spoc_video_course.id))
        self.mock_log.info.assert_any_call(
            u'Removed PlaybackStore records. contract_id={} course_id={}'.format(
                self.multiple_courses_contract.id, self.multiple_spoc_video_course.id))

        for i in range(3):
            self.mock_log.warning.assert_any_call(
                u'Can not store(try:{},sleep:0) PlaybackStore record count(-1) does not match Contract Register record count(100) or records count(100). contract_id={} course_id={}'.format(
                    i + 1, self.multiple_courses_contract.id, self.single_spoc_video_course.id))
        for i in range(3):
            self.mock_log.warning.assert_any_call(
                u'Can not store(try:{},sleep:0) PlaybackStore record count(-1) does not match Contract Register record count(100) or records count(100). contract_id={} course_id={}'.format(
                    i + 1, self.multiple_courses_contract.id, self.multiple_spoc_video_course.id))

        mock_time_sleep.assert_not_called()

        self.mock_log.error.assert_any_call(
            u'Unexpected error occurred: PlaybackStore record count(-1) does not match Contract Register record count(100) or records count(100). contract_id={} course_id={}'.format(
                self.multiple_courses_contract.id, self.single_spoc_video_course.id))
        self.mock_log.error.assert_any_call(
            u'Unexpected error occurred: PlaybackStore record count(-1) does not match Contract Register record count(100) or records count(100). contract_id={} course_id={}'.format(
                self.multiple_courses_contract.id, self.multiple_spoc_video_course.id))

        PlaybackBatchStatus.objects.get(contract=self.multiple_courses_contract, course_id=self.single_spoc_video_course.id, status=BATCH_STATUS_ERROR, student_count=None)
        PlaybackBatchStatus.objects.get(contract=self.multiple_courses_contract, course_id=self.multiple_spoc_video_course.id, status=BATCH_STATUS_ERROR, student_count=None)


class TestGroupedTargetVerticals(ModuleStoreTestCase):
    """
    Tests for TargetVertical and GroupedTargetVerticals
    """
    def setUp(self):
        super(TestGroupedTargetVerticals, self).setUp()
        self.course = CourseFactory.create(org='TestX', course='TS101', run='T1')
        self.chapter_x = ItemFactory.create(parent=self.course, category='chapter', display_name='chapter_x')
        self.chapter_y = ItemFactory.create(parent=self.course, category='chapter', display_name='chapter_y')
        self.section_x1 = ItemFactory.create(parent=self.chapter_x, category='sequential', display_name='sequential_x1')
        self.section_y1 = ItemFactory.create(parent=self.chapter_y, category='sequential', display_name='sequential_y1')
        self.section_y2 = ItemFactory.create(parent=self.chapter_y, category='sequential', display_name='sequential_y2')
        self.vertical_x1a = ItemFactory.create(parent=self.section_x1, category='vertical', display_name='vertical_x1a')
        self.vertical_x1b = ItemFactory.create(parent=self.section_x1, category='vertical', display_name='vertical_x1b')
        self.vertical_y1a = ItemFactory.create(parent=self.section_y1, category='vertical', display_name='vertical_y1a')
        self.vertical_y2a = ItemFactory.create(parent=self.section_y2, category='vertical', display_name='vertical_y2a')
        self.vertical_y2b = ItemFactory.create(parent=self.section_y2, category='vertical', display_name='vertical_y2b')
        self.target_vertical_x1a = TargetVertical(self.vertical_x1a)
        self.target_vertical_x1b = TargetVertical(self.vertical_x1b)
        self.target_vertical_y1a = TargetVertical(self.vertical_y1a)
        self.target_vertical_y2a = TargetVertical(self.vertical_y2a)
        self.target_vertical_y2b = TargetVertical(self.vertical_y2b)

    def test_target_vertical_init_invalid(self):
        with self.assertRaises(TypeError):
            TargetVertical('test')

    def test_grouped_target_verticals_append_invalid(self):
        grouped_target_verticals = GroupedTargetVerticals()
        with self.assertRaises(TypeError):
            grouped_target_verticals.append('test')

    def test_grouped_target_verticals_with_no_element(self):
        grouped_target_verticals = GroupedTargetVerticals()
        self.assertEquals(grouped_target_verticals.keys(), [])
        self.assertEquals(grouped_target_verticals.values(), [])

    def test_grouped_target_verticals(self):
        grouped_target_verticals = GroupedTargetVerticals()
        grouped_target_verticals.append(self.target_vertical_x1a)
        grouped_target_verticals.append(self.target_vertical_x1b)
        grouped_target_verticals.append(self.target_vertical_y1a)
        grouped_target_verticals.append(self.target_vertical_y2a)
        grouped_target_verticals.append(self.target_vertical_y2b)

        self.assertEquals(grouped_target_verticals.keys(), [self.chapter_x.location, self.chapter_y.location])
        self.assertEquals(grouped_target_verticals.values(),
                          [[self.target_vertical_x1a, self.target_vertical_x1b],
                           [self.target_vertical_y1a, self.target_vertical_y2a, self.target_vertical_y2b]])
        self.assertEquals(grouped_target_verticals.get(self.chapter_x.location),
                          [self.target_vertical_x1a, self.target_vertical_x1b])
        self.assertEquals(grouped_target_verticals.get(self.chapter_y.location),
                          [self.target_vertical_y1a, self.target_vertical_y2a, self.target_vertical_y2b])


class TestGetGroupedTargetVerticals(ModuleStoreTestCase):
    """
    Tests for get_grouped_target_verticals
    """
    def setUp(self):
        super(TestGetGroupedTargetVerticals, self).setUp()
        self.course = CourseFactory.create(org='TestX', course='TS101', run='T1')
        self.chapter_x = ItemFactory.create(parent=self.course, category='chapter', display_name='chapter_x')
        self.chapter_y = ItemFactory.create(parent=self.course, category='chapter', display_name='chapter_y')
        self.section_x1 = ItemFactory.create(parent=self.chapter_x, category='sequential', display_name='sequential_x1')
        self.section_y1 = ItemFactory.create(parent=self.chapter_y, category='sequential', display_name='sequential_y1')
        self.section_y2 = ItemFactory.create(parent=self.chapter_y, category='sequential', display_name='sequential_y2')
        self.vertical_x1a = ItemFactory.create(parent=self.section_x1, category='vertical', display_name='vertical_x1a')
        self.vertical_y1a = ItemFactory.create(parent=self.section_y1, category='vertical', display_name='vertical_y1a')
        self.vertical_y2a = ItemFactory.create(parent=self.section_y2, category='vertical', display_name='vertical_y2a')
        self.component_x1a_1 = ItemFactory.create(parent=self.vertical_x1a, category='jwplayerxblock', display_name='component_x1a_1')
        self.component_y1a_1 = ItemFactory.create(parent=self.vertical_y1a, category='jwplayerxblock', display_name='component_y1a_1')
        self.component_y2a_1 = ItemFactory.create(parent=self.vertical_y2a, category='jwplayerxblock', display_name='component_y2a_1')

    def test_if_chapter_is_hide_from_students(self):
        self.chapter_x.visible_to_staff_only = True
        self.store.update_item(self.chapter_x, self.user.id)

        grouped_target_verticals = get_grouped_target_verticals(self.course)
        self.assertEquals(
            [[tv.vertical_id for tv in tvs] for tvs in grouped_target_verticals.values()],
            [[self.vertical_x1a.location.block_id], [self.vertical_y1a.location.block_id, self.vertical_y2a.location.block_id]]
        )

    def test_if_section_is_hide_from_students(self):
        self.section_y1.visible_to_staff_only = True
        self.store.update_item(self.section_y1, self.user.id)

        grouped_target_verticals = get_grouped_target_verticals(self.course)
        self.assertEquals(
            [[tv.vertical_id for tv in tvs] for tvs in grouped_target_verticals.values()],
            [[self.vertical_x1a.location.block_id], [self.vertical_y1a.location.block_id, self.vertical_y2a.location.block_id]]
        )

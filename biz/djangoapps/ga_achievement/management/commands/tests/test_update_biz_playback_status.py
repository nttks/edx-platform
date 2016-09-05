"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from collections import namedtuple
import logging
from mock import patch
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore
from biz.djangoapps.ga_achievement.management.commands import update_biz_playback_status
from biz.djangoapps.ga_achievement.models import PlaybackBatchStatus, BATCH_STATUS_STARTED, BATCH_STATUS_FINISHED, BATCH_STATUS_ERROR
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from lms.djangoapps.courseware.tests.helpers import LoginEnrollmentTestCase
from opaque_keys.edx.locator import CourseLocator
from student.models import CourseEnrollment
from student.tests.factories import UserFactory, UserProfileFactory
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

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


@override_settings(BIZ_SET_PLAYBACK_COMMAND_OUTPUT=command_output_file.name)
class UpdateBizPlaybackStatusTest(BizStoreTestBase, ModuleStoreTestCase, LoginEnrollmentTestCase):

    def setUp(self):
        super(UpdateBizPlaybackStatusTest, self).setUp()
        # Course
        self.no_spoc_video_course = self._create_course(self.gacco_organization.org_code, 'no_spoc_video_course', 'run', no_spoc_video_block)
        self.single_spoc_video_course = self._create_course(self.gacco_organization.org_code, 'single_spoc_video_course', 'run', single_spoc_video_block)
        self.multiple_spoc_video_course = self._create_course(self.gacco_organization.org_code, 'multiple_spoc_video_course', 'run', multiple_spoc_video_block)
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
        # Setup mock
        patcher_aggregate = patch.object(update_biz_playback_status.PlaybackLogStore, 'aggregate')
        self.mock_aggregate = patcher_aggregate.start()
        self.mock_aggregate.return_value = {}
        self.addCleanup(patcher_aggregate.stop)

        patcher_log = patch('biz.djangoapps.ga_achievement.management.commands.update_biz_playback_status.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

    def _create_course(self, org, course, run, block_info_tree):
        location = self.create_sample_course(org, course, run, block_info_tree=block_info_tree)
        return self.store.get_course(CourseLocator(location.org, location.course, location.run))

    # Note: this is removed since Dogwood release,
    #       so we restore it from common/lib/xmodule/xmodule/modulestore/tests/django_utils.py (Cypress ver.)
    def create_sample_course(self, org, course, run, block_info_tree=None, course_fields=None):
        """
        create a course in the default modulestore from the collection of BlockInfo
        records defining the course tree
        Returns:
            course_loc: the CourseKey for the created course
        """
        with self.store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, None):
            course = self.store.create_course(org, course, run, self.user.id, fields=course_fields)
            self.course_loc = course.location  # pylint: disable=attribute-defined-outside-init

            def create_sub_tree(parent_loc, block_info):
                """Recursively creates a sub_tree on this parent_loc with this block."""
                block = self.store.create_child(
                    self.user.id,
                    # TODO remove version_agnostic() when we impl the single transaction
                    parent_loc.version_agnostic(),
                    block_info.category, block_id=block_info.block_id,
                    fields=block_info.fields,
                )
                for tree in block_info.sub_tree:
                    create_sub_tree(block.location, tree)
                setattr(self, block_info.block_id, block.location.version_agnostic())

            for tree in block_info_tree:
                create_sub_tree(self.course_loc, tree)

            # remove version_agnostic when bulk write works
            self.store.publish(self.course_loc.version_agnostic(), self.user.id)
        return self.course_loc.course_key.version_agnostic()

    def _profile(self, user):
        UserProfileFactory.create(user=user, name='profile_name')

    def _unenroll(self, user, course):
        CourseEnrollment.unenroll(user, course.id)

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

    def assert_error(self, contract, course):
        PlaybackBatchStatus.objects.get(contract=contract, course_id=course.id, status=BATCH_STATUS_STARTED)
        PlaybackBatchStatus.objects.get(contract=contract, course_id=course.id, status=BATCH_STATUS_ERROR, student_count=None)

        playback_list = PlaybackStore(contract.id, unicode(course.id)).get_documents()
        self.assertEquals(len(playback_list), 0)
        return playback_list

    def test_contract_with_no_user(self):
        call_command('update_biz_playback_status', self.no_spoc_video_contract.id)

        self.assert_finished(0, self.no_spoc_video_contract, self.no_spoc_video_course)

    def test_contract_with_not_enrolled_user(self):
        self._input_contract(self.no_spoc_video_contract, self.user)

        call_command('update_biz_playback_status', self.no_spoc_video_contract.id)

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

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_FULL_NAME, None))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, None))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_ADDITIONAL_INFO + PlaybackStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, None))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__NOT_ENROLLED))

        assert_playback(self.no_spoc_video_contract, self.no_spoc_video_course)

    def test_contract_with_enrolled_user(self):
        self._profile(self.user)
        self._register_contract(self.no_spoc_video_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        call_command('update_biz_playback_status', self.no_spoc_video_contract.id)

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

        assert_playback(self.no_spoc_video_contract, self.no_spoc_video_course)

    def test_contract_with_unenrolled_user(self):
        self._profile(self.user)
        self._register_contract(self.no_spoc_video_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._unenroll(self.user, self.no_spoc_video_course)

        call_command('update_biz_playback_status', self.no_spoc_video_contract.id)

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
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__UNENROLLED))

        assert_playback(self.no_spoc_video_contract, self.no_spoc_video_course)

    def test_contract_with_disabled_user(self):
        self._profile(self.user)
        self._register_contract(self.no_spoc_video_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._account_disable(self.user)

        call_command('update_biz_playback_status', self.no_spoc_video_contract.id)

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
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__DISABLED))

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

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_DOCUMENT_TYPE, PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_FULL_NAME, None))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (PlaybackStore.FIELD_STUDENT_STATUS, PlaybackStore.FIELD_STUDENT_STATUS__NOT_ENROLLED))

        assert_playback(self.no_additional_info_contract, self.no_spoc_video_course)

    def test_contract_with_single_spoc_video(self):
        self._profile(self.user)
        self._register_contract(self.single_spoc_video_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        _aggregate_duration_by_vertical = {
            u'vertical_x1a': 100.0,
        }
        self.mock_aggregate.return_value = _aggregate_duration_by_vertical
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

        assert_playback(self.single_spoc_video_contract, self.single_spoc_video_course)

    def test_contract_with_multiple_spoc_video(self):
        self._profile(self.user)
        self._register_contract(self.multiple_spoc_video_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        _aggregate_duration_by_vertical = {
            u'vertical_x1a': 100.0,
            u'vertical_x1c': 200.0,
            u'vertical_y1a': 400.0,
        }
        self.mock_aggregate.return_value = _aggregate_duration_by_vertical
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

        assert_playback(self.multiple_spoc_video_contract, self.multiple_spoc_video_course)

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

        class DummyCourseDescriptor(object):
            def __init__(self, org, course, run):
                self.id = CourseLocator(org, course, run)

        not_exist_course = DummyCourseDescriptor('not', 'exist', 'course')
        not_exist_course_contract = self._create_contract(
            detail_courses=[not_exist_course],
        )

        call_command('update_biz_playback_status', not_exist_course_contract.id)

        self.assert_error(not_exist_course_contract, not_exist_course)
        self.mock_log.warning.assert_called_once()

    def test_error(self):
        self.mock_aggregate.side_effect = Exception()
        self._input_contract(self.single_spoc_video_contract, self.user)

        call_command('update_biz_playback_status', self.single_spoc_video_contract.id)

        self.assert_error(self.single_spoc_video_contract, self.single_spoc_video_course)
        self.mock_log.error.assert_called_once()

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

from biz.djangoapps.ga_achievement.achievement_store import ScoreStore
from biz.djangoapps.ga_achievement.management.commands import update_biz_score_status
from biz.djangoapps.ga_achievement.management.commands.update_biz_score_status import (
    TargetSection, GroupedTargetSections, get_grouped_target_sections,
)
from biz.djangoapps.ga_achievement.models import ScoreBatchStatus, BATCH_STATUS_STARTED, BATCH_STATUS_FINISHED, BATCH_STATUS_ERROR
from biz.djangoapps.ga_achievement.tests.factories import ScoreBatchStatusFactory
from biz.djangoapps.ga_contract.tests.factories import ContractAuthFactory
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.util.decorators import ExitWithWarning
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from certificates.models import CertificateStatuses, GeneratedCertificate
from certificates.tests.factories import GeneratedCertificateFactory
from courseware import grades
from courseware.grades import _Score
from courseware.tests.helpers import LoginEnrollmentTestCase
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
    Tests for parsing arguments of the `update_biz_score_status` command
    """
    def setUp(self):
        super(TestArgParsing, self).setUp()
        self.command = update_biz_score_status.Command()

    def test_args_debug(self):
        self.command.execute(debug=True)
        self.assertEquals(update_biz_score_status.log.level, logging.DEBUG)

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
@override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=command_output_file.name)
class UpdateBizScoreStatusTest(BizStoreTestBase, ModuleStoreTestCase, LoginEnrollmentTestCase):

    def _certificate(self, user, course):
        GeneratedCertificateFactory.create(
            user=user,
            course_id=course.id,
            status=CertificateStatuses.downloadable,
            mode='verified',
            download_url='http://test_certificate_url',
        )

    def _profile(self, user):
        UserProfileFactory.create(user=user, name='profile_name')

    def _unenroll(self, user, course):
        CourseEnrollment.unenroll(user, course.id)

    def _biz_user(self, user, login_code, contract):
        if login_code:
            BizUserFactory.create(user=user, login_code=login_code)
            ContractAuthFactory.create(contract=contract, url_code='test-url-code', send_mail=False)

    def setUp(self):
        super(UpdateBizScoreStatusTest, self).setUp()
        self.course1_blocks = [
            BlockInfo(
                'chapter_x', 'chapter', {'display_name': 'chapter_x'}, [
                    BlockInfo(
                        'sequential_x1', 'sequential', {'display_name': 'sequential_x1', 'graded': True, 'format': 'format_x1'}, [
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
                        'sequential_y1', 'sequential', {'display_name': 'sequential_y1', 'graded': True, 'format': 'format_y1'}, [
                            BlockInfo(
                                'vertical_y1a', 'vertical', {'display_name': 'vertical_y1a'}, [
                                    BlockInfo('component_y1a_1', 'problem', {'display_name': 'component_y1a_1'}, []),
                                ]
                            ),
                        ]
                    ),
                    BlockInfo(
                        'sequential_y2', 'sequential', {'display_name': 'sequential_y2', 'graded': True, 'format': 'format_y2'}, [
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
        self.course1 = self._create_course(self.gacco_organization.org_code, 'course1', 'run', self.course1_blocks)
        self.course2_blocks = [
            BlockInfo(
                'chapter_z', 'chapter', {'display_name': 'chapter_z'}, [
                    BlockInfo(
                        'sequential_z1', 'sequential', {'display_name': 'sequential_z1', 'graded': True, 'format': 'format_z1'}, [
                            BlockInfo(
                                'vertical_z1a', 'vertical', {'display_name': 'vertical_z1a'}, [
                                    BlockInfo('component_z1a_1', 'problem', {'display_name': 'component_z1a_1'}, []),
                                ]
                            ),
                        ]
                    ),
                ]
            ),
        ]
        self.course2 = self._create_course(self.gacco_organization.org_code, 'course2', 'run', self.course2_blocks)
        self.contract = self._create_contract(
            detail_courses=[self.course1, self.course2],
            additional_display_names=[ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_DISPLAY_NAME2],
        )

        # Contract with self-paced course
        self.individual_end_days = 10
        self.self_paced_course = CourseFactory.create(
            org=self.gacco_organization.org_code, number='self_paced_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            individual_end_days=self.individual_end_days,
        )
        self.self_paced_contract = self._create_contract(
            detail_courses=[self.self_paced_course],
            additional_display_names=[ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_DISPLAY_NAME2],
        )

        # Setup mock
        patcher_grade = patch.object(grades, 'grade')
        self.mock_grade = patcher_grade.start()
        self.mock_grade.return_value = {
            'totaled_scores': {},
            'percent': 0,
        }
        self.addCleanup(patcher_grade.stop)

        patcher_log = patch('biz.djangoapps.ga_achievement.management.commands.update_biz_score_status.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

        patcher_exists_today = patch.object(update_biz_score_status.ScoreBatchStatus, 'exists_today')
        self.mock_exists_today = patcher_exists_today.start()
        self.mock_exists_today.return_value = False
        self.addCleanup(patcher_exists_today.stop)

    def assert_finished(self, count, contract, course):
        ScoreBatchStatus.objects.get(contract=contract, course_id=course.id, status=BATCH_STATUS_STARTED)
        ScoreBatchStatus.objects.get(contract=contract, course_id=course.id, status=BATCH_STATUS_FINISHED, student_count=count)

        column_list = ScoreStore(contract.id, unicode(course.id)).get_documents(
            conditions={ScoreStore.FIELD_DOCUMENT_TYPE: ScoreStore.FIELD_DOCUMENT_TYPE__COLUMN}
        )
        record_list = ScoreStore(contract.id, unicode(course.id)).get_documents(
            conditions={ScoreStore.FIELD_DOCUMENT_TYPE: ScoreStore.FIELD_DOCUMENT_TYPE__RECORD}
        )
        if count == 0:
            self.assertEquals(len(column_list), 0)
            self.assertEquals(len(record_list), 0)
        else:
            self.assertEquals(len(column_list), 1)
            self.assertEquals(len(record_list), count)
        return column_list, record_list

    def assert_error(self, contract, course_id):
        ScoreBatchStatus.objects.get(contract=contract, course_id=course_id, status=BATCH_STATUS_STARTED)
        ScoreBatchStatus.objects.get(contract=contract, course_id=course_id, status=BATCH_STATUS_ERROR, student_count=None)

        playback_list = ScoreStore(contract.id, unicode(course_id)).get_documents()
        self.assertEquals(len(playback_list), 0)
        return playback_list

    def assert_datetime(self, first, second):
        _format = '%Y%m%d%H%M%S%Z'
        self.assertEquals(first.strftime(_format), second.strftime(_format))

    def assert_column_list(self, column_list, contract, course, login_code=None, self_paced=False):
        self.assertEquals(len(column_list), 1)
        column_dict = column_list[0]
        column_items = column_dict.iteritems()
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_CONTRACT_ID, contract.id))
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_COURSE_ID, unicode(course.id)))
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_DOCUMENT_TYPE, ScoreStore.FIELD_DOCUMENT_TYPE__COLUMN))
        if login_code:
            self.assertEquals(column_items.next(), (ScoreStore.FIELD_LOGIN_CODE, ScoreStore.COLUMN_TYPE__TEXT))
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_FULL_NAME, ScoreStore.COLUMN_TYPE__TEXT))
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_USERNAME, ScoreStore.COLUMN_TYPE__TEXT))
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_EMAIL, ScoreStore.COLUMN_TYPE__TEXT))
        self.assertEquals(column_items.next(), (
        ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1,
        ScoreStore.COLUMN_TYPE__TEXT))
        self.assertEquals(column_items.next(), (
        ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2,
        ScoreStore.COLUMN_TYPE__TEXT))
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_STUDENT_STATUS, ScoreStore.COLUMN_TYPE__TEXT))
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_CERTIFICATE_STATUS, ScoreStore.COLUMN_TYPE__TEXT))
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_ENROLL_DATE, ScoreStore.COLUMN_TYPE__DATE))
        if self_paced:
            self.assertEquals(column_items.next(), (ScoreStore.FIELD_EXPIRE_DATE, ScoreStore.COLUMN_TYPE__DATE))
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, ScoreStore.COLUMN_TYPE__DATE))
        self.assertEquals(column_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, ScoreStore.COLUMN_TYPE__PERCENT))
        for chapter in course.get_children():
            for section in chapter.get_children():
                self.assertEquals(column_items.next(), (
                chapter.display_name + ScoreStore.FIELD_DELIMITER + section.display_name,
                ScoreStore.COLUMN_TYPE__PERCENT))
        self.assertRaises(StopIteration, column_items.next)

    def test_contract_with_no_user(self):
        call_command('update_biz_score_status')

        self.assert_finished(0, self.contract, self.course1)
        self.assert_finished(0, self.contract, self.course2)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_not_enrolled_user(self, login_code):
        self._input_contract(self.contract, self.user)
        self._biz_user(self.user, login_code, self.contract)

        call_command('update_biz_score_status')

        def assert_score(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)
            self.assert_column_list(column_list, contract, course, login_code)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_DOCUMENT_TYPE, ScoreStore.FIELD_DOCUMENT_TYPE__RECORD))
            if login_code:
                self.assertEquals(record_items.next(), (ScoreStore.FIELD_LOGIN_CODE, login_code))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_FULL_NAME, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_STUDENT_STATUS, ScoreStore.FIELD_STUDENT_STATUS__NOT_ENROLLED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_STATUS, ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ENROLL_DATE, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, 0.0))
            for chapter in course.get_children():
                for section in chapter.get_children():
                    self.assertEquals(record_items.next(), (
                        chapter.display_name + ScoreStore.FIELD_DELIMITER + section.display_name,
                        ScoreStore.VALUE__NOT_ATTEMPTED
                    ))
            self.assertRaises(StopIteration, record_items.next)

        assert_score(self.contract, self.course1)
        assert_score(self.contract, self.course2)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_enrolled_user(self, login_code):
        self._profile(self.user)
        self._register_contract(self.contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._biz_user(self.user, login_code, self.contract)

        call_command('update_biz_score_status')

        def assert_score(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)
            self.assert_column_list(column_list, contract, course, login_code)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_DOCUMENT_TYPE, ScoreStore.FIELD_DOCUMENT_TYPE__RECORD))
            if login_code:
                self.assertEquals(record_items.next(), (ScoreStore.FIELD_LOGIN_CODE, login_code))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_STUDENT_STATUS, ScoreStore.FIELD_STUDENT_STATUS__ENROLLED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_STATUS, ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED))
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_ENROLL_DATE)
            self.assert_datetime(v, CourseEnrollment.get_enrollment(self.user, course.id).created)
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, 0.0))
            for chapter in course.get_children():
                for section in chapter.get_children():
                    self.assertEquals(record_items.next(), (
                        chapter.display_name + ScoreStore.FIELD_DELIMITER + section.display_name,
                        ScoreStore.VALUE__NOT_ATTEMPTED
                    ))
            self.assertRaises(StopIteration, record_items.next)

        assert_score(self.contract, self.course1)
        assert_score(self.contract, self.course2)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_grade(self, login_code):
        self._profile(self.user)
        self._register_contract(self.contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)
        self._biz_user(self.user, login_code, self.contract)

        grade_return_values = [
            # For course1
            {
                'totaled_scores': {
                    u'chapter_x': [
                        _Score(0.0, 10.0, True, u'sequential_x1', u'i4x://gacco/course1/sequential/sequential_x1', True),
                    ],
                    u'chapter_y': [
                        _Score(10.0, 20.0, True, u'sequential_y1', u'i4x://gacco/course1/sequential/sequential_y1', True),
                        _Score(20.0, 30.0, True, u'sequential_y2', u'i4x://gacco/course1/sequential/sequential_y2', True),
                    ],
                },
                'percent': 88.8888888888,
            },
            # For course2
            {
                'totaled_scores': {
                    u'chapter_z': [
                        _Score(0.0, 0.0, True, u'sequential_z1', u'i4x://gacco/course2/sequential/sequential_z1', False),
                    ],
                },
                'percent': 0.0,
            },
        ]
        self.mock_grade.side_effect = grade_return_values

        call_command('update_biz_score_status')

        def assert_score(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)
            self.assert_column_list(column_list, contract, course, login_code)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_DOCUMENT_TYPE, ScoreStore.FIELD_DOCUMENT_TYPE__RECORD))
            if login_code:
                self.assertEquals(record_items.next(), (ScoreStore.FIELD_LOGIN_CODE, login_code))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_STUDENT_STATUS, ScoreStore.FIELD_STUDENT_STATUS__ENROLLED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_STATUS, ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE))
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_ENROLL_DATE)
            self.assert_datetime(v, CourseEnrollment.get_enrollment(self.user, course.id).created)
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE)
            self.assert_datetime(v, GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            if course.number == 'course1':
                self.assertEquals(record_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, grade_return_values[0]['percent']))
                totaled_scores = grade_return_values[0]['totaled_scores']
                for i, chapter in enumerate(course.get_children()):
                    for j, section in enumerate(chapter.get_children()):
                        self.assertEquals(record_items.next(), (
                            chapter.display_name + ScoreStore.FIELD_DELIMITER + section.display_name,
                            totaled_scores[chapter.display_name][j].earned / totaled_scores[chapter.display_name][j].possible
                        ))
            elif course.number == 'course2':
                self.assertEquals(record_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, grade_return_values[1]['percent']))
                for i, chapter in enumerate(course.get_children()):
                    for j, section in enumerate(chapter.get_children()):
                        self.assertEquals(record_items.next(), (
                            chapter.display_name + ScoreStore.FIELD_DELIMITER + section.display_name,
                            ScoreStore.VALUE__NOT_ATTEMPTED
                        ))
            self.assertRaises(StopIteration, record_items.next)

        assert_score(self.contract, self.course1)
        assert_score(self.contract, self.course2)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_grade_error(self, login_code):
        self._profile(self.user)
        self._register_contract(self.contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)
        self._biz_user(self.user, login_code, self.contract)

        self.mock_grade.side_effect = Exception()

        call_command('update_biz_score_status')

        def assert_score(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)
            self.assert_column_list(column_list, contract, course, login_code)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_DOCUMENT_TYPE, ScoreStore.FIELD_DOCUMENT_TYPE__RECORD))
            if login_code:
                self.assertEquals(record_items.next(), (ScoreStore.FIELD_LOGIN_CODE, login_code))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_STUDENT_STATUS, ScoreStore.FIELD_STUDENT_STATUS__ENROLLED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_STATUS, ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE))
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_ENROLL_DATE)
            self.assert_datetime(v, CourseEnrollment.get_enrollment(self.user, course.id).created)
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE)
            self.assert_datetime(v, GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            # If grades.grade() raises exception, 'Total Score' is set to 0.0 and scores for each section are set to '-'
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, 0.0))
            for chapter in course.get_children():
                for section in chapter.get_children():
                    self.assertEquals(record_items.next(), (
                        chapter.display_name + ScoreStore.FIELD_DELIMITER + section.display_name,
                        ScoreStore.VALUE__NOT_ATTEMPTED
                    ))
            self.assertRaises(StopIteration, record_items.next)

        assert_score(self.contract, self.course1)
        assert_score(self.contract, self.course2)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_unenrolled_user(self, login_code):
        self._profile(self.user)
        self._register_contract(self.contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)
        self._unenroll(self.user, self.course1)
        self._unenroll(self.user, self.course2)
        self._biz_user(self.user, login_code, self.contract)

        call_command('update_biz_score_status')

        def assert_score(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)
            self.assert_column_list(column_list, contract, course, login_code)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_DOCUMENT_TYPE, ScoreStore.FIELD_DOCUMENT_TYPE__RECORD))
            if login_code:
                self.assertEquals(record_items.next(), (ScoreStore.FIELD_LOGIN_CODE, login_code))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_STUDENT_STATUS, ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_STATUS, ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE))
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_ENROLL_DATE)
            self.assert_datetime(v, CourseEnrollment.get_enrollment(self.user, course.id).created)
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE)
            self.assert_datetime(v, GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, 0.0))
            for chapter in course.get_children():
                for section in chapter.get_children():
                    self.assertEquals(record_items.next(), (
                        chapter.display_name + ScoreStore.FIELD_DELIMITER + section.display_name,
                        ScoreStore.VALUE__NOT_ATTEMPTED
                    ))
            self.assertRaises(StopIteration, record_items.next)

        assert_score(self.contract, self.course1)
        assert_score(self.contract, self.course2)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_disabled_user(self, login_code):
        self._profile(self.user)
        self._register_contract(self.contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)
        self._account_disable(self.user)
        self._biz_user(self.user, login_code, self.contract)

        call_command('update_biz_score_status')

        def assert_score(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)
            self.assert_column_list(column_list, contract, course, login_code)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_DOCUMENT_TYPE, ScoreStore.FIELD_DOCUMENT_TYPE__RECORD))
            if login_code:
                self.assertEquals(record_items.next(), (ScoreStore.FIELD_LOGIN_CODE, login_code))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_STUDENT_STATUS, ScoreStore.FIELD_STUDENT_STATUS__DISABLED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_STATUS, ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE))
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_ENROLL_DATE)
            self.assert_datetime(v, CourseEnrollment.get_enrollment(self.user, course.id).created)
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE)
            self.assert_datetime(v, GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, 0.0))
            for chapter in course.get_children():
                for section in chapter.get_children():
                    self.assertEquals(record_items.next(), (
                        chapter.display_name + ScoreStore.FIELD_DELIMITER + section.display_name,
                        ScoreStore.VALUE__NOT_ATTEMPTED
                    ))
            self.assertRaises(StopIteration, record_items.next)

        assert_score(self.contract, self.course1)
        assert_score(self.contract, self.course2)

    def test_contract_with_self_paced_course_if_user_not_enrolled(self):
        """
        When:
            - The contract includes a self-paced course.
            - The user has not enrolled in the course.
        Then:
            - 'Student Status' is set to 'Not Enrolled'.
            - 'Expire Date' is stored and set to None.
        """
        self._profile(self.user)
        self._register_contract(self.self_paced_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        # Delete enrollment to simulate a scenario that the user has not enrolled in the course
        enrollment = CourseEnrollment.get_enrollment(self.user, self.self_paced_course.id)
        enrollment.delete()

        call_command('update_biz_score_status')

        def assert_score(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)
            self.assert_column_list(column_list, contract, course, self_paced=True)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_DOCUMENT_TYPE, ScoreStore.FIELD_DOCUMENT_TYPE__RECORD))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_STUDENT_STATUS, ScoreStore.FIELD_STUDENT_STATUS__NOT_ENROLLED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_STATUS, ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ENROLL_DATE, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_EXPIRE_DATE, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, 0.0))
            self.assertRaises(StopIteration, record_items.next)

        assert_score(self.self_paced_contract, self.self_paced_course)

    def test_contract_with_self_paced_course(self):
        """
        When:
            - The contract includes a self-paced course.
            - The user had already enrolled in the course.
            - The self-paced course is available for the user (today is earlier than the end date).
        Then:
            - 'Student Status' is set to 'Enrolled'.
            - 'Expire Date' is stored and set to the end date for the user.
        """
        self._profile(self.user)
        self._register_contract(self.self_paced_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        call_command('update_biz_score_status')

        def assert_score(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)
            self.assert_column_list(column_list, contract, course, self_paced=True)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_DOCUMENT_TYPE, ScoreStore.FIELD_DOCUMENT_TYPE__RECORD))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_STUDENT_STATUS, ScoreStore.FIELD_STUDENT_STATUS__ENROLLED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_STATUS, ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED))
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_ENROLL_DATE)
            self.assert_datetime(v, CourseEnrollment.get_enrollment(self.user, course.id).created)
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_EXPIRE_DATE)
            enrollment = CourseEnrollment.get_enrollment(self.user, course.id)
            self.assert_datetime(v, enrollment.created + timedelta(self.individual_end_days))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, 0.0))
            self.assertRaises(StopIteration, record_items.next)

        assert_score(self.self_paced_contract, self.self_paced_course)

    def test_contract_with_expired_self_paced_course(self):
        """
        When:
            - The contract includes a self-paced course.
            - The self-paced course has already expired for the user (today is later than the end date).
        Then:
            - 'Student Status' is set to 'Expired'.
            - 'Expire Date' is stored and set to the end date for the user.
        """
        self._profile(self.user)
        self._register_contract(self.self_paced_contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        # Update enrollment.created to simulate a scenario that the self-paced course has expired
        enrollment = CourseEnrollment.get_enrollment(self.user, self.self_paced_course.id)
        enrollment.created = enrollment.created - timedelta(days=self.individual_end_days + 1)
        enrollment.save()

        call_command('update_biz_score_status')

        def assert_score(contract, course):
            column_list, record_list = self.assert_finished(1, contract, course)
            self.assert_column_list(column_list, contract, course, self_paced=True)

            record_dict = record_list[0]
            record_items = record_dict.iteritems()
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CONTRACT_ID, contract.id))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_COURSE_ID, unicode(course.id)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_DOCUMENT_TYPE, ScoreStore.FIELD_DOCUMENT_TYPE__RECORD))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_FULL_NAME, self.user.profile.name))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_USERNAME, self.user.username))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_EMAIL, self.user.email))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME1, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_ADDITIONAL_INFO + ScoreStore.FIELD_DELIMITER + ADDITIONAL_DISPLAY_NAME2, '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE)))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_STUDENT_STATUS, ScoreStore.FIELD_STUDENT_STATUS__EXPIRED))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_STATUS, ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED))
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_ENROLL_DATE)
            self.assert_datetime(v, CourseEnrollment.get_enrollment(self.user, course.id).created)
            k, v = record_items.next()
            self.assertEquals(k, ScoreStore.FIELD_EXPIRE_DATE)
            enrollment = CourseEnrollment.get_enrollment(self.user, course.id)
            self.assert_datetime(v, enrollment.created + timedelta(self.individual_end_days))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, None))
            self.assertEquals(record_items.next(), (ScoreStore.FIELD_TOTAL_SCORE, 0.0))
            self.assertRaises(StopIteration, record_items.next)

        assert_score(self.self_paced_contract, self.self_paced_course)

    def test_target_user_count(self):
        for var in range(0, 50):
            user = UserFactory.create()
            self._input_contract(self.contract, user)
        for var in range(0, 50):
            user = UserFactory.create()
            self._register_contract(self.contract, user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        for var in range(0, 50):
            user = UserFactory.create()
            self._unregister_contract(self.contract, user)

        call_command('update_biz_score_status')

        self.assert_finished(100, self.contract, self.course1)
        self.assert_finished(100, self.contract, self.course2)

    def test_course_does_not_exist(self):

        not_exist_course_id = CourseKey.from_string('course-v1:not+exist+course')
        not_exist_course_contract = self._create_contract(
            detail_courses=[not_exist_course_id],
        )

        call_command('update_biz_score_status', not_exist_course_contract.id)

        self.assert_error(not_exist_course_contract, not_exist_course_id)
        self.mock_log.warning.assert_called_once()

    def test_error(self):
        self._input_contract(self.contract, self.user)

        # Setup another contract
        another_course = CourseFactory.create(org=self.gacco_organization.org_code, number='another_course', run='run')
        another_contract = self._create_contract(detail_courses=[another_course])
        self._input_contract(another_contract, self.user)

        with patch(
                'biz.djangoapps.ga_achievement.management.commands.update_biz_score_status.ScoreStore.remove_documents',
                side_effect=Exception()):
            call_command('update_biz_score_status')

        self.assert_error(self.contract, self.course1.id)
        self.assert_error(self.contract, self.course2.id)
        self.assert_error(another_contract, another_course.id)
        self.mock_log.error.assert_called_once()

    def _create_batch_status(self, contract, course, status, count=None):
        self.batch_status = ScoreBatchStatusFactory.create(contract=contract,
                                                           course_id=unicode(course.id),
                                                           status=status,
                                                           student_count=count)

    def test_if_batch_status_exist_today(self):
        self.mock_exists_today.return_value = True
        self._register_contract(self.contract, self.user)

        call_command('update_biz_score_status')

        def assert_not_started(contract, course):
            self.assertFalse(ScoreBatchStatus.objects.filter(contract=contract, course_id=course.id,
                                                             status=BATCH_STATUS_STARTED).exists())
            self.assertFalse(ScoreBatchStatus.objects.filter(contract=contract, course_id=course.id,
                                                             status=BATCH_STATUS_FINISHED).exists())
            self.assertEquals(len(ScoreStore(contract.id, unicode(course.id)).get_documents()), 0)

        assert_not_started(self.contract, self.course1)
        assert_not_started(self.contract, self.course2)

    def test_force_if_batch_status_exist_today(self):
        self.mock_exists_today.return_value = True
        self._create_batch_status(self.contract, self.course1, BATCH_STATUS_ERROR)
        self._register_contract(self.contract, self.user)

        call_command('update_biz_score_status', force=True)

        self.assert_finished(1, self.contract, self.course1)
        self.assert_finished(1, self.contract, self.course2)

    def test_success_log(self):
        for var in range(0, 50):
            user = UserFactory.create()
            self._input_contract(self.contract, user)
        for var in range(0, 50):
            user = UserFactory.create()
            self._register_contract(self.contract, user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        call_command('update_biz_score_status', self.contract.id)

        self.mock_log.info.assert_any_call(
            u'Removed ScoreStore records. contract_id={} course_id={}'.format(
                self.contract.id, self.course1.id))
        self.mock_log.info.assert_any_call(
            u'Removed ScoreStore records. contract_id={} course_id={}'.format(
                self.contract.id, self.course2.id))

        self.mock_log.info.assert_any_call(
            u'Stored ScoreStore record count(100). contract_id={} course_id={}'.format(
                self.contract.id, self.course1.id))
        self.mock_log.info.assert_any_call(
            u'Stored ScoreStore record count(100). contract_id={} course_id={}'.format(
                self.contract.id, self.course2.id))

        ScoreBatchStatus.objects.get(contract=self.contract, course_id=self.course1.id, status=BATCH_STATUS_FINISHED, student_count=100)
        ScoreBatchStatus.objects.get(contract=self.contract, course_id=self.course2.id, status=BATCH_STATUS_FINISHED, student_count=100)

    @override_settings(
        MAX_RETRY_REMOVE_DOCUMENTS=3,
        SLEEP_RETRY_REMOVE_DOCUMENTS=3,
        MAX_RETRY_SET_DOCUMENTS=3,
        SLEEP_RETRY_SET_DOCUMENTS=3,
    )
    @patch('biz.djangoapps.ga_achievement.management.commands.update_biz_score_status.time.sleep')
    def test_error_log_can_not_remove_documents(self, mock_time_sleep):
        for var in range(0, 50):
            user = UserFactory.create()
            self._input_contract(self.contract, user)
        for var in range(0, 50):
            user = UserFactory.create()
            self._register_contract(self.contract, user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        with patch('biz.djangoapps.ga_achievement.management.commands.update_biz_score_status.ScoreStore.get_count', return_value=100):
            call_command('update_biz_score_status', self.contract.id)

        for i in range(3):
            self.mock_log.warning.assert_any_call(
                u'Can not remove(try:{},sleep:3) ScoreStore record count(100). contract_id={} course_id={}'.format(
                    i + 1, self.contract.id, self.course1.id))
        for i in range(3):
            self.mock_log.warning.assert_any_call(
                u'Can not remove(try:{},sleep:3) ScoreStore record count(100). contract_id={} course_id={}'.format(
                    i + 1, self.contract.id, self.course2.id))

        self.assertEqual(6, mock_time_sleep.call_count)
        mock_time_sleep.assert_any_call(3)

        self.mock_log.error.assert_any_call(
            u'Unexpected error occurred: Can not remove ScoreStore record count(100). contract_id={} course_id={}'.format(
                self.contract.id, self.course1.id))
        self.mock_log.error.assert_any_call(
            u'Unexpected error occurred: Can not remove ScoreStore record count(100). contract_id={} course_id={}'.format(
                self.contract.id, self.course2.id))

        ScoreBatchStatus.objects.get(contract=self.contract, course_id=self.course1.id, status=BATCH_STATUS_ERROR, student_count=None)
        ScoreBatchStatus.objects.get(contract=self.contract, course_id=self.course2.id, status=BATCH_STATUS_ERROR, student_count=None)

    @override_settings(
        MAX_RETRY_REMOVE_DOCUMENTS=3,
        SLEEP_RETRY_REMOVE_DOCUMENTS=0,
        MAX_RETRY_SET_DOCUMENTS=3,
        SLEEP_RETRY_SET_DOCUMENTS=0,
    )
    @patch('biz.djangoapps.ga_achievement.management.commands.update_biz_score_status.time.sleep')
    def test_error_log_can_not_set_documents(self, mock_time_sleep):
        for var in range(0, 50):
            user = UserFactory.create()
            self._input_contract(self.contract, user)
        for var in range(0, 50):
            user = UserFactory.create()
            self._register_contract(self.contract, user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        with patch('biz.djangoapps.ga_achievement.management.commands.update_biz_score_status.ScoreStore.get_count', return_value=0):
            call_command('update_biz_score_status', self.contract.id)

        self.mock_log.info.assert_any_call(
            u'Removed ScoreStore records. contract_id={} course_id={}'.format(
                self.contract.id, self.course1.id))
        self.mock_log.info.assert_any_call(
            u'Removed ScoreStore records. contract_id={} course_id={}'.format(
                self.contract.id, self.course2.id))

        for i in range(3):
            self.mock_log.warning.assert_any_call(
                u'Can not store(try:{},sleep:0) ScoreStore record count(-1) does not match Contract Register record count(100) or records count(100). contract_id={} course_id={}'.format(
                    i + 1, self.contract.id, self.course1.id))
        for i in range(3):
            self.mock_log.warning.assert_any_call(
                u'Can not store(try:{},sleep:0) ScoreStore record count(-1) does not match Contract Register record count(100) or records count(100). contract_id={} course_id={}'.format(
                    i + 1, self.contract.id, self.course2.id))

        mock_time_sleep.assert_not_called()

        self.mock_log.error.assert_any_call(
            u'Unexpected error occurred: ScoreStore record count(-1) does not match Contract Register record count(100) or records count(100). contract_id={} course_id={}'.format(
                self.contract.id, self.course1.id))
        self.mock_log.error.assert_any_call(
            u'Unexpected error occurred: ScoreStore record count(-1) does not match Contract Register record count(100) or records count(100). contract_id={} course_id={}'.format(
                self.contract.id, self.course2.id))

        ScoreBatchStatus.objects.get(contract=self.contract, course_id=self.course1.id, status=BATCH_STATUS_ERROR, student_count=None)
        ScoreBatchStatus.objects.get(contract=self.contract, course_id=self.course2.id, status=BATCH_STATUS_ERROR, student_count=None)


class TestGroupedTargetSections(ModuleStoreTestCase):
    """
    Tests for TargetSection and GroupedTargetSections
    """
    def setUp(self):
        super(TestGroupedTargetSections, self).setUp()
        self.course = CourseFactory.create(org='TestX', course='TS101', run='T1')
        self.chapter_x = ItemFactory.create(parent=self.course, category='chapter', display_name='chapter_x')
        self.chapter_y = ItemFactory.create(parent=self.course, category='chapter', display_name='chapter_y')
        self.section_x1 = ItemFactory.create(parent=self.chapter_x, category='sequential', display_name='sequential_x1')
        self.section_y1 = ItemFactory.create(parent=self.chapter_y, category='sequential', display_name='sequential_y1')
        self.section_y2 = ItemFactory.create(parent=self.chapter_y, category='sequential', display_name='sequential_y2')
        self.target_section_x1 = TargetSection(self.section_x1)
        self.target_section_y1 = TargetSection(self.section_y1)
        self.target_section_y2 = TargetSection(self.section_y2)

    def test_target_section_init_invalid(self):
        with self.assertRaises(TypeError):
            TargetSection('test')

    def test_grouped_target_sections_append_invalid(self):
        grouped_target_sections = GroupedTargetSections()
        with self.assertRaises(TypeError):
            grouped_target_sections.append('test')

    def test_grouped_target_sections_with_no_element(self):
        grouped_target_sections = GroupedTargetSections()
        self.assertEquals(grouped_target_sections.course_key, None)
        self.assertEquals(grouped_target_sections.course_display_name, None)
        self.assertEquals(grouped_target_sections.keys(), [])
        self.assertEquals(grouped_target_sections.values(), [])

    def test_grouped_target_sections(self):
        grouped_target_sections = GroupedTargetSections()
        grouped_target_sections.append(self.target_section_x1)
        grouped_target_sections.append(self.target_section_y1)
        grouped_target_sections.append(self.target_section_y2)

        self.assertEquals(grouped_target_sections.course_key, self.course.id)
        self.assertEquals(grouped_target_sections.course_display_name, self.course.display_name)
        self.assertEquals(grouped_target_sections.keys(), [self.chapter_x.location, self.chapter_y.location])
        self.assertEquals(grouped_target_sections.values(), [[self.target_section_x1], [self.target_section_y1, self.target_section_y2]])
        self.assertEquals(grouped_target_sections.get(self.chapter_x.location), [self.target_section_x1])
        self.assertEquals(grouped_target_sections.get(self.chapter_y.location), [self.target_section_y1, self.target_section_y2])
        self.assertEquals(grouped_target_sections.target_sections, [self.target_section_x1, self.target_section_y1, self.target_section_y2])


class TestGetGroupedTargetSections(ModuleStoreTestCase):
    """
    Tests for get_grouped_target_sections
    """
    def setUp(self):
        super(TestGetGroupedTargetSections, self).setUp()
        self.course = CourseFactory.create(org='TestX', course='TS101', run='T1')
        self.chapter_x = ItemFactory.create(parent=self.course, category='chapter', display_name='chapter_x')
        self.chapter_y = ItemFactory.create(parent=self.course, category='chapter', display_name='chapter_y')
        self.section_x1 = ItemFactory.create(parent=self.chapter_x, category='sequential', display_name='sequential_x1', metadata={'graded': True, 'format': 'format_x1'})
        self.section_y1 = ItemFactory.create(parent=self.chapter_y, category='sequential', display_name='sequential_y1', metadata={'graded': True, 'format': 'format_y1'})
        self.section_y2 = ItemFactory.create(parent=self.chapter_y, category='sequential', display_name='sequential_y2', metadata={'graded': True, 'format': 'format_y2'})
        self.vertical_x1a = ItemFactory.create(parent=self.section_x1, category='vertical', display_name='vertical_x1a')
        self.vertical_y1a = ItemFactory.create(parent=self.section_y1, category='vertical', display_name='vertical_y1a')
        self.vertical_y2a = ItemFactory.create(parent=self.section_y2, category='vertical', display_name='vertical_y2a')
        self.component_x1a_1 = ItemFactory.create(parent=self.vertical_x1a, category='problem', display_name='component_x1a_1')
        self.component_y1a_1 = ItemFactory.create(parent=self.vertical_y1a, category='problem', display_name='component_y1a_1')
        self.component_y2a_1 = ItemFactory.create(parent=self.vertical_y2a, category='problem', display_name='component_y2a_1')

    def test_if_chapter_is_hide_from_students(self):
        self.chapter_x.visible_to_staff_only = True
        self.store.update_item(self.chapter_x, self.user.id)

        grouped_target_sections = get_grouped_target_sections(self.course)
        self.assertEquals(
            [ts.module_id for ts in grouped_target_sections.target_sections],
            [unicode(self.section_x1.location), unicode(self.section_y1.location), unicode(self.section_y2.location)]
        )

    def test_if_section_is_hide_from_students(self):
        self.section_y1.visible_to_staff_only = True
        self.store.update_item(self.section_y1, self.user.id)

        grouped_target_sections = get_grouped_target_sections(self.course)
        self.assertEquals(
            [ts.module_id for ts in grouped_target_sections.target_sections],
            [unicode(self.section_x1.location), unicode(self.section_y1.location), unicode(self.section_y2.location)]
        )

    def test_if_section_grade_is_not_set(self):
        self.section_y2.graded = False
        self.store.update_item(self.section_y2, self.user.id)

        grouped_target_sections = get_grouped_target_sections(self.course)
        self.assertEquals(
            [ts.module_id for ts in grouped_target_sections.target_sections],
            [unicode(self.section_x1.location), unicode(self.section_y1.location)]
        )

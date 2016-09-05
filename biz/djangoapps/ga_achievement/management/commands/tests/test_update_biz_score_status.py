"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import logging
from mock import patch
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings

from biz.djangoapps.ga_achievement.achievement_store import ScoreStore
from biz.djangoapps.ga_achievement.management.commands import update_biz_score_status
from biz.djangoapps.ga_achievement.models import ScoreBatchStatus, BATCH_STATUS_STARTED, BATCH_STATUS_FINISHED, BATCH_STATUS_ERROR
from biz.djangoapps.util.mongo_utils import DEFAULT_DATETIME
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from certificates.models import CertificateStatuses, GeneratedCertificate
from certificates.tests.factories import GeneratedCertificateFactory
from courseware import grades
from courseware.tests.helpers import LoginEnrollmentTestCase
from opaque_keys.edx.locator import CourseLocator
from student.models import CourseEnrollment
from student.tests.factories import UserFactory, UserProfileFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

command_output_file = tempfile.NamedTemporaryFile()

ADDITIONAL_DISPLAY_NAME1 = 'test_number'
ADDITIONAL_DISPLAY_NAME2 = 'test_section'
ADDITIONAL_SETTINGS_VALUE = 'test_value'
DEFAULT_KEY = [
    ScoreStore.FIELD_CONTRACT_ID,
    ScoreStore.FIELD_COURSE_ID,
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

    def setUp(self):
        super(UpdateBizScoreStatusTest, self).setUp()
        self.course1 = CourseFactory.create(org=self.gacco_organization.org_code, number='course1', run='run')
        self.course2 = CourseFactory.create(org=self.gacco_organization.org_code, number='course2', run='run')
        self.contract = self._create_contract(
            detail_courses=[self.course1, self.course2],
            additional_display_names=[ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_DISPLAY_NAME2],
        )
        # Setup mock
        patcher_grade = patch.object(grades, 'grade')
        self.mock_grade = patcher_grade.start()
        self.mock_grade.return_value = {
            'section_breakdown': [],
            'percent': 0,
        }
        self.addCleanup(patcher_grade.stop)

        patcher_log = patch('biz.djangoapps.ga_achievement.management.commands.update_biz_score_status.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

    def assert_finished(self, count, contract, course):
        ScoreBatchStatus.objects.get(contract=contract, course_id=course.id, status=BATCH_STATUS_STARTED)
        ScoreBatchStatus.objects.get(contract=contract, course_id=course.id, status=BATCH_STATUS_FINISHED, student_count=count)

        score_list = ScoreStore(contract.id, unicode(course.id)).get_documents()
        self.assertEquals(len(score_list), count)
        return score_list

    def assert_error(self, contract, course):
        ScoreBatchStatus.objects.get(contract=contract, course_id=course.id, status=BATCH_STATUS_STARTED)
        ScoreBatchStatus.objects.get(contract=contract, course_id=course.id, status=BATCH_STATUS_ERROR, student_count=None)

        score_list = ScoreStore(contract.id, unicode(course.id)).get_documents()
        self.assertEquals(len(score_list), 0)
        return score_list

    def assert_datetime(self, first, second):
        _format = '%Y%m%d%H%M%S%Z'
        self.assertEquals(first.strftime(_format), second.strftime(_format))

    def test_contract_with_no_user(self):
        call_command('update_biz_score_status')

        self.assert_finished(0, self.contract, self.course1)
        self.assert_finished(0, self.contract, self.course2)

    def test_contract_with_not_enrolled_user(self):
        self._input_contract(self.contract, self.user)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, self.contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            self.assertIsNone(score_dict[ScoreStore.FIELD_FULL_NAME])
            self.assertEquals(score_dict[ScoreStore.FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[ScoreStore.FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[ScoreStore.FIELD_STUDENT_STATUS], ScoreStore.FIELD_STUDENT_STATUS__NOT_ENROLLED)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_STATUS], ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED)
            self.assertEquals(score_dict[ScoreStore.FIELD_ENROLL_DATE], DEFAULT_DATETIME)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE], DEFAULT_DATETIME)
            self.assertEquals(score_dict[ScoreStore.FIELD_TOTAL_SCORE], 0)
            self.assertIsNone(score_dict[ADDITIONAL_DISPLAY_NAME1])
            self.assertIsNone(score_dict[ADDITIONAL_DISPLAY_NAME2])

        assert_score(self.course1)
        assert_score(self.course2)

    def test_contract_with_enrolled_user(self):
        self._profile(self.user)
        self._register_contract(self.contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, self.contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            self.assertEquals(score_dict[ScoreStore.FIELD_FULL_NAME], self.user.profile.name)
            self.assertEquals(score_dict[ScoreStore.FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[ScoreStore.FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[ScoreStore.FIELD_STUDENT_STATUS], ScoreStore.FIELD_STUDENT_STATUS__ENROLLED)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_STATUS], ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED)
            self.assert_datetime(score_dict[ScoreStore.FIELD_ENROLL_DATE], CourseEnrollment.get_enrollment(self.user, course.id).created)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE], DEFAULT_DATETIME)
            self.assertEquals(score_dict[ScoreStore.FIELD_TOTAL_SCORE], 0)
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME1], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE))
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME2], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE))

        assert_score(self.course1)
        assert_score(self.course2)

    def test_contract_with_grade(self):
        self._profile(self.user)
        self._register_contract(self.contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)

        grade_return_value = {
            'section_breakdown': [
                {'label': 'First', 'percent': 11.11111111},
                {'label': 'Second', 'percent': 22.22222222},
                {'label': 'Third', 'percent': 33.33333333},
                {'label': 'Fourth', 'percent': 44.44444444},
                {'label': 'Fifth', 'percent': 55.55555555},
                {'label': 'Sixth', 'percent': 66.66666666},
            ],
            'percent': 88.8888888888
        }
        self.mock_grade.return_value = grade_return_value
        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, self.contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            self.assertEquals(score_dict[ScoreStore.FIELD_FULL_NAME], self.user.profile.name)
            self.assertEquals(score_dict[ScoreStore.FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[ScoreStore.FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[ScoreStore.FIELD_STUDENT_STATUS], ScoreStore.FIELD_STUDENT_STATUS__ENROLLED)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_STATUS], ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE)
            self.assert_datetime(score_dict[ScoreStore.FIELD_ENROLL_DATE], CourseEnrollment.get_enrollment(self.user, course.id).created)
            self.assert_datetime(score_dict[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE], GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            self.assertEquals(score_dict[ScoreStore.FIELD_TOTAL_SCORE], 88.89)
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME1], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE))
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME2], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE))

            self.assertEquals(score_dict['First'], 11.11)
            self.assertEquals(score_dict['Second'], 22.22)
            self.assertEquals(score_dict['Third'], 33.33)
            self.assertEquals(score_dict['Fourth'], 44.44)
            self.assertEquals(score_dict['Fifth'], 55.56)
            self.assertEquals(score_dict['Sixth'], 66.67)

        assert_score(self.course1)
        assert_score(self.course2)

    def test_contract_with_unenrolled_user(self):
        self._profile(self.user)
        self._register_contract(self.contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)
        self._unenroll(self.user, self.course1)
        self._unenroll(self.user, self.course2)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, self.contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            self.assertEquals(score_dict[ScoreStore.FIELD_FULL_NAME], self.user.profile.name)
            self.assertEquals(score_dict[ScoreStore.FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[ScoreStore.FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[ScoreStore.FIELD_STUDENT_STATUS], ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_STATUS], ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE)
            self.assert_datetime(score_dict[ScoreStore.FIELD_ENROLL_DATE], CourseEnrollment.get_enrollment(self.user, course.id).created)
            self.assert_datetime(score_dict[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE], GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            self.assertEquals(score_dict[ScoreStore.FIELD_TOTAL_SCORE], 0)
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME1], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE))
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME2], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE))

        assert_score(self.course1)
        assert_score(self.course2)

    def test_contract_with_disabled_user(self):
        self._profile(self.user)
        self._register_contract(self.contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)
        self._account_disable(self.user)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, self.contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            self.assertEquals(score_dict[ScoreStore.FIELD_FULL_NAME], self.user.profile.name)
            self.assertEquals(score_dict[ScoreStore.FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[ScoreStore.FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[ScoreStore.FIELD_STUDENT_STATUS], ScoreStore.FIELD_STUDENT_STATUS__DISABLED)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_STATUS], ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE)
            self.assert_datetime(score_dict[ScoreStore.FIELD_ENROLL_DATE], CourseEnrollment.get_enrollment(self.user, course.id).created)
            self.assert_datetime(score_dict[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE], GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            self.assertEquals(score_dict[ScoreStore.FIELD_TOTAL_SCORE], 0)
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME1], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE))
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME2], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE))

        assert_score(self.course1)
        assert_score(self.course2)

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

        class DummyCourseDescriptor(object):
            def __init__(self, org, course, run):
                self.id = CourseLocator(org, course, run)

        not_exist_course = DummyCourseDescriptor('not', 'exist', 'course')
        not_exist_course_contract = self._create_contract(
            detail_courses=[not_exist_course],
        )

        call_command('update_biz_score_status', not_exist_course_contract.id)

        self.assert_error(not_exist_course_contract, not_exist_course)
        self.mock_log.warning.assert_called_once()

    def test_error(self):
        self.mock_grade.side_effect = Exception()
        self._input_contract(self.contract, self.user)

        call_command('update_biz_score_status')

        self.assert_error(self.contract, self.course1)
        self.assert_error(self.contract, self.course2)
        self.mock_log.error.assert_called_once()

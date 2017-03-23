"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
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
from biz.djangoapps.ga_achievement.models import ScoreBatchStatus, BATCH_STATUS_STARTED, BATCH_STATUS_FINISHED, BATCH_STATUS_ERROR
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.util.mongo_utils import DEFAULT_DATETIME
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from certificates.models import CertificateStatuses, GeneratedCertificate
from certificates.tests.factories import GeneratedCertificateFactory
from courseware import grades
from courseware.tests.helpers import LoginEnrollmentTestCase
from opaque_keys.edx.keys import CourseKey
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

    def _biz_user(self, user, login_code):
        if login_code:
            BizUserFactory.create(user=user, login_code=login_code)

    def setUp(self):
        super(UpdateBizScoreStatusTest, self).setUp()
        self.course1 = CourseFactory.create(org=self.gacco_organization.org_code, number='course1', run='run')
        self.course2 = CourseFactory.create(org=self.gacco_organization.org_code, number='course2', run='run')
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

    def assert_error(self, contract, course_id):
        ScoreBatchStatus.objects.get(contract=contract, course_id=course_id, status=BATCH_STATUS_STARTED)
        ScoreBatchStatus.objects.get(contract=contract, course_id=course_id, status=BATCH_STATUS_ERROR, student_count=None)

        score_list = ScoreStore(contract.id, unicode(course_id)).get_documents()
        self.assertEquals(len(score_list), 0)
        return score_list

    def assert_datetime(self, first, second):
        _format = '%Y%m%d%H%M%S%Z'
        self.assertEquals(first.strftime(_format), second.strftime(_format))

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
        self._biz_user(self.user, login_code)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, self.contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            if login_code:
                self.assertEquals(score_dict[ScoreStore.FIELD_LOGIN_CODE], login_code)
            else:
                self.assertIsNone(score_dict.get(ScoreStore.FIELD_LOGIN_CODE))
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
            self.assertTrue(ScoreStore.FIELD_EXPIRE_DATE not in score_dict)

        assert_score(self.course1)
        assert_score(self.course2)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_enrolled_user(self, login_code):
        self._profile(self.user)
        self._register_contract(self.contract, self.user, additional_value=ADDITIONAL_SETTINGS_VALUE)
        self._biz_user(self.user, login_code)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, self.contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            if login_code:
                self.assertEquals(score_dict[ScoreStore.FIELD_LOGIN_CODE], login_code)
            else:
                self.assertIsNone(score_dict.get(ScoreStore.FIELD_LOGIN_CODE))
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
            self.assertTrue(ScoreStore.FIELD_EXPIRE_DATE not in score_dict)

        assert_score(self.course1)
        assert_score(self.course2)

    @ddt.data(
        'test_login_code',
        None,
    )
    def test_contract_with_grade(self, login_code):
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

        self._biz_user(self.user, login_code)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, self.contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            if login_code:
                self.assertEquals(score_dict[ScoreStore.FIELD_LOGIN_CODE], login_code)
            else:
                self.assertIsNone(score_dict.get(ScoreStore.FIELD_LOGIN_CODE))
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
            self.assertTrue(ScoreStore.FIELD_EXPIRE_DATE not in score_dict)

            self.assertEquals(score_dict['First'], 11.11)
            self.assertEquals(score_dict['Second'], 22.22)
            self.assertEquals(score_dict['Third'], 33.33)
            self.assertEquals(score_dict['Fourth'], 44.44)
            self.assertEquals(score_dict['Fifth'], 55.56)
            self.assertEquals(score_dict['Sixth'], 66.67)

        assert_score(self.course1)
        assert_score(self.course2)

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
        self._biz_user(self.user, login_code)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, self.contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            if login_code:
                self.assertEquals(score_dict[ScoreStore.FIELD_LOGIN_CODE], login_code)
            else:
                self.assertIsNone(score_dict.get(ScoreStore.FIELD_LOGIN_CODE))
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
            self.assertTrue(ScoreStore.FIELD_EXPIRE_DATE not in score_dict)

        assert_score(self.course1)
        assert_score(self.course2)

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
        self._biz_user(self.user, login_code)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, self.contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            if login_code:
                self.assertEquals(score_dict[ScoreStore.FIELD_LOGIN_CODE], login_code)
            else:
                self.assertIsNone(score_dict.get(ScoreStore.FIELD_LOGIN_CODE))
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
            self.assertTrue(ScoreStore.FIELD_EXPIRE_DATE not in score_dict)

        assert_score(self.course1)
        assert_score(self.course2)

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
            score_list = self.assert_finished(1, contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            self.assertIsNone(score_dict.get(ScoreStore.FIELD_LOGIN_CODE))
            self.assertEquals(score_dict[ScoreStore.FIELD_FULL_NAME], self.user.profile.name)
            self.assertEquals(score_dict[ScoreStore.FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[ScoreStore.FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[ScoreStore.FIELD_STUDENT_STATUS], ScoreStore.FIELD_STUDENT_STATUS__NOT_ENROLLED)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_STATUS], ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED)
            self.assertEquals(score_dict[ScoreStore.FIELD_ENROLL_DATE], DEFAULT_DATETIME)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE], DEFAULT_DATETIME)
            self.assertEquals(score_dict[ScoreStore.FIELD_TOTAL_SCORE], 0)
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME1], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE))
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME2], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE))
            self.assertEquals(score_dict[ScoreStore.FIELD_EXPIRE_DATE], DEFAULT_DATETIME)

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
            score_list = self.assert_finished(1, contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            self.assertIsNone(score_dict.get(ScoreStore.FIELD_LOGIN_CODE))
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
            enrollment = CourseEnrollment.get_enrollment(self.user, course.id)
            self.assert_datetime(score_dict[ScoreStore.FIELD_EXPIRE_DATE], enrollment.created + timedelta(self.individual_end_days))

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
            score_list = self.assert_finished(1, contract, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[ScoreStore.FIELD_CONTRACT_ID], contract.id)
            self.assertEquals(score_dict[ScoreStore.FIELD_COURSE_ID], unicode(course.id))
            self.assertIsNone(score_dict.get(ScoreStore.FIELD_LOGIN_CODE))
            self.assertEquals(score_dict[ScoreStore.FIELD_FULL_NAME], self.user.profile.name)
            self.assertEquals(score_dict[ScoreStore.FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[ScoreStore.FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[ScoreStore.FIELD_STUDENT_STATUS], ScoreStore.FIELD_STUDENT_STATUS__EXPIRED)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_STATUS], ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED)
            self.assert_datetime(score_dict[ScoreStore.FIELD_ENROLL_DATE], CourseEnrollment.get_enrollment(self.user, course.id).created)
            self.assertEquals(score_dict[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE], DEFAULT_DATETIME)
            self.assertEquals(score_dict[ScoreStore.FIELD_TOTAL_SCORE], 0)
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME1], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE))
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME2], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE))
            enrollment = CourseEnrollment.get_enrollment(self.user, course.id)
            self.assert_datetime(score_dict[ScoreStore.FIELD_EXPIRE_DATE], enrollment.created + timedelta(self.individual_end_days))

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
        self.mock_grade.side_effect = Exception()
        self._input_contract(self.contract, self.user)

        call_command('update_biz_score_status')

        self.assert_error(self.contract, self.course1.id)
        self.assert_error(self.contract, self.course2.id)
        self.mock_log.error.assert_called_once()

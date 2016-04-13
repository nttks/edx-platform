"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from mock import patch
import tempfile

from django.test.utils import override_settings
from django.core.management import call_command

from biz.djangoapps.ga_achievement.models import ScoreBatchStatus, SCORE_BATCH_STATUS_STARTED, SCORE_BATCH_STATUS_FINISHED, SCORE_BATCH_STATUS_ERROR
from biz.djangoapps.ga_achievement.score_store import (
    ScoreStore, SCORE_STORE_FIELD_CONTRACT_ID, SCORE_STORE_FIELD_COURSE_ID,
    SCORE_STORE_FIELD_NAME, SCORE_STORE_FIELD_USERNAME, SCORE_STORE_FIELD_EMAIL, SCORE_STORE_FIELD_STUDENT_STATUS,
    SCORE_STORE_FIELD_STUDENT_STATUS_NOT_ENROLLED, SCORE_STORE_FIELD_STUDENT_STATUS_ENROLLED,
    SCORE_STORE_FIELD_STUDENT_STATUS_UNENROLLED, SCORE_STORE_FIELD_STUDENT_STATUS_DISABLED,
    SCORE_STORE_FIELD_CERTIFICATE_STATUS, SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE,
    SCORE_STORE_FIELD_CERTIFICATE_STATUS_UNPUBLISHED, SCORE_STORE_FIELD_ENROLL_DATE,
    SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE, SCORE_STORE_FIELD_TOTAL_SCORE
)
from biz.djangoapps.ga_contract.tests.factories import AdditionalInfoFactory, ContractFactory, ContractDetailFactory
from biz.djangoapps.ga_invitation.tests.factories import AdditionalInfoSettingFactory, ContractRegisterFactory
from biz.djangoapps.ga_invitation.models import INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE
from biz.djangoapps.util.mongo_utils import DEFAULT_DATETIME
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from certificates.models import CertificateStatuses, GeneratedCertificate
from certificates.tests.factories import GeneratedCertificateFactory
from courseware.tests.helpers import LoginEnrollmentTestCase
from courseware.courses import get_course_by_id
from student.models import CourseEnrollment, UserStanding
from student.tests.factories import UserFactory, UserProfileFactory, UserStandingFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


COMMAND_OUTPUT_FILE = tempfile.NamedTemporaryFile()
ADDITIONAL_DISPLAY_NAME1 = 'test_number'
ADDITIONAL_DISPLAY_NAME2 = 'test_section'
ADDITIONAL_SETTINGS_VALUE = 'test_value'
DEFAULT_KEY = [
    SCORE_STORE_FIELD_CONTRACT_ID,
    SCORE_STORE_FIELD_COURSE_ID,
    SCORE_STORE_FIELD_NAME,
    SCORE_STORE_FIELD_USERNAME,
    SCORE_STORE_FIELD_EMAIL,
    SCORE_STORE_FIELD_STUDENT_STATUS,
    SCORE_STORE_FIELD_CERTIFICATE_STATUS,
    SCORE_STORE_FIELD_ENROLL_DATE,
    SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE,
    SCORE_STORE_FIELD_TOTAL_SCORE,
    ADDITIONAL_DISPLAY_NAME1,
    ADDITIONAL_DISPLAY_NAME2,
]


class UpdateBizScoreStatusTest(BizStoreTestBase, ModuleStoreTestCase, LoginEnrollmentTestCase):

    def _input_contract(self, user):
        ContractRegisterFactory.create(user=user, contract=self.contract, status=INPUT_INVITATION_CODE)

    def _register_contract(self, user):
        ContractRegisterFactory.create(user=user, contract=self.contract, status=REGISTER_INVITATION_CODE)
        for additional_info in self.contract.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=user,
                contract=self.contract,
                display_name=additional_info.display_name,
                value='{}_{}'.format(additional_info.display_name, ADDITIONAL_SETTINGS_VALUE)
            )
        for detail in self.contract.details.all():
            CourseEnrollment.enroll(user, get_course_by_id(detail.course_id).id)

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

    def _account_disable(self, user):
        UserStandingFactory.create(user=user, account_status=UserStanding.ACCOUNT_DISABLED, changed_by=self.user)

    def setUp(self):
        super(UpdateBizScoreStatusTest, self).setUp()
        self.course1 = CourseFactory.create(org='gacco', number='course1', run='run')
        self.course2 = CourseFactory.create(org='gacco', number='course2', run='run')
        self.org_a = self._create_organization(org_name='a', org_code='a', creator_org=self.gacco_organization)
        self.contract = ContractFactory.create(contractor_organization=self.org_a,
                                               owner_organization=self.gacco_organization,
                                               created_by=UserFactory.create())
        ContractDetailFactory.create(contract=self.contract, course_id=self.course1.id)
        ContractDetailFactory.create(contract=self.contract, course_id=self.course2.id)
        AdditionalInfoFactory.create(contract=self.contract, display_name=ADDITIONAL_DISPLAY_NAME1)
        AdditionalInfoFactory.create(contract=self.contract, display_name=ADDITIONAL_DISPLAY_NAME2)

    def assert_finished(self, count, course):
        ScoreBatchStatus.objects.get(contract=self.contract, course_id=course.id, status=SCORE_BATCH_STATUS_STARTED)
        ScoreBatchStatus.objects.get(contract=self.contract, course_id=course.id, status=SCORE_BATCH_STATUS_FINISHED, student_count=count)

        score_list = ScoreStore(self.contract.id, unicode(course.id)).get_documents()
        self.assertEquals(len(score_list), count)
        return score_list

    def assert_error(self, course):
        ScoreBatchStatus.objects.get(contract=self.contract, course_id=course.id, status=SCORE_BATCH_STATUS_STARTED)
        ScoreBatchStatus.objects.get(contract=self.contract, course_id=course.id, status=SCORE_BATCH_STATUS_ERROR, student_count=None)

        score_list = ScoreStore(self.contract.id, unicode(course.id)).get_documents()
        self.assertEquals(len(score_list), 0)
        return score_list

    def assert_datetime(self, first, second):
        _format = '%Y%m%d%H%M%S%Z'
        self.assertEquals(first.strftime(_format), second.strftime(_format))

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=COMMAND_OUTPUT_FILE.name)
    def test_non_register(self):
        call_command('update_biz_score_status')

        self.assert_finished(0, self.course1)
        self.assert_finished(0, self.course2)

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=COMMAND_OUTPUT_FILE.name)
    def test_input_contract(self):
        self._input_contract(self.user)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_COURSE_ID], unicode(course.id))
            self.assertIsNone(score_dict[SCORE_STORE_FIELD_NAME])
            self.assertEquals(score_dict[SCORE_STORE_FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_STUDENT_STATUS], SCORE_STORE_FIELD_STUDENT_STATUS_NOT_ENROLLED)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CERTIFICATE_STATUS], SCORE_STORE_FIELD_CERTIFICATE_STATUS_UNPUBLISHED)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_ENROLL_DATE], DEFAULT_DATETIME)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE], DEFAULT_DATETIME)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_TOTAL_SCORE], 0)
            self.assertIsNone(score_dict[ADDITIONAL_DISPLAY_NAME1])
            self.assertIsNone(score_dict[ADDITIONAL_DISPLAY_NAME2])
            for k, v in score_dict.items():
                if k not in DEFAULT_KEY:
                    self.assertEquals(v, 0)

        assert_score(self.course1)
        assert_score(self.course2)

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=COMMAND_OUTPUT_FILE.name)
    def test_register_contract(self):
        self._profile(self.user)
        self._register_contract(self.user)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_COURSE_ID], unicode(course.id))
            self.assertEquals(score_dict[SCORE_STORE_FIELD_NAME], self.user.profile.name)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_STUDENT_STATUS], SCORE_STORE_FIELD_STUDENT_STATUS_ENROLLED)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CERTIFICATE_STATUS], SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE)
            self.assert_datetime(score_dict[SCORE_STORE_FIELD_ENROLL_DATE], CourseEnrollment.get_enrollment(self.user, course.id).created)
            self.assert_datetime(score_dict[SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE], GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_TOTAL_SCORE], 0)
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME1], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE))
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME2], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE))
            for k, v in score_dict.items():
                if k not in DEFAULT_KEY:
                    self.assertEquals(v, 0)

        assert_score(self.course1)
        assert_score(self.course2)

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=COMMAND_OUTPUT_FILE.name)
    def test_register_contract_rate(self):
        self._profile(self.user)
        self._register_contract(self.user)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)

        get_grade_return_value = {
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
        with patch('biz.djangoapps.ga_achievement.management.commands.update_biz_score_status.get_grade', return_value=get_grade_return_value):
            call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_COURSE_ID], unicode(course.id))
            self.assertEquals(score_dict[SCORE_STORE_FIELD_NAME], self.user.profile.name)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_STUDENT_STATUS], SCORE_STORE_FIELD_STUDENT_STATUS_ENROLLED)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CERTIFICATE_STATUS], SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE)
            self.assert_datetime(score_dict[SCORE_STORE_FIELD_ENROLL_DATE], CourseEnrollment.get_enrollment(self.user, course.id).created)
            self.assert_datetime(score_dict[SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE], GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_TOTAL_SCORE], 88.89)
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

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=COMMAND_OUTPUT_FILE.name)
    def test_register_contract_unenroll(self):
        self._profile(self.user)
        self._register_contract(self.user)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)
        self._unenroll(self.user, self.course1)
        self._unenroll(self.user, self.course2)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_COURSE_ID], unicode(course.id))
            self.assertEquals(score_dict[SCORE_STORE_FIELD_NAME], self.user.profile.name)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_STUDENT_STATUS], SCORE_STORE_FIELD_STUDENT_STATUS_UNENROLLED)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CERTIFICATE_STATUS], SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE)
            self.assert_datetime(score_dict[SCORE_STORE_FIELD_ENROLL_DATE], CourseEnrollment.get_enrollment(self.user, course.id).created)
            self.assert_datetime(score_dict[SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE], GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_TOTAL_SCORE], 0)
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME1], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE))
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME2], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE))
            for k, v in score_dict.items():
                if k not in DEFAULT_KEY:
                    self.assertEquals(v, 0)

        assert_score(self.course1)
        assert_score(self.course2)

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=COMMAND_OUTPUT_FILE.name)
    def test_register_contract_account_disable(self):
        self._profile(self.user)
        self._register_contract(self.user)
        self._certificate(self.user, self.course1)
        self._certificate(self.user, self.course2)
        self._account_disable(self.user)

        call_command('update_biz_score_status')

        def assert_score(course):
            score_list = self.assert_finished(1, course)

            score_dict = score_list[0]
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CONTRACT_ID], self.contract.id)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_COURSE_ID], unicode(course.id))
            self.assertEquals(score_dict[SCORE_STORE_FIELD_NAME], self.user.profile.name)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_USERNAME], self.user.username)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_EMAIL], self.user.email)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_STUDENT_STATUS], SCORE_STORE_FIELD_STUDENT_STATUS_DISABLED)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_CERTIFICATE_STATUS], SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE)
            self.assert_datetime(score_dict[SCORE_STORE_FIELD_ENROLL_DATE], CourseEnrollment.get_enrollment(self.user, course.id).created)
            self.assert_datetime(score_dict[SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE], GeneratedCertificate.certificate_for_student(self.user, course.id).created_date)
            self.assertEquals(score_dict[SCORE_STORE_FIELD_TOTAL_SCORE], 0)
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME1], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME1, ADDITIONAL_SETTINGS_VALUE))
            self.assertEquals(score_dict[ADDITIONAL_DISPLAY_NAME2], '{}_{}'.format(ADDITIONAL_DISPLAY_NAME2, ADDITIONAL_SETTINGS_VALUE))
            for k, v in score_dict.items():
                if k not in DEFAULT_KEY:
                    self.assertEquals(v, 0)

        assert_score(self.course1)
        assert_score(self.course2)

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=COMMAND_OUTPUT_FILE.name)
    def test_input_and_register(self):
        for var in range(0, 50):
            user = UserFactory.create()
            self._input_contract(user)
        for var in range(0, 50):
            user = UserFactory.create()
            self._register_contract(user)

        call_command('update_biz_score_status')

        self.assert_finished(100, self.course1)
        self.assert_finished(100, self.course2)

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=COMMAND_OUTPUT_FILE.name)
    def test_update_biz_score_status_error(self):
        with patch('biz.djangoapps.ga_achievement.models.ScoreBatchStatus.save_for_finished', side_effect=Exception()):
            call_command('update_biz_score_status')

        self.assert_error(self.course1)
        self.assert_error(self.course2)

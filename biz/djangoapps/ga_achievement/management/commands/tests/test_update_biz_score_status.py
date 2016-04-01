"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from mock import patch
import tempfile

from django.test.utils import override_settings
from django.core.management import call_command

from biz.djangoapps.ga_achievement.models import ScoreBatchStatus, SCORE_BATCH_STATUS_ERROR
from biz.djangoapps.ga_achievement.score_store import (
    ScoreStore, SCORE_STORE_FIELD_CONTRACT_ID, SCORE_STORE_FIELD_COURSE_ID,
    SCORE_STORE_FIELD_NAME, SCORE_STORE_FIELD_USERNAME, SCORE_STORE_FIELD_EMAIL, SCORE_STORE_FIELD_STUDENT_STATUS,
    SCORE_STORE_FIELD_STUDENT_STATUS_NOT_ENROLLED, SCORE_STORE_FIELD_STUDENT_STATUS_ENROLLED,
    SCORE_STORE_FIELD_STUDENT_STATUS_UNENROLLED, SCORE_STORE_FIELD_STUDENT_STATUS_DISABLED,
    SCORE_STORE_FIELD_CERTIFICATE_STATUS, SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE,
    SCORE_STORE_FIELD_CERTIFICATE_STATUS_UNPUBLISHED, SCORE_STORE_FIELD_ENROLL_DATE,
    SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE
)
from biz.djangoapps.ga_contract.tests.factories import ContractFactory, ContractDetailFactory, AdditionalInfoFactory
from biz.djangoapps.ga_invitation.tests.factories import AdditionalInfoSettingFactory, ContractRegisterFactory
from biz.djangoapps.ga_invitation.models import INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from certificates.models import CertificateStatuses
from certificates.tests.factories import GeneratedCertificateFactory
from courseware.tests.helpers import LoginEnrollmentTestCase
from lms.djangoapps.courseware.courses import get_course_by_id
from student.models import UserStanding
from student.tests.factories import CourseEnrollmentFactory, UserProfileFactory, UserStandingFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


class UpdateBizScoreStatusTest(BizStoreTestBase, ModuleStoreTestCase, LoginEnrollmentTestCase):

    def _create_contract(self, name, contractor, owner, created_by, invitation_code):
        return ContractFactory.create(contract_name=name, contractor_organization=contractor, owner_organization=owner,
                                      created_by=created_by, invitation_code=invitation_code)

    def _create_course(self):
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')

    def _create_contract_register(self, user, contract, status=REGISTER_INVITATION_CODE):
        ContractRegisterFactory.create(user=user, contract=contract, status=status)

    def _create_additional_info(self, user, contract):
        for additional_info in contract.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=user,
                contract=contract,
                display_name=additional_info.display_name,
            )

    def _create_course_enrollment(self, user, contract):
        for detail in contract.details.all():
            try:
                course = get_course_by_id(detail.course_id)
                CourseEnrollmentFactory.create(user=user, course_id=course.id)
            except:
                pass

    def _create_inactive_course_enrollment(self, user, contract):
        for detail in contract.details.all():
            try:
                course = get_course_by_id(detail.course_id)
                CourseEnrollmentFactory.create(user=user, course_id=course.id, is_active=False)
            except:
                pass

    def _create_contract_detail(self, contract, course_id):
        return ContractDetailFactory.create(course_id=course_id, contract=contract)

    def _create_user(self):
        self.setup_user()

    def _create_org_data(self):
        self.org_a = self._create_organization(org_name='a', org_code='a', creator_org=self.gacco_organization)

    def set_normal(self):
        self._create_user()
        self.user_standing = UserStandingFactory.create(
            user=self.user,
            account_status=UserStanding.ACCOUNT_ENABLED,
            changed_by=self.user
        )
        self._create_course()
        self.user_profile = UserProfileFactory(user=self.user)
        self._create_org_data()
        self.contract = self._create_contract('contract_a', self.org_a, self.gacco_organization,
                                              self.user, 'invitation_code_a')
        self._create_contract_detail(self.contract, self.course.id)
        self._create_contract_register(self.user, self.contract)
        self._create_additional_info(self.user, self.contract)
        self._create_course_enrollment(self.user, self.contract)
        for additional_info in self.contract.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=self.user,
                contract=self.contract,
                display_name=additional_info.display_name,
            )
        certificate_url = "http://test_certificate_url"
        self.genrated_certificate = GeneratedCertificateFactory.create(
            user=self.user,
            course_id=self.course.id,
            status=CertificateStatuses.downloadable,
            mode='verified',
            download_url=certificate_url,
        )

    def set_user_standing_account_disabled(self):
        self._create_user()
        self.user_standing = UserStandingFactory.create(
            user=self.user,
            account_status=UserStanding.ACCOUNT_DISABLED,
            changed_by=self.user
        )
        self._create_course()
        self.user_profile = UserProfileFactory(user=self.user)
        self._create_org_data()
        self.contract = self._create_contract('contract_a', self.org_a, self.gacco_organization,
                                              self.user, 'invitation_code_a')
        self._create_contract_detail(self.contract, self.course.id)
        self._create_contract_register(self.user, self.contract, INPUT_INVITATION_CODE)
        self._create_additional_info(self.user, self.contract)
        self._create_course_enrollment(self.user, self.contract)
        for additional_info in self.contract.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=self.user,
                contract=self.contract,
                display_name=additional_info.display_name
            )
        certificate_url = "http://test_certificate_url"
        self.genrated_certificate = GeneratedCertificateFactory.create(
            user=self.user,
            course_id=self.course.id,
            status=CertificateStatuses.downloadable,
            mode='verified',
            download_url=certificate_url,
        )

    def tearDown(self):
        pass

    command_output_file = tempfile.NamedTemporaryFile()

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=command_output_file.name)
    def test_update_biz_score_status(self):
        self.set_normal()

        call_command('update_biz_score_status')
        score_store = ScoreStore(self.contract.id, unicode(self.course.id))
        score_list = score_store.get_documents()

        check_list = [
            SCORE_STORE_FIELD_CONTRACT_ID, SCORE_STORE_FIELD_COURSE_ID,
            SCORE_STORE_FIELD_NAME, SCORE_STORE_FIELD_USERNAME, SCORE_STORE_FIELD_EMAIL,
            SCORE_STORE_FIELD_STUDENT_STATUS, SCORE_STORE_FIELD_STUDENT_STATUS_NOT_ENROLLED,
            SCORE_STORE_FIELD_STUDENT_STATUS_ENROLLED, SCORE_STORE_FIELD_STUDENT_STATUS_UNENROLLED,
            SCORE_STORE_FIELD_STUDENT_STATUS_DISABLED, SCORE_STORE_FIELD_CERTIFICATE_STATUS,
            SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE, SCORE_STORE_FIELD_CERTIFICATE_STATUS_UNPUBLISHED,
            SCORE_STORE_FIELD_ENROLL_DATE, SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE
        ]

        for score_order_dict in score_list:
            for score in score_order_dict:
                self.assertIn(score, check_list)
                if score == SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE:
                    break

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=command_output_file.name)
    def test_user_standing_account_disabled_update_biz_score_status(self):
        self.set_user_standing_account_disabled()

        call_command('update_biz_score_status')
        score_store = ScoreStore(self.contract.id, unicode(self.course.id))
        score_list = score_store.get_documents()

        check_list = [
            SCORE_STORE_FIELD_CONTRACT_ID, SCORE_STORE_FIELD_COURSE_ID,
            SCORE_STORE_FIELD_NAME, SCORE_STORE_FIELD_USERNAME, SCORE_STORE_FIELD_EMAIL,
            SCORE_STORE_FIELD_STUDENT_STATUS, SCORE_STORE_FIELD_STUDENT_STATUS_NOT_ENROLLED,
            SCORE_STORE_FIELD_STUDENT_STATUS_ENROLLED, SCORE_STORE_FIELD_STUDENT_STATUS_UNENROLLED,
            SCORE_STORE_FIELD_STUDENT_STATUS_DISABLED, SCORE_STORE_FIELD_CERTIFICATE_STATUS,
            SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE, SCORE_STORE_FIELD_CERTIFICATE_STATUS_UNPUBLISHED,
            SCORE_STORE_FIELD_ENROLL_DATE, SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE
        ]

        for score_order_dict in score_list:
            for score in score_order_dict:
                self.assertIn(score, check_list)
                if score == SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE:
                    break

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=command_output_file.name)
    def test_none_contract_register_update_biz_score_status(self):
        self.user_standing = None
        self.user_profile = None
        self._create_course()
        self._create_org_data()
        self.contract = self._create_contract('contract_a', self.org_a, self.gacco_organization,
                                              self.user, 'invitation_code_a')
        self._create_contract_detail(self.contract, self.course.id)
        self._create_contract_register(self.user, self.contract)

        for additional_info in self.contract.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=self.user,
                contract=self.contract,
                display_name=additional_info.display_name
            )
        certificate_url = "http://test_certificate_url"
        self.genrated_certificate = GeneratedCertificateFactory.create(
            user=self.user,
            course_id=self.course.id,
            status=CertificateStatuses.downloadable,
            mode='verified',
            download_url=certificate_url,
        )

        call_command('update_biz_score_status')
        score_store = ScoreStore(self.contract.id, unicode(self.course.id))
        score_list = score_store.get_documents()

        for score_order_dict in score_list:
            self.assertEqual(SCORE_STORE_FIELD_STUDENT_STATUS_NOT_ENROLLED,
                             score_order_dict[SCORE_STORE_FIELD_STUDENT_STATUS])
            break

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=command_output_file.name)
    def test_none_user_standing_and_none_user_profile_update_biz_score_status(self):
        self.user_standing = None
        self.user_profile = None
        self._create_course()
        self._create_org_data()
        self.contract = self._create_contract('contract_a', self.org_a, self.gacco_organization,
                                              self.user, 'invitation_code_a')
        self._create_contract_detail(self.contract, self.course.id)
        self._create_contract_register(self.user, self.contract)

        for additional_info in self.contract.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=self.user,
                contract=self.contract,
                display_name=additional_info.display_name
            )
        certificate_url = "http://test_certificate_url"
        self.genrated_certificate = GeneratedCertificateFactory.create(
            user=self.user,
            course_id=self.course.id,
            status=CertificateStatuses.downloadable,
            mode='verified',
            download_url=certificate_url,
        )

        call_command('update_biz_score_status')
        score_store = ScoreStore(self.contract.id, unicode(self.course.id))
        score_list = score_store.get_documents()

        for score_order_dict in score_list:
            self.assertIsNone(score_order_dict[SCORE_STORE_FIELD_NAME])
            break

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=command_output_file.name)
    def test_none_user_profile_and_user_standing_contract_disabled_update_biz_score_status(self):
        self._create_user()
        self.user_profile = None
        self._create_course()
        self._create_org_data()
        self.contract = self._create_contract('contract_a', self.org_a, self.gacco_organization,
                                              self.user, 'invitation_code_a')
        self._create_contract_detail(self.contract, self.course.id)
        self._create_contract_register(self.user, self.contract)

        for additional_info in self.contract.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=self.user,
                contract=self.contract,
                display_name=additional_info.display_name,
                value='test'
            )
        certificate_url = "http://test_certificate_url"
        self.genrated_certificate = GeneratedCertificateFactory.create(
            user=self.user,
            course_id=self.course.id,
            status=CertificateStatuses.generating,
            mode='verified',
            download_url=certificate_url,
        )
        self.user_standing = UserStandingFactory.create(
            user=self.user,
            account_status=UserStanding.ACCOUNT_DISABLED,
            changed_by=self.user
        )

        call_command('update_biz_score_status')
        score_store = ScoreStore(self.contract.id, unicode(self.course.id))
        score_list = score_store.get_documents()

        for score_order_dict in score_list:
            self.assertEqual(SCORE_STORE_FIELD_STUDENT_STATUS_DISABLED,
                             score_order_dict[SCORE_STORE_FIELD_STUDENT_STATUS])
            break

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=command_output_file.name)
    def test_none_user_profile_and_user_standing_account_enable_in_display_name_update_biz_score_status(self):
        self._create_user()
        self.user_profile = None
        self._create_course()
        self._create_org_data()
        self.contract = self._create_contract('contract_a', self.org_a, self.gacco_organization,
                                              self.user, 'invitation_code_a')
        self._create_contract_detail(self.contract, self.course.id)
        self._create_contract_register(self.user, self.contract)

        AdditionalInfoFactory.create(contract=self.contract, display_name='test_display')

        AdditionalInfoSettingFactory.create(
            user=self.user,
            contract=self.contract,
            display_name='test_display',
            value='test_value'
        )

        certificate_url = "http://test_certificate_url"
        self.genrated_certificate = GeneratedCertificateFactory.create(
            user=self.user,
            course_id=self.course.id,
            status=CertificateStatuses.generating,
            mode='verified',
            download_url=certificate_url,
        )
        self.user_standing = UserStandingFactory.create(
            user=self.user,
            account_status=UserStanding.ACCOUNT_ENABLED,
            changed_by=self.user
        )
        self._create_inactive_course_enrollment(self.user, self.contract)

        call_command('update_biz_score_status')
        score_store = ScoreStore(self.contract.id, unicode(self.course.id))
        score_list = score_store.get_documents()

        for score_order_dict in score_list:
            self.assertEqual('test_value', score_order_dict['test_display'])
            self.assertEqual(SCORE_STORE_FIELD_STUDENT_STATUS_UNENROLLED,
                             score_order_dict[SCORE_STORE_FIELD_STUDENT_STATUS])
            break

    @override_settings(BIZ_SET_SCORE_COMMAND_OUTPUT=command_output_file.name)
    def test_update_biz_score_status_error(self):
        self.set_normal()
        contract_id = self.contract.id
        course_id = self.course.id

        with patch('courseware.grades.grade') as mock_grade:
            mock_grade.side_effect = TypeError()
            call_command('update_biz_score_status')
            score_batch_status = ScoreBatchStatus.get_last_status(contract_id, course_id)

            self.assertEqual(SCORE_BATCH_STATUS_ERROR, score_batch_status.status)
            self.assertEqual(contract_id, score_batch_status.contract_id)
            self.assertEqual(course_id, score_batch_status.course_id)

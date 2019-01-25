"""
Tests for mask utilities
"""
import ddt
from mock import patch

from biz.djangoapps.util import mask_utils
from biz.djangoapps.util.tests.testcase import BizTestBase
from certificates.models import CertificateStatuses
from certificates.tests.factories import GeneratedCertificateFactory
from student.tests.factories import UserFactory, CourseEnrollmentFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting
from biz.djangoapps.ga_invitation.tests.factories import AdditionalInfoSettingFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase

from ga_shoppingcart.models import PersonalInfo
from ga_shoppingcart.tests.factories import PersonalInfoFactory, PersonalInfoSettingFactory
from ga_shoppingcart.tests.utils import get_order_from_advanced_course

@ddt.ddt
class MaskUtilsTest(BizContractTestBase, ModuleStoreTestCase):
    """Test for mask utilities"""

    def setUp(self):
        super(MaskUtilsTest, self).setUp()

        self.course = CourseFactory.create(org='org', course='course1', run='run')

    @patch('biz.djangoapps.util.mask_utils.CertificatePDF.delete')
    @ddt.data(
        CertificateStatuses.unavailable,
        CertificateStatuses.regenerating,
        CertificateStatuses.deleting,
        CertificateStatuses.deleted,
        CertificateStatuses.notpassing,
        CertificateStatuses.restricted,
    )
    def test_delete_certificates_success(self, status, mock_delete):
        self.user = UserFactory.create()
        self.certificate = GeneratedCertificateFactory.create(
            status=status,
            key='key',
            user=self.user,
            course_id=self.course.id)
        CourseEnrollmentFactory.create(course_id=self.course.id, user=self.user)
        mask_utils.delete_certificates(self.user)

        self.assertEqual(self.certificate.status, status)

    @patch('biz.djangoapps.util.mask_utils.log.error')
    @patch('biz.djangoapps.util.mask_utils.CertificatePDF.delete')
    @ddt.data(
        CertificateStatuses.generating,
        CertificateStatuses.downloadable,
    )
    def test_delete_certificates_error(self, status, mock_delete, mock_log_error):
        self.user = UserFactory.create()
        error_message = 'Failed to delete certificates of User {user_id}.'.format(user_id=self.user.id)
        self.certificate = GeneratedCertificateFactory.create(
            status=status,
            key='key',
            user=self.user,
            course_id=self.course.id)
        CourseEnrollmentFactory.create(course_id=self.course.id, user=self.user)

        with self.assertRaises(Exception) as e:
            mask_utils.delete_certificates(self.user)
        self.assertEqual(e.exception.message, error_message)
        mock_log_error.assert_called_once_with('Failed to delete certificate. user={user_id}, course_id={course_id}'.format(user_id=self.user.id, course_id=self.course.id))

    def test_disable_all_additional_info(self):
        user = UserFactory.create()

        for additional_info in self.contract.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=user,
                contract=self.contract,
                display_name=additional_info.display_name,
                value='value_of_{}_{}'.format(additional_info.display_name, self.contract.id)
            )
        for additional_info in self.contract_mooc.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=user,
                contract=self.contract_mooc,
                display_name=additional_info.display_name,
                value='value_of_{}_{}'.format(additional_info.display_name, self.contract_mooc.id)
            )

        for additional_setting in AdditionalInfoSetting.find_by_user_and_contract(user, self.contract):
            self.assertEqual(additional_setting.value,
                             'value_of_{}_{}'.format(additional_setting.display_name, self.contract.id))
        for additional_setting in AdditionalInfoSetting.find_by_user_and_contract(user, self.contract_mooc):
            self.assertEqual(additional_setting.value,
                             'value_of_{}_{}'.format(additional_setting.display_name, self.contract_mooc.id))

        mask_utils.disable_all_additional_info(user)

        for additional_setting in AdditionalInfoSetting.find_by_user_and_contract(user, self.contract):
            self.assertEqual(
                additional_setting.value,
                mask_utils.hash('value_of_{}_{}'.format(additional_setting.display_name, self.contract.id)))
        for additional_setting in AdditionalInfoSetting.find_by_user_and_contract(user, self.contract_mooc):
            self.assertEqual(
                additional_setting.value,
                mask_utils.hash('value_of_{}_{}'.format(additional_setting.display_name, self.contract_mooc.id)))

    def test_mask_shoppingcart_personalinfo(self):
        user = UserFactory.create()

        course_for_advanced = CourseFactory.create(
            metadata={
                'is_f2f_course': True,
                'is_f2f_course_sell': True,
            }
        )
        order, advanced_course = get_order_from_advanced_course(course_for_advanced, user)
        personal_info_setting = PersonalInfoSettingFactory.create(**dict(
            advanced_course=advanced_course,
            free_entry_field_1_title='aaa',
            free_entry_field_2_title='bbb',
            free_entry_field_3_title='ccc',
            free_entry_field_4_title='ddd',
            free_entry_field_5_title='eee'
        ))
        personal_info = PersonalInfoFactory.create(**dict(
                user=user,
                full_name='name',
                kana='kana',
                postal_code='1111111',
                address_line_1='address1',
                address_line_2='address2',
                phone_number='09000000000',
                free_entry_field_1='free1',
                free_entry_field_2='free2',
                free_entry_field_3='free3',
                free_entry_field_4='free4',
                free_entry_field_5='free5',
                order_id=order.id,
                choice=personal_info_setting
        ))

        mask_utils.mask_shoppingcart_personalinfo(user)

        for pis in PersonalInfo.objects.filter(user=user):
            self.assertEqual(pis.full_name, mask_utils.hash(personal_info.full_name))
            self.assertEqual(pis.kana, mask_utils.hash(personal_info.kana))
            self.assertEqual(pis.postal_code, None)
            self.assertEqual(pis.address_line_1, mask_utils.hash(personal_info.address_line_1))
            self.assertEqual(pis.address_line_2, mask_utils.hash(personal_info.address_line_2))
            self.assertEqual(pis.phone_number, None)
            self.assertEqual(pis.free_entry_field_1, mask_utils.hash(personal_info.free_entry_field_1))
            self.assertEqual(pis.free_entry_field_2, mask_utils.hash(personal_info.free_entry_field_2))
            self.assertEqual(pis.free_entry_field_3, mask_utils.hash(personal_info.free_entry_field_3))
            self.assertEqual(pis.free_entry_field_4, mask_utils.hash(personal_info.free_entry_field_4))
            self.assertEqual(pis.free_entry_field_5, mask_utils.hash(personal_info.free_entry_field_5))

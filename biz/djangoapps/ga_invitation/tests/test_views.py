from datetime import timedelta
import json
from mock import patch

from django.core.urlresolvers import reverse
from django.test import TestCase, RequestFactory
from django.utils.crypto import get_random_string
from django.test.utils import override_settings

from opaque_keys.edx.keys import CourseKey

from student.models import CourseEnrollment, CourseEnrollmentException
from student.tests.factories import UserFactory, CourseEnrollmentFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from lms.djangoapps.courseware.courses import get_course_by_id

from biz.djangoapps.ga_contract.models import CONTRACT_TYPE_GACCO_SERVICE, REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT
from biz.djangoapps.ga_invitation.models import (
    AdditionalInfoSetting, ContractRegister,
    INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE)
from biz.djangoapps.ga_invitation.tests.factories import AdditionalInfoSettingFactory, ContractRegisterFactory
from biz.djangoapps.ga_invitation.views import ADDITIONAL_NAME
from biz.djangoapps.util.datetime_utils import timezone_today
from biz.djangoapps.util.tests.testcase import BizTestBase, BizViewTestBase


class BizContractTestBase(BizViewTestBase, ModuleStoreTestCase):

    def setUp(self):
        super(BizContractTestBase, self).setUp()

        self.contract_org = self._create_organization(org_code='contractor')
        self.contract_org_other = self._create_organization(org_code='contractor_other')
        self.no_contract_org = self._create_organization(org_code='no_contractor')

        self.course_spoc1 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc1', run='run1')
        self.course_spoc2 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc2', run='run2')
        self.course_spoc3 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc3', run='run3')
        self.course_spoc4 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc4', run='run4')
        self.course_spoc5 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc5', run='run5')
        self.course_spoc6 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc6', run='run6')
        self.course_spoc7 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc7', run='run7')
        self.course_spoc8 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc8', run='run8')
        self.course_mooc1 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='mooc1', run='run5')
        self.no_contract_course = CourseFactory.create(
            org=self.gacco_organization.org_code, number='gene1', run='run6')

        self.no_course_id = CourseKey.from_string(unicode(self.course_spoc1.id).replace('run1', 'run0'))

        self.contract = self._create_contract(
            contractor_organization=self.contract_org,
            detail_courses=[self.course_spoc1.id, self.course_spoc2.id],
            additional_display_names=['country', 'dept'])
        self.contract_disabled = self._create_contract(
            contract_name='test contract disabled',
            contractor_organization=self.contract_org_other,
            end_date=(timezone_today() - timedelta(days=1)),
            detail_courses=[self.course_spoc3.id, self.course_spoc4.id],
            additional_display_names=['country', 'dept'])
        self.contract_nodetail = self._create_contract(
            contract_name='test contract nodetail',
            contractor_organization=self.contract_org,
            additional_display_names=['country', 'dept'])
        self.contract_nocourse = self._create_contract(
            contract_name='test contract nocourse',
            contractor_organization=self.contract_org,
            detail_courses=[self.no_course_id],
            additional_display_names=['country', 'dept'])
        self.contract_mooc = self._create_contract(
            contract_name='test contract mooc',
            contract_type=CONTRACT_TYPE_GACCO_SERVICE[0],
            contractor_organization=self.contract_org,
            detail_courses=[self.course_mooc1.id],
            additional_display_names=['country', 'dept'])
        self.contract_auth = self._create_contract(
            contract_name='test contract auth',
            contractor_organization=self.contract_org,
            detail_courses=[self.course_spoc5.id],
            url_code='testAuth')
        self.contract_auth_disabled = self._create_contract(
            contract_name='test contract auth disabled',
            contractor_organization=self.contract_org,
            end_date=(timezone_today() - timedelta(days=1)),
            detail_courses=[self.course_spoc6.id],
            url_code='testAuthDisabled')
        self.contract_student_cannot_register = self._create_contract(
            register_type=REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT[0],
            contract_name='test contract student cannot register',
            contractor_organization=self.contract_org,
            detail_courses=[self.course_spoc7.id],
            additional_display_names=['country', 'dept'])
        self.contract_auth_student_cannot_register = self._create_contract(
            register_type=REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT[0],
            contract_name='test contract auth student cannot register',
            contractor_organization=self.contract_org,
            detail_courses=[self.course_spoc8.id],
            additional_display_names=['country', 'dept'],
            url_code='testAuthRegisterDirector')

    def create_contract_register(self, user, contract, status=REGISTER_INVITATION_CODE):
        register = ContractRegisterFactory.create(user=user, contract=contract, status=status)
        for additional_info in contract.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=user,
                contract=contract,
                display_name=additional_info.display_name
            )
        for detail in contract.details.all():
            try:
                course = get_course_by_id(detail.course_id)
                CourseEnrollmentFactory.create(user=user, course_id=course.id)
            except:
                pass
        return register


class InvitationViewsTest(BizContractTestBase):

    def _url_index(self):
        return reverse('biz:invitation:index')

    def _url_verify(self):
        return reverse('biz:invitation:verify')

    def _url_confirm(self, invitation_code):
        return reverse('biz:invitation:confirm', kwargs={'invitation_code': invitation_code})

    def _url_register(self):
        return reverse('biz:invitation:register')


class InvitationViewsIndexTest(InvitationViewsTest):

    def test_contract_register(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract)
        self.create_contract_register(self.user, self.contract_disabled)
        response = self.assert_request_status_code(200, self._url_index())
        self.assertIn(self.contract.contract_name, response.content)
        self.assertNotIn(self.contract_disabled.contract_name, response.content)

    def test_no_contract_register(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_index())
        self.assertNotIn(self.contract.contract_name, response.content)
        self.assertNotIn(self.contract_disabled.contract_name, response.content)

    def test_no_login(self):
        response = self.assert_request_status_code(302, self._url_index())

    def test_post_method(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract)
        response = self.assert_request_status_code(405, self._url_index(), 'POST')


class InvitationViewsVerifyTest(InvitationViewsTest):

    def test_no_param(self):
        self.setup_user()
        response = self.assert_request_status_code(400, self._url_verify(), 'POST')

    def test_no_input(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': ''})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertEqual(content['message'], 'Invitation code is required.')

    def test_not_found(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': 'hoge'})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertEqual(content['message'], 'Invitation code is invalid.')

    def test_disabled(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': self.contract_disabled.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertEqual(content['message'], 'Invitation code is invalid.')

    def test_auth_no_register(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': self.contract_auth.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertEqual(content['message'], 'Invitation code is invalid.')

    def test_student_cannot_register_no_register(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': self.contract_student_cannot_register.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertEqual(content['message'], 'Invitation code is invalid.')

    def test_student_cannot_register_yes_register_input(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract_student_cannot_register, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': self.contract_student_cannot_register.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertEqual(content['message'], 'Please ask your administrator to register the invitation code.')

    def test_student_cannot_register_yes_register_register(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract_student_cannot_register, REGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': self.contract_student_cannot_register.invitation_code})
        content = json.loads(response.content)
        self.assertTrue(content['result'])
        self.assertEqual(content['href'], self._url_confirm(self.contract_student_cannot_register.invitation_code))

    def test_student_cannot_register_yes_register_unregister(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract_student_cannot_register, UNREGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': self.contract_student_cannot_register.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertEqual(content['message'], 'Invitation code is invalid.')

    def test_no_detail(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': self.contract_nodetail.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertEqual(content['message'], 'Invitation code is invalid.')

    def test_no_course(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': self.contract_nocourse.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertEqual(content['message'], 'Invitation code is invalid.')

    def test_no_login(self):
        response = self.assert_request_status_code(302, self._url_verify(), 'POST', data={'invitation_code': self.contract.invitation_code})

    def test_success(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_verify(), 'POST', data={'invitation_code': self.contract.invitation_code})
        content = json.loads(response.content)
        self.assertTrue(content['result'])
        self.assertEqual(content['href'], self._url_confirm(self.contract.invitation_code))

    def test_get_method(self):
        self.setup_user()
        response = self.assert_request_status_code(405, self._url_verify(), data={'invitation_code': self.contract.invitation_code})


class InvitationViewsConfirmTest(InvitationViewsTest):

    def test_not_found(self):
        self.setup_user()
        response = self.assert_request_status_code(404, self._url_confirm('hoge'))

    def test_disabled(self):
        self.setup_user()
        response = self.assert_request_status_code(404, self._url_confirm(self.contract_disabled.invitation_code))
        with self.assertRaises(ContractRegister.DoesNotExist):
            ContractRegister.objects.get(user=self.user)

    def test_auth_no_register(self):
        self.setup_user()
        response = self.assert_request_status_code(404, self._url_confirm(self.contract_auth.invitation_code))
        with self.assertRaises(ContractRegister.DoesNotExist):
            ContractRegister.objects.get(user=self.user)

    def test_student_cannot_register_no_register(self):
        self.setup_user()
        response = self.assert_request_status_code(404, self._url_confirm(self.contract_student_cannot_register.invitation_code))
        with self.assertRaises(ContractRegister.DoesNotExist):
            ContractRegister.objects.get(user=self.user)

    def test_student_cannot_register_yes_register_input(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract_student_cannot_register, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(404, self._url_confirm(self.contract_student_cannot_register.invitation_code))
        self.assertEqual(ContractRegister.objects.get(user=self.user).status, INPUT_INVITATION_CODE)

    def test_student_cannot_register_yes_register_register(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract_student_cannot_register, REGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(200, self._url_confirm(self.contract_student_cannot_register.invitation_code))
        self.assertEqual(ContractRegister.objects.get(user=self.user).status, REGISTER_INVITATION_CODE)

    def test_student_cannot_register_yes_register_unregister(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract_student_cannot_register, UNREGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(404, self._url_confirm(self.contract_student_cannot_register.invitation_code))
        self.assertEqual(ContractRegister.objects.get(user=self.user).status, UNREGISTER_INVITATION_CODE)

    def test_no_detail(self):
        self.setup_user()
        response = self.assert_request_status_code(404, self._url_confirm(self.contract_nodetail.invitation_code))
        with self.assertRaises(ContractRegister.DoesNotExist):
            ContractRegister.objects.get(user=self.user)

    def test_no_course(self):
        self.setup_user()
        response = self.assert_request_status_code(404, self._url_confirm(self.contract_nocourse.invitation_code))
        with self.assertRaises(ContractRegister.DoesNotExist):
            ContractRegister.objects.get(user=self.user)

    def test_no_login(self):
        response = self.assert_request_status_code(302, self._url_confirm(self.contract.invitation_code))

    def test_success(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        self.assertEqual(ContractRegister.objects.get(user=self.user).status, INPUT_INVITATION_CODE)
        # re-confirm
        response = self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        self.assertEqual(ContractRegister.objects.get(user=self.user).status, INPUT_INVITATION_CODE)

    def test_post_method(self):
        self.setup_user()
        response = self.assert_request_status_code(405, self._url_confirm(self.contract.invitation_code), 'POST')
        with self.assertRaises(ContractRegister.DoesNotExist):
            ContractRegister.objects.get(user=self.user)

    @override_settings(DOMAIN_CONTROL_ACCESS=[{'invitation18': ['@test.com']}])
    def test_domain_control_access_pass(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        self.assertEqual(ContractRegister.objects.get(user=self.user).status, INPUT_INVITATION_CODE)

    @override_settings(DOMAIN_CONTROL_ACCESS=[{'invitation18': '@tester.com'}])
    def test_domain_control_access_not_pass(self):
        self.setup_user()
        response = self.assert_request_status_code(403, self._url_confirm(self.contract.invitation_code))

    @override_settings(DOMAIN_CONTROL_ACCESS=[{'invitation44': '@test.com'}])
    def test_domain_control_access_register_type_not_pass(self):
        self.setup_user()
        response = self.assert_request_status_code(404, self._url_confirm(self.contract_auth_student_cannot_register.invitation_code))

    @override_settings(DOMAIN_CONTROL_ACCESS=[{'invitation44': '@tester.com'}])
    def test_domain_control_access_register_type_not_pass_2(self):
        self.setup_user()
        response = self.assert_request_status_code(404, self._url_confirm(
            self.contract_auth_student_cannot_register.invitation_code))


class InvitationViewsRegisterTest(InvitationViewsTest):

    def test_no_param(self):
        self.setup_user()
        response = self.assert_request_status_code(400, self._url_register(), 'POST')

    def test_no_input(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data={'invitation_code': ''})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_index(), content['message'])

    def test_not_found(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data={'invitation_code': 'hoge'})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_index(), content['message'])

    def test_disabled(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data={'invitation_code': self.contract_disabled.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_index(), content['message'])

    def test_auth_no_register(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data={'invitation_code': self.contract_auth.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_index(), content['message'])

    def test_student_cannot_register_no_register(self):
        self.setup_user()
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data={'invitation_code': self.contract_student_cannot_register.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_index(), content['message'])

    def test_student_cannot_register_yes_register_input(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract_student_cannot_register, INPUT_INVITATION_CODE)
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data={'invitation_code': self.contract_student_cannot_register.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_index(), content['message'])

    def test_student_cannot_register_yes_register_register(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract_student_cannot_register, REGISTER_INVITATION_CODE)
        data={'invitation_code': self.contract_student_cannot_register.invitation_code}
        for a in self.contract_student_cannot_register.additional_info.all():
            data[ADDITIONAL_NAME.format(additional_id=a.id)] = 'input_value'
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data=data)
        content = json.loads(response.content)
        self.assertTrue(content['result'])
        self.assertEqual(content['href'], reverse('dashboard'))
        self.assertEqual(ContractRegister.objects.get(user=self.user).status, REGISTER_INVITATION_CODE)
        for a in self.contract_student_cannot_register.additional_info.all():
            self.assertEqual('input_value', AdditionalInfoSetting.get_value(self.user, self.contract_student_cannot_register, a))

    def test_student_cannot_register_yes_register_unregister(self):
        self.setup_user()
        self.create_contract_register(self.user, self.contract_student_cannot_register, UNREGISTER_INVITATION_CODE)
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data={'invitation_code': self.contract_student_cannot_register.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_index(), content['message'])

    def test_no_detail(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data={'invitation_code': self.contract_nodetail.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_index(), content['message'])

    def test_no_course(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data={'invitation_code': self.contract_nocourse.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_index(), content['message'])

    def test_no_login(self):
        response = self.assert_request_status_code(302, self._url_register(), 'POST', data={'invitation_code': self.contract.invitation_code})

    def test_not_param_additional(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data={'invitation_code': self.contract.invitation_code})
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_confirm(self.contract.invitation_code), content['message'])

    def test_no_input_additional(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        data = {'invitation_code': self.contract.invitation_code}
        assert_messages = []
        for a in self.contract.additional_info.all():
            data[ADDITIONAL_NAME.format(additional_id=a.id)] = ''
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data=data)
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertEqual(content['message'], '')
        self.assertEqual(
            [e['name'] for e in content['additional_errors']],
            [ADDITIONAL_NAME.format(additional_id=a.id) for a in self.contract.additional_info.all()])
        self.assertEqual(
            [e['message'] for e in content['additional_errors']],
            ['{display_name} is required.'.format(display_name=a.display_name) for a in self.contract.additional_info.all()])

    def test_success(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        data = {'invitation_code': self.contract.invitation_code}
        for a in self.contract.additional_info.all():
            data[ADDITIONAL_NAME.format(additional_id=a.id)] = 'input_value'
        response = self.assert_request_status_code(200, self._url_register(), 'POST', data=data)
        content = json.loads(response.content)
        self.assertTrue(content['result'])
        self.assertEqual(content['href'], reverse('dashboard'))
        self.assertEqual(ContractRegister.objects.get(user=self.user).status, REGISTER_INVITATION_CODE)
        for a in self.contract.additional_info.all():
            self.assertEqual('input_value', AdditionalInfoSetting.get_value(self.user, self.contract, a))

    def test_get_method(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        response = self.assert_request_status_code(405, self._url_register(), data={'invitation_code': self.contract.invitation_code})

    def test_error(self):
        self.setup_user()
        self.assert_request_status_code(200, self._url_confirm(self.contract.invitation_code))
        data = {'invitation_code': self.contract.invitation_code}
        for a in self.contract.additional_info.all():
            data[ADDITIONAL_NAME.format(additional_id=a.id)] = 'input_value'
        with patch('student.models.CourseEnrollment.enroll', side_effect=CourseEnrollmentException()):
            response = self.assert_request_status_code(200, self._url_register(), 'POST', data=data)
        content = json.loads(response.content)
        self.assertFalse(content['result'])
        self.assertIn(self._url_index(), content['message'])
        self.assertIn('Failed to register the invitation code.', content['message'])

"""
Test for contract feature
"""
from datetime import date, timedelta

from biz.djangoapps.ga_invitation.models import REGISTER_INVITATION_CODE

from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory

from biz.djangoapps.ga_contract.models import Contract, ContractDetail, AdditionalInfo, CONTRACT_TYPE_GACCO_SERVICE, REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT, REGISTER_TYPE_ENABLE_REGISTER_BY_STUDENT
from biz.djangoapps.ga_contract.tests.factories import ContractFactory, ContractDetailFactory, AdditionalInfoFactory
from biz.djangoapps.util.tests.testcase import BizViewTestBase
from django.core.urlresolvers import reverse
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


class ContractViewTest(BizViewTestBase, ModuleStoreTestCase):
    def _index_view(self):
        return reverse('biz:contract:index')

    def _show_register_view(self):
        return reverse('biz:contract:show_register')

    def _register_view(self):
        return reverse('biz:contract:register')

    def _detail_view(self, selected_contract_id):
        return reverse('biz:contract:detail', kwargs={'selected_contract_id': selected_contract_id})

    def _edit_view(self, selected_contract_id):
        return reverse('biz:contract:edit', kwargs={'selected_contract_id': selected_contract_id})

    def _create_contract(self, name, contractor, owner, created_by, invitation_code):
        return ContractFactory.create(contract_name=name, contractor_organization=contractor, owner_organization=owner,
                                      created_by=created_by, invitation_code=invitation_code)

    def _create_contract_detail(self, contract, course_id):
        return ContractDetailFactory.create(course_id=course_id, contract=contract)

    def _create_additional_info(self, contract, display_name):
        return AdditionalInfoFactory.create(display_name=display_name, contract=contract)

    def _setup_course_data(self):
        self.course_gacco1 = CourseFactory.create(org='gacco', number='course1', run='run1')
        self.course_gacco2 = CourseFactory.create(org='gacco', number='course2', run='run2')

        self.course_tac1 = CourseFactory.create(org='tac', number='course1', run='run1')
        self.course_tac2 = CourseFactory.create(org='tac', number='course2', run='run2')

    def _setup_org_data(self):
        self.org_tac = self._create_organization(org_name='tac', org_code='tac', creator_org=self.gacco_organization)
        self.org_a = self._create_organization(org_name='a', org_code='a', creator_org=self.gacco_organization)
        self.org_b = self._create_organization(org_name='b', org_code='b', creator_org=self.gacco_organization)
        self.org_e = self._create_organization(org_name='e', org_code='e', creator_org=self.org_tac)

    def _setup_contract_data(self):
        self.contract_tac = self._create_contract('contract_tac', self.org_tac, self.gacco_organization, self.user,
                                                  'invitationcodetac')
        self.contract_a = self._create_contract('contract_a', self.org_a, self.gacco_organization, self.user,
                                                'invitationcodea')
        self.contract_b = self._create_contract('contract_b', self.org_b, self.gacco_organization, self.user,
                                                'invitationcodeb')
        self.contract_e = self._create_contract('other_contract', self.org_e, self.org_tac, self.user,
                                                'invitationcodee')

        self._create_contract_detail(self.contract_b, 'gacco/course1/run1')
        self._create_contract_detail(self.contract_b, 'gacco/course2/run2')

        self._create_additional_info(self.contract_b, 'first name')
        self._create_additional_info(self.contract_b, 'last name')

    def test_index_for_aggregator(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()

        with self.skip_check_course_selection(current_organization=self.org_tac):
            response = self.client.get(self._index_view())

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract List', response.content)
        self.assertIn(self.contract_e.contract_name, response.content)
        for e in [self.contract_tac, self.contract_a, self.contract_b]:
            self.assertNotIn(e.contract_name, response.content)

    def test_index_for_platfomer(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()

        expected_contract = [
            self.contract_tac, self.contract_a, self.contract_b
        ]
        self.current_org = self.gacco_organization
        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.get(self._index_view())

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract List', response.content)
        for e in expected_contract:
            self.assertIn(e.contract_name, response.content)
        self.assertNotIn(self.contract_e.contract_name, response.content)

    def test_show_register(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.get(self._show_register_view())

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail', response.content)

    def test_show_register_have_no_org(self):
        # Create account and logged in.
        self.setup_user()

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.get(self._show_register_view(), follow=True)

        self.assertRedirects(response, self._index_view())
        self.assertIn('You need to create an organization first.', response.content)

    def test_register_field_required_error(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()

        data = {
            'contract_name': '',
            'contract_type': 'PF',
            'register_type': REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': '',
            'contractor_organization': self.org_tac.id,
            'start_date': '',
            'end_date': '',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._register_view(), data=data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail', response.content)
        self.assertEqual(4, response.content.count(' The field is required.'))

    def test_register_contract_field_invalid_error(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()

        data = {
            'contract_name': '12345678901234567890123456789012345678901234567890123456789012345678901234567890123456789\
            01234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456\
            7890123456789012345678901234567890123456789012345678901234567890',
            'contract_type': 'PF',
            'register_type': REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': '666666',
            'contractor_organization': self.org_tac.id,
            'start_date': '2016/03/31',
            'end_date': '2016/03/01',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._register_view(), data=data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail', response.content)
        self.assertIn('Ensure this value has at most 255 characters', response.content)
        self.assertIn('Ensure this value has at least 8 characters (it has 6).', response.content)
        self.assertIn('Contract end date is before contract start date.', response.content)

    def test_register_invitation_code_is_used_error(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()

        data = {
            'contract_name': 'name',
            'contract_type': 'PF',
            'register_type': REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': self.contract_a.invitation_code,
            'contractor_organization': self.org_tac.id,
            'start_date': '2016/03/01',
            'end_date': '2016/03/31',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._register_view(), data=data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail', response.content)
        self.assertIn('The invitation code has been used.', response.content)

    def test_register_contract_detail_field_invalid_error(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()

        data = {
            'contract_name': 'owner contract for tac',
            'contract_type': 'O',
            'register_type': REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': 'invitation_code_tac',
            'contractor_organization': self.org_tac.id,
            'start_date': '2016/03/01',
            'end_date': '2016/03/31',
            'detail_course': ['course-v1:edX+k01+2016_03', 'course-v1:edX+k01+2016_03'],
            'detail_delete': ['', ''],
            'detail_id': ['', '']
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._register_view(), data=data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail Info', response.content)
        self.assertIn('You can not enter duplicate values in Contract Detail Info.', response.content)

    def test_register_additional_info__field_invalid_error(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()

        data = {
            'contract_name': 'owner contract for tac',
            'contract_type': 'O',
            'register_type': REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': 'invitation_code_tac',
            'contractor_organization': self.org_tac.id,
            'start_date': '2016/03/01',
            'end_date': '2016/03/31',
            'detail_course': ['course-v1:edX+k01+2016_03', 'course-v1:edX+k02+2016_03'],
            'detail_delete': ['', ''],
            'detail_id': ['', ''],
            'additional_info_display_name': ['english name', 'english name'],
            'additional_info_delete': ['', ''],
            'additional_info_id': ['', '']
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._register_view(), data=data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail', response.content)
        self.assertIn('You can not enter duplicate values in Additional Info.', response.content)

    def test_register_by_platfomer_success(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()

        data = {
            'contract_name': 'owner contract for tac',
            'contract_type': 'O',
            'register_type': REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': 'invitationcodetac',
            'contractor_organization': self.org_tac.id,
            'start_date': '2016/03/01',
            'end_date': '2016/03/31',
            'detail_course': ['course-v1:edX+k01+2016_03', 'course-v1:edX+k02+2016_03'],
            'detail_delete': ['', ''],
            'detail_id': ['', ''],
            'additional_info_display_name': ['first name', 'family name'],
            'additional_info_delete': ['', ''],
            'additional_info_id': ['', '']
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._register_view(), data=data, follow=True)

        self.assertIn("The new contract has been added.", response.content)
        self.assertRedirects(response, self._index_view())
        self.assertIn('owner contract for tac', response.content)
        self.assertIn('invitationcodetac', response.content)

    def test_register_by_aggregator_success(self):

        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()

        data = {
            'contract_name': 'owner service contract for org_e',
            'contract_type': 'OS',
            'register_type': REGISTER_TYPE_DISABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': 'invitationcodee',
            'contractor_organization': self.org_e.id,
            'start_date': '2016/03/01',
            'end_date': '2016/03/31',
            'detail_course': ['course-v1:edX+k01+2016_03', 'course-v1:edX+k02+2016_03'],
            'detail_delete': ['', ''],
            'detail_id': ['', ''],
            'additional_info_display_name': ['first name', 'last name'],
            'additional_info_delete': ['', ''],
            'additional_info_id': ['', '']
        }

        with self.skip_check_course_selection(current_organization=self.org_tac):
            response = self.client.post(self._register_view(), data=data, follow=True)

        self.assertRedirects(response, self._index_view())
        self.assertIn("The new contract has been added", response.content)
        self.assertIn('owner service contract for org_e', response.content)
        self.assertIn('invitationcodee', response.content)

    def test_detail_illegal_access(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.get(self._detail_view(self.contract_e.id))

        self.assertEqual(404, response.status_code)

    def test_detail_success(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.get(self._detail_view(self.contract_b.id))

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail', response.content)
        self.assertIn(self.contract_b.contract_name, response.content)
        self.assertIn('gacco/course1/run1', response.content)
        self.assertIn('gacco/course2/run2', response.content)
        self.assertNotIn('tac/course1/run1', response.content)
        self.assertNotIn('tac/course2/run2', response.content)

    def test_edit_illegal_access(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()

        data = {
            'contract_name': self.contract_a.contract_name,
            'contract_type': self.contract_a.contract_type,
            'register_type':self.contract_a.register_type,
            'invitation_code': self.contract_a.invitation_code,
            'contractor_organization': self.org_a.id,
            'start_date': self.contract_a.start_date,
            'end_date': self.contract_a.end_date,
        }

        with self.skip_check_course_selection(current_organization=self.org_tac):
            response = self.client.post(self._edit_view(self.contract_a.id), data=data)

        self.assertEqual(404, response.status_code)

    def test_edit_field_required_error(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()

        data = {
            'contract_name': '',
            'contract_type': 'PF',
            'register_type': REGISTER_TYPE_ENABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': '',
            'contractor_organization': self.org_a.id,
            'start_date': '',
            'end_date': '',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._edit_view(self.contract_a.id), data=data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail', response.content)
        self.assertEqual(4, response.content.count(' The field is required.'))

    def test_edit_contract_field_invalid_error(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()

        data = {
            'contract_name': '12345678901234567890123456789012345678901234567890123456789012345678901234567890123456789\
            01234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456\
            7890123456789012345678901234567890123456789012345678901234567890',
            'contract_type': 'PF',
            'register_type': REGISTER_TYPE_ENABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': '123456',
            'contractor_organization': self.org_a.id,
            'start_date': '2016/03/31',
            'end_date': '2016/03/01',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._edit_view(self.contract_a.id), data=data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail', response.content)
        self.assertIn('Ensure this value has at most 255 characters', response.content)
        self.assertIn('Ensure this value has at least 8 characters (it has 6).', response.content)
        self.assertIn('Contract end date is before contract start date.', response.content)

    def test_edit_contract_detail_field_invalid_error(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()

        data = {
            'contract_name': 'owner contract for tac',
            'contract_type': 'PF',
            'register_type': REGISTER_TYPE_ENABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': 'invitationcodea',
            'contractor_organization': self.org_a.id,
            'start_date': '2016/03/01',
            'end_date': '2016/03/31',
            'detail_course': ['gacco/course1/run1', 'gacco/course1/run1'],
            'detail_delete': ['', ''],
            'detail_id': ['', '']
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._edit_view(self.contract_a.id), data=data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail Info', response.content)
        self.assertIn('You can not enter duplicate values in Contract Detail Info.', response.content)

    def test_edit_additional_info__field_invalid_error(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()

        data = {
            'contract_name': 'owner contract for tac',
            'contract_type': 'O',
            'register_type': REGISTER_TYPE_ENABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': 'invitationcodea',
            'contractor_organization': self.org_a.id,
            'start_date': '2016/03/01',
            'end_date': '2016/03/31',
            'detail_course': ['gacco/course1/run1', 'gacco/course2/run2'],
            'detail_delete': ['', ''],
            'detail_id': ['', ''],
            'additional_info_display_name': ['english name', 'english name'],
            'additional_info_delete': ['', ''],
            'additional_info_id': ['', '']
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._edit_view(self.contract_a.id), data=data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail', response.content)
        self.assertIn('You can not enter duplicate values in Additional Info.', response.content)

    def test_edit_update_contract(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()

        _new_contract_name = self.contract_a.contract_name + '_new'
        _new_invitation_code = self.contract_a.invitation_code + 'new'
        _new_start_date = date.today()
        _new_end_date = (date.today() + timedelta(100))
        _new_contract_type = CONTRACT_TYPE_GACCO_SERVICE

        data = {
            'contract_name': _new_contract_name,
            'contract_type': _new_contract_type[0],
            'register_type': REGISTER_TYPE_ENABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': _new_invitation_code,
            'contractor_organization': self.org_a.id,
            'start_date': _new_start_date.strftime("%Y/%m/%d"),
            'end_date': _new_end_date.strftime("%Y/%m/%d")
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._edit_view(self.contract_a.id), data=data, follow=True)

        self.assertRedirects(response, self._index_view())
        self.assertIn("The contract changes have been saved.", response.content)
        self.assertIn(_new_contract_name, response.content)
        self.assertIn(_new_invitation_code, response.content)
        self.assertIn('Gacco Service Contract', response.content)
        self.assertIn(_new_start_date.strftime("%Y/%m/%d"), response.content)
        self.assertIn(_new_end_date.strftime("%Y/%m/%d"), response.content)

    def test_edit_add_contract_detail_and_additional_info(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()

        _new_contract_name = self.contract_a.contract_name + '_new'
        _new_invitation_code = self.contract_a.invitation_code + 'new'
        _new_start_date = date.today()
        _new_end_date = (date.today() + timedelta(100))
        _new_contract_type = CONTRACT_TYPE_GACCO_SERVICE

        data = {
            'contract_name': _new_contract_name,
            'contract_type': _new_contract_type[0],
            'register_type': REGISTER_TYPE_ENABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': _new_invitation_code,
            'contractor_organization': self.org_a.id,
            'start_date': _new_start_date.strftime("%Y/%m/%d"),
            'end_date': _new_end_date.strftime("%Y/%m/%d"),
            'detail_course': ['gacco/course1/run1', 'gacco/course2/run2'],
            'detail_delete': ['', ''],
            'detail_id': ['', ''],
            'additional_info_display_name': ['first name', 'last name'],
            'additional_info_delete': ['', ''],
            'additional_info_id': ['', '']
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._edit_view(self.contract_a.id), data=data, follow=True)

        self.assertRedirects(response, self._index_view())
        self.assertIn('The contract changes have been saved.', response.content)
        self.assertEqual(2, len(AdditionalInfo.find_by_contract_id(self.contract_b)))
        self.assertEqual(2, len(ContractDetail.find_enabled_by_contractor_and_contract_id(self.org_b.id, self.contract_b.id)))

    def test_edit_remove_contract_detail_and_additional_info(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()

        _new_contract_name = self.contract_b.contract_name + '_new'
        _new_invitation_code = self.contract_b.invitation_code + 'new'
        _new_start_date = date.today()
        _new_end_date = (date.today() + timedelta(100))
        _new_contract_type = CONTRACT_TYPE_GACCO_SERVICE

        data = {
            'contract_name': _new_contract_name,
            'contract_type': _new_contract_type[0],
            'register_type': REGISTER_TYPE_ENABLE_REGISTER_BY_STUDENT[0],
            'invitation_code': _new_invitation_code,
            'contractor_organization': self.org_b.id,
            'start_date': _new_start_date.strftime("%Y/%m/%d"),
            'end_date': _new_end_date.strftime("%Y/%m/%d"),
            'detail_course': ['gacco/course1/run1', 'gacco/course2/run2'],
            'detail_delete': ['', '1'],
            'detail_id': ['1', '2'],
            'additional_info_display_name': ['first name', 'last name'],
            'additional_info_delete': ['', '1'],
            'additional_info_id': ['1', '2']
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._edit_view(self.contract_b.id), data=data, follow=True)

        self.assertRedirects(response, self._index_view())
        self.assertIn('The contract changes have been saved.', response.content)

        after_additional_info_list = AdditionalInfo.find_by_contract_id(self.contract_b)
        after_contract_detail_list = ContractDetail.find_enabled_by_contractor_and_contract_id(self.org_b.id, self.contract_b.id)
        self.assertEqual(1, len(after_additional_info_list))
        self.assertEqual('first name', after_additional_info_list[0].display_name)
        self.assertEqual(1, len(after_contract_detail_list))
        self.assertEqual('gacco/course1/run1', unicode(after_contract_detail_list[0].course_id))

    def test_edit_remove_contract(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()

        data = {
            'contract_name': self.contract_b.contract_name,
            'contract_type': self.contract_b.contract_type,
            'register_type': self.contract_b.register_type,
            'invitation_code': self.contract_b.invitation_code,
            'contractor_organization': self.org_b.id,
            'start_date': self.contract_b.start_date,
            'end_date': self.contract_b.end_date,
            'detail_course': ['gacco/course1/run1', 'gacco/course2/run2'],
            'detail_delete': ['', ''],
            'detail_id': ['1', '2'],
            'additional_info_display_name': ['first name', 'last name'],
            'additional_info_delete': ['', ''],
            'additional_info_id': ['1', '2'],
            'action_name': 'delete'
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._edit_view(self.contract_b.id), data=data, follow=True)

        self.assertRedirects(response, self._index_view())
        self.assertIn('The contract has been deleted.', response.content)
        self.assertNotIn(self.contract_b.contract_name, response.content)
        self.assertEqual(0, len(Contract.find_enabled_by_contractor(self.org_b.id)))

    def test_edit_cannot_remove_contract_error(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_org_data()
        self._setup_contract_data()
        self._setup_course_data()
        ContractRegisterFactory.create(user=self.user, contract=self.contract_b, status=REGISTER_INVITATION_CODE)

        data = {
            'contract_name': self.contract_b.contract_name,
            'contract_type': self.contract_b.contract_type,
            'register_type': self.contract_b.register_type,
            'invitation_code': self.contract_b.invitation_code,
            'contractor_organization': self.org_b.id,
            'start_date': self.contract_b.start_date.strftime("%Y/%m/%d"),
            'end_date': self.contract_b.end_date.strftime("%Y/%m/%d"),
            'action_name': 'delete'
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._edit_view(self.contract_b.id), data=data, follow=True)

        self.assertEqual(200, response.status_code)
        self.assertIn('Contract Detail', response.content)
        self.assertIn('The contract cannot be deleted, because invitation code has been registered.', response.content)

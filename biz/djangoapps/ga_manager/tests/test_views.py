"""
Test for contract feature
"""
import json

from django.core.urlresolvers import reverse

from biz.djangoapps.ga_contract.tests.factories import ContractFactory
from biz.djangoapps.ga_invitation.models import REGISTER_INVITATION_CODE
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_manager.models import PERMISSION_AGGREGATOR, PERMISSION_DIRECTOR, PERMISSION_MANAGER, Manager
from biz.djangoapps.ga_manager.tests.factories import ManagerFactory
from biz.djangoapps.util.tests.testcase import BizViewTestBase
from student.tests.factories import UserFactory


class ManagerViewTest(BizViewTestBase):
    def _index_view(self):
        return reverse('biz:manager:index')

    def _modify_ajax_view(self):
        return reverse('biz:manager:modify_ajax')

    def _list_ajax_view(self):
        return reverse('biz:manager:list_ajax')

    def _setup_test_data(self):
        self.user_gacco_staff = UserFactory(username='gacco_staff', is_staff=True, is_superuser=True)
        self.user_tac_aggregator = UserFactory(username='tac_aggregator')
        self.user_a_director = UserFactory(username='a_director')
        self.user_a_manager = UserFactory(username='a_manager')
        self.user_e_director1 = UserFactory(username='e_director1')
        self.user_e_director2 = UserFactory(username='e_director2')

        self.org_tac = self._create_organization(org_name='org_tac', org_code='tac', creator_org=self.gacco_organization)
        self.org_a = self._create_organization(org_name='org_a', org_code='a', creator_org=self.gacco_organization)
        self.org_b = self._create_organization(org_name='org_b', org_code='b', creator_org=self.gacco_organization)
        self.org_e = self._create_organization(org_name='org_e', org_code='e', creator_org=self.org_tac)

        self.manager_platfomer = ManagerFactory.create(org=self.gacco_organization, user=self.user_gacco_staff,
                                                       permissions=[self.platformer_permission])
        self.manager_aggregator = ManagerFactory.create(org=self.org_tac, user=self.user_tac_aggregator,
                                                        permissions=[self.aggregator_permission])
        self.manager_a_director = ManagerFactory.create(org=self.org_a, user=self.user_a_director,
                                                        permissions=[self.director_permission])
        self.manager_e_director1 = ManagerFactory.create(org=self.org_e, user=self.user_e_director1,
                                                         permissions=[self.director_permission,
                                                                      self.manager_permission])
        self.manager_e_director2 = ManagerFactory.create(org=self.org_e, user=self.user_e_director2,
                                                         permissions=[self.director_permission])

    def test_index_for_platfomer(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.get(self._index_view())

        self.assertEqual(200, response.status_code)
        # assert organization select list
        self.assertIn('Manager Setting', response.content)
        self.assertIn(self.org_tac.org_name, response.content)
        self.assertIn(self.org_a.org_name, response.content)
        self.assertIn(self.org_b.org_name, response.content)
        self.assertNotIn(self.org_e.org_name, response.content)
        # assert permission select list
        self.assertIn('<option value="{}">{}</option>'.format(PERMISSION_AGGREGATOR[0], PERMISSION_AGGREGATOR[0]),
                      response.content)
        self.assertIn('<option value="{}">{}</option>'.format(PERMISSION_DIRECTOR[0], PERMISSION_DIRECTOR[0]),
                      response.content)
        self.assertIn('<option value="{}">{}</option>'.format(PERMISSION_MANAGER[0], PERMISSION_MANAGER[0]),
                      response.content)

    def test_index_for_aggregator(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.org_tac,
                                              current_manager=self.manager_aggregator):
            response = self.client.get(self._index_view())

        self.assertEqual(200, response.status_code)
        # assert organization select list
        self.assertIn('Manager Setting', response.content)
        self.assertIn(self.org_e.org_name, response.content)
        self.assertNotIn(self.org_a.org_name, response.content)
        self.assertNotIn(self.org_b.org_name, response.content)
        # assert permission select list
        self.assertNotIn('<option value="{}">{}</option>'.format(PERMISSION_AGGREGATOR[0], PERMISSION_AGGREGATOR[0]),
                         response.content)
        self.assertIn('<option value="{}">{}</option>'.format(PERMISSION_DIRECTOR[0], PERMISSION_DIRECTOR[0]),
                      response.content)
        self.assertIn('<option value="{}">{}</option>'.format(PERMISSION_MANAGER[0], PERMISSION_MANAGER[0]),
                      response.content)

    def test_index_for_director(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.org_a,
                                              current_manager=self.manager_a_director):
            response = self.client.get(self._index_view())

        self.assertEqual(200, response.status_code)
        # assert organization select list
        self.assertIn('Manager Setting', response.content)
        self.assertIn(self.org_a.org_name, response.content)
        self.assertNotIn(self.org_b.org_name, response.content)
        self.assertNotIn(self.org_e.org_name, response.content)
        # assert permission select list
        self.assertNotIn('<option value="{}">{}</option>'.format(PERMISSION_AGGREGATOR[0], PERMISSION_AGGREGATOR[0]),
                         response.content)
        self.assertIn('<option value="{}">{}</option>'.format(PERMISSION_DIRECTOR[0], PERMISSION_DIRECTOR[0]),
                      response.content)
        self.assertIn('<option value="{}">{}</option>'.format(PERMISSION_MANAGER[0], PERMISSION_MANAGER[0]),
                      response.content)

    def test_list_ajax_not_exists_org(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._list_ajax_view(),
                                        data={'selected_org_id': '100', 'permission_name': PERMISSION_DIRECTOR[0]})

            self.assertEqual(404, response.status_code)

    def test_list_ajax_invalid_org_for_platfomer(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._list_ajax_view(),
                                        data={'selected_org_id': self.org_e.id,
                                              'permission_name': PERMISSION_DIRECTOR[0]})

            self.assertEqual(400, response.status_code)

    def test_list_ajax_invalid_org_for_aggregator(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.org_tac,
                                              current_manager=self.manager_aggregator):
            response = self.client.post(self._list_ajax_view(),
                                        data={'selected_org_id': self.org_a.id,
                                              'permission_name': PERMISSION_DIRECTOR[0]})

            self.assertEqual(400, response.status_code)

    def test_list_ajax_invalid_org_for_director(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.org_a,
                                              current_manager=self.manager_a_director):
            response = self.client.post(self._list_ajax_view(),
                                        data={'selected_org_id': self.org_b.id,
                                              'permission_name': PERMISSION_DIRECTOR[0]})

            self.assertEqual(400, response.status_code)

    def test_list_ajax_not_exists_permission(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._list_ajax_view(),
                                        data={'selected_org_id': self.org_a.id,
                                              'permission_name': 'dummy_permission'})

            self.assertEqual(404, response.status_code)

    def test_list_ajax_invalid_permission(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.org_a,
                                              current_manager=self.manager_a_director):
            response = self.client.post(self._list_ajax_view(),
                                        data={'selected_org_id': self.org_a.id,
                                              'permission_name': PERMISSION_AGGREGATOR[0]})

            self.assertEqual(400, response.status_code)

    def test_list_ajax_single(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._list_ajax_view(),
                                        data={'selected_org_id': self.org_tac.id,
                                              'permission_name': PERMISSION_AGGREGATOR[0]})

            content = json.loads(response.content)
            self.assertEqual(200, response.status_code)
            self.assertEqual(True, content['success'])
            self.assertEqual(1, len(content['show_list']))
            self.assertEqual(self.user_tac_aggregator.username, content['show_list'][0]['name'])
            self.assertEqual(self.user_tac_aggregator.email, content['show_list'][0]['email'])

    def test_list_ajax_multiple(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.org_tac,
                                              current_manager=self.manager_aggregator):
            response = self.client.post(self._list_ajax_view(),
                                        data={'selected_org_id': self.org_e.id,
                                              'permission_name': PERMISSION_DIRECTOR[0]})

            content = json.loads(response.content)
            self.assertEqual(200, response.status_code)
            self.assertEqual(True, content['success'])
            self.assertEqual(2, len(content['show_list']))
            self.assertEqual(self.user_e_director1.username, content['show_list'][0]['name'])
            self.assertEqual(self.user_e_director1.email, content['show_list'][0]['email'])
            self.assertEqual(self.user_e_director2.username, content['show_list'][1]['name'])
            self.assertEqual(self.user_e_director2.email, content['show_list'][1]['email'])

    def test_modify_ajax_miss_param_user(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_tac.id,
                                              'permission_name': PERMISSION_AGGREGATOR[0]})

            self.assertEqual(400, response.status_code)

    def test_modify_ajax_miss_param_org(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'permission_name': PERMISSION_AGGREGATOR[0],
                                              'unique_student_identifier': 'dummy'})

            self.assertEqual(400, response.status_code)

    def test_modify_ajax_miss_param_permission(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_tac.id,
                                              'unique_student_identifier': 'dummy'})

            self.assertEqual(400, response.status_code)

    def test_modify_ajax_not_exists_user(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_tac.id,
                                              'permission_name': PERMISSION_AGGREGATOR[0],
                                              'unique_student_identifier': 'dummy'})

            content = json.loads(response.content)
            self.assertEqual(200, response.status_code)
            self.assertEqual(False, content['success'])
            self.assertEqual('The user does not exist.', content['message'])

    def test_modify_ajax_not_active_user(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        not_active_user = UserFactory(username='not_active', is_active=False)

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_tac.id,
                                              'permission_name': PERMISSION_AGGREGATOR[0],
                                              'unique_student_identifier': not_active_user.username,
                                              'action': 'revoke'})

            content = json.loads(response.content)
            self.assertEqual(200, response.status_code)
            self.assertEqual(False, content['success'])
            self.assertEqual('The user is not active.', content['message'])

    def test_modify_ajax_own_self(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_tac.id,
                                              'permission_name': PERMISSION_AGGREGATOR[0],
                                              'unique_student_identifier': self.user.username,
                                              'action': 'revoke'})

            content = json.loads(response.content)
            self.assertEqual(200, response.status_code)
            self.assertEqual(False, content['success'])
            self.assertEqual('You can not change permissions of yourself.', content['message'])

    def test_modify_ajax_contract_unregistered_user(self):
        self.setup_user()
        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.org_a,
                                              current_manager=self.manager_a_director):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_a.id,
                                              'permission_name': PERMISSION_DIRECTOR[0],
                                              'unique_student_identifier': UserFactory().username,
                                              'action': 'allow'})

            content = json.loads(response.content)
            self.assertEqual(200, response.status_code)
            self.assertEqual(False, content['success'])
            self.assertEqual('The user have not registered course.', content['message'])

    def test_modify_ajax_miss_action(self):
        # Create account and logged in.
        self.setup_user()

        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_tac.id,
                                              'permission_name': PERMISSION_AGGREGATOR[0],
                                              'unique_student_identifier': UserFactory().username})

            self.assertEqual(400, response.status_code)

    def test_modify_ajax_revoke_from_single_permission(self):
        self.setup_user()
        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.org_e,
                                              current_manager=self.manager_e_director1):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_e.id,
                                              'permission_name': PERMISSION_DIRECTOR[0],
                                              'unique_student_identifier': self.user_e_director2.email,
                                              'action': 'revoke'})

        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(True, content['success'])
        self.assertEqual(self.user_e_director2.username, content['name'])
        self.assertEqual(self.user_e_director2.email, content['email'])

        self.assertEqual(False, self.manager_e_director2.is_director())

    def test_modify_ajax_revoke_from_multiple_permission(self):
        self.setup_user()
        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.org_e,
                                              current_manager=self.manager_e_director2):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_e.id,
                                              'permission_name': PERMISSION_DIRECTOR[0],
                                              'unique_student_identifier': self.user_e_director1.email,
                                              'action': 'revoke'})

        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(True, content['success'])
        self.assertEqual(self.user_e_director1.username, content['name'])
        self.assertEqual(self.user_e_director1.email, content['email'])

        self.assertEqual(True, self.manager_e_director1.is_manager())
        self.assertEqual(False, self.manager_e_director1.is_director())

    def test_modify_ajax_revoke_not_have_permission_user(self):
        self.setup_user()
        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.org_e,
                                              current_manager=self.manager_e_director2):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_e.id,
                                              'permission_name': PERMISSION_DIRECTOR[0],
                                              'unique_student_identifier': UserFactory().username,
                                              'action': 'revoke'})

        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(False, content['success'])
        self.assertEqual('The user does not have permission.', content['message'])

    def test_modify_ajax_allow_for_platfomer(self):
        self.setup_user()
        self._setup_test_data()
        user = UserFactory(username='b_director')

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_b.id,
                                              'permission_name': PERMISSION_DIRECTOR[0],
                                              'unique_student_identifier': user.username,
                                              'action': 'allow'})

        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(True, content['success'])
        self.assertEqual(user.username, content['name'])
        self.assertEqual(user.email, content['email'])

        manager = Manager.get_manager(user, self.org_b)
        self.assertEqual(True, manager.is_director())
        self.assertEqual(False, manager.is_manager())

    def test_modify_ajax_allow_have_same_permission_user(self):
        self.setup_user()
        self._setup_test_data()

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_a.id,
                                              'permission_name': PERMISSION_DIRECTOR[0],
                                              'unique_student_identifier': self.user_a_director.username,
                                              'action': 'allow'})

        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(False, content['success'])
        self.assertEqual('The user already has the same permission.', content['message'])

    def test_modify_ajax_allow_contract_registered_user(self):
        self.setup_user()
        self._setup_test_data()

        user = UserFactory(username='a_manager2')
        contract = ContractFactory.create(contractor_organization=self.org_a,
                                          owner_organization=self.gacco_organization, created_by=self.user_gacco_staff)
        ContractRegisterFactory(user=user, contract=contract, status=REGISTER_INVITATION_CODE)

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=self.manager_platfomer):
            response = self.client.post(self._modify_ajax_view(),
                                        data={'selected_org_id': self.org_a.id,
                                              'permission_name': PERMISSION_MANAGER[0],
                                              'unique_student_identifier': user.username,
                                              'action': 'allow'})

        content = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(True, content['success'])
        self.assertEqual(user.username, content['name'])
        self.assertEqual(user.email, content['email'])

        manager = Manager.get_manager(user, self.org_a)
        self.assertEqual(False, manager.is_director())
        self.assertEqual(True, manager.is_manager())

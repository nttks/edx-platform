from biz.djangoapps.ga_contract.tests.factories import ContractFactory
from django.core.urlresolvers import reverse

from biz.djangoapps.util.tests.testcase import BizViewTestBase


class OrganizationViewTest(BizViewTestBase):
    def _index_view(self):
        return reverse('biz:organization:index')

    def _show_register_view(self):
        return reverse('biz:organization:show_register')

    def _register_view(self):
        return reverse('biz:organization:register')

    def _detail_view(self, selected_org_id):
        return reverse('biz:organization:detail', kwargs={'selected_id': selected_org_id})

    def _edit_view(self, selected_org_id):
        return reverse('biz:organization:edit', kwargs={'selected_id': selected_org_id})

    def test_index(self):
        # Create account and logged in.
        self.setup_user()

        expected_organization = [
            self._create_organization(org_code='org1', creator_org=self.gacco_organization),
            self._create_organization(org_code='org2', creator_org=self.gacco_organization),
            self._create_organization(org_code='org3', creator_org=self.gacco_organization)
        ]
        # Create other organization
        other_organization = self._create_organization(org_code='other_org', creator_org=expected_organization[0])

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.get(self._index_view())

        self.assertEqual(200, response.status_code)
        self.assertIn('Organization List', response.content)
        for org in expected_organization:
            self.assertIn(org.org_code, response.content)
        self.assertNotIn(other_organization.org_code, response.content)

    def test_show_register(self):
        # Create account and logged in.
        self.setup_user()

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.get(self._show_register_view())

        self.assertEqual(200, response.status_code)
        self.assertIn('Organization Detail', response.content)

    def test_register_field_required_error(self):
        # Create account and logged in.
        self.setup_user()

        data = {
            'org_name': '',
            'org_code': '',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._register_view(), data=data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Organization Detail', response.content)

    def test_register_field_invalid_error(self):
        # Create account and logged in.
        self.setup_user()

        data = {
            'org_name': '123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123\
            4567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789\
            0123456789012345678901234567890123456789012345678901234567890',
            'org_code': '12345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            response = self.client.post(self._register_view(), data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Organization Detail', response.content)

    def test_register_success(self):
        # Create account and logged in.
        self.setup_user()

        data = {
            'org_name': 'new_org_name',
            'org_code': 'new_org_code',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization):
            # use follow=True to follow redirect
            response = self.client.post(self._register_view(), data=data, follow=True)

        self.assertRedirects(response, self._index_view())
        self.assertIn("The new organization has been added.", response.content)
        self.assertIn("new_org_name", response.content)
        self.assertIn("new_org_code", response.content)

    def test_detail_illegal_access(self):
        # Create account and logged in.
        self.setup_user()

        platformer_manager = self._create_manager(self.gacco_organization, self.user,
                                                  self.gacco_organization, [self.platformer_permission])

        org1 = self._create_organization(org_code='org1', creator_org=self.gacco_organization)
        org2 = self._create_organization(org_code='org2', creator_org=org1)

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=platformer_manager):
            response = self.client.get(self._detail_view(org2.id))

        self.assertEqual(404, response.status_code)

    def test_detail_success(self):
        # Create account and logged in.
        self.setup_user()

        platformer_manager = self._create_manager(self.gacco_organization, self.user,
                                                  self.gacco_organization, [self.platformer_permission])

        org1 = self._create_organization(org_code='org1', creator_org=self.gacco_organization)

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=platformer_manager):
            response = self.client.get(self._detail_view(org1.id))

        self.assertEqual(200, response.status_code)
        self.assertIn('Organization Detail', response.content)
        self.assertIn('org1', response.content)

    def test_edit_field_required_error(self):
        # Create account and logged in.
        self.setup_user()

        platformer_manager = self._create_manager(self.gacco_organization, self.user,
                                                  self.gacco_organization, [self.platformer_permission])
        org1 = self._create_organization(org_code='org1', creator_org=self.gacco_organization)

        data = {
            'org_name': '',
            'org_code': '',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=platformer_manager):
            response = self.client.post(self._edit_view(org1.id), data)

        self.assertEqual(200, response.status_code)
        self.assertIn('The field is required.', response.content)

    def test_edit_field_invalid_error(self):
        # Create account and logged in.
        self.setup_user()

        platformer_manager = self._create_manager(self.gacco_organization, self.user,
                                                  self.gacco_organization, [self.platformer_permission])
        org1 = self._create_organization(org_code='org1', creator_org=self.gacco_organization)

        data = {
            'org_name': '123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123\
            4567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789\
            0123456789012345678901234567890123456789012345678901234567890',
            'org_code': '12345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=platformer_manager):
            response = self.client.post(self._edit_view(org1.id), data)

        self.assertEqual(200, response.status_code)
        self.assertIn('Ensure this value has at most 255 characters', response.content)
        self.assertIn('Ensure this value has at most 64 characters', response.content)

    def test_edit_update_success(self):
        # Create account and logged in.
        self.setup_user()

        platformer_manager = self._create_manager(self.gacco_organization, self.user,
                                                  self.gacco_organization, [self.platformer_permission])
        org1 = self._create_organization(org_code='org1', creator_org=self.gacco_organization)

        data = {
            'org_name': 'new_org_name',
            'org_code': 'new_org_code',
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=platformer_manager):
            # use follow=True to follow redirect
            response = self.client.post(self._edit_view(org1.id), data, follow=True)

        self.assertRedirects(response, self._index_view())
        self.assertIn("The organization changes have been saved.", response.content)
        self.assertIn("new_org_name", response.content)
        self.assertIn("new_org_code", response.content)

    def test_edit_delete_success(self):
        # Create account and logged in.
        self.setup_user()

        platformer_manager = self._create_manager(self.gacco_organization, self.user,
                                                  self.gacco_organization, [self.platformer_permission])
        org1 = self._create_organization(org_code='org1', creator_org=self.gacco_organization)

        data = {
            'org_name': org1.org_code,
            'org_code': org1.org_name,
            'action_name': 'delete'
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=platformer_manager):
            # use follow=True to follow redirect
            response = self.client.post(self._edit_view(org1.id), data, follow=True)

        self.assertRedirects(response, self._index_view())
        self.assertIn("The organization has been deleted.", response.content)
        self.assertNotIn(org1.org_code, response.content)
        self.assertNotIn(org1.org_name, response.content)

    def test_edit_cannot_delete(self):
        # Create account and logged in.
        self.setup_user()

        platformer_manager = self._create_manager(self.gacco_organization, self.user,
                                                  self.gacco_organization, [self.platformer_permission])
        org1 = self._create_organization(org_code='org1', creator_org=self.gacco_organization)
        ContractFactory.create(contractor_organization=org1, owner_organization=self.gacco_organization,
                               created_by=self.user)

        data = {
            'org_name': org1.org_code,
            'org_code': org1.org_name,
            'action_name': 'delete'
        }

        with self.skip_check_course_selection(current_organization=self.gacco_organization,
                                              current_manager=platformer_manager):
            # use follow=True to follow redirect
            response = self.client.post(self._edit_view(org1.id), data, follow=True)

        self.assertEqual(200, response.status_code)
        self.assertIn("The organization cannot be deleted, because it have contracts.", response.content)

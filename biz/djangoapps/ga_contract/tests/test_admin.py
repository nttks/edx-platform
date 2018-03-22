from mock import patch

from django.core.urlresolvers import reverse

from biz.djangoapps.util.tests.testcase import BizTestBase
from student.tests.factories import UserFactory


class ContractAuthAdminTest(BizTestBase):

    def setUp(self):
        super(ContractAuthAdminTest, self).setUp()

        user = UserFactory.create(is_staff=True, is_superuser=True)
        user.save()

        self.client.login(username=user.username, password='test')

        self.contract = self._create_contract()
        self.contract_other = self._create_contract()
        self.url_code = 'testUrlCode'

    def test_initial_url_code(self):
        with patch(
            'biz.djangoapps.ga_contract.admin.get_random_string',
            return_value=self.url_code
        ):
            response = self.client.get(reverse('admin:ga_contract_contractauth_add'))
            self.assertEqual(200, response.status_code)
            self.assertIn('value="{url_code}"'.format(url_code=self.url_code), response.content)

    def test_add(self):
        response = self.client.post(reverse('admin:ga_contract_contractauth_add'), data={
            'contract': self.contract.id,
            'url_code': self.url_code,
        })
        self.assertRedirects(response, reverse('admin:ga_contract_contractauth_changelist'))

        response = self.client.get(reverse('admin:ga_contract_contractauth_changelist'))
        self.assertEqual(200, response.status_code)
        self.assertIn('{contract_name}({url_code})'.format(contract_name=self.contract.contract_name, url_code=self.url_code), response.content)

    def test_contract_required(self):
        response = self.client.post(reverse('admin:ga_contract_contractauth_add'), data={
            'url_code': self.url_code,
        })
        self.assertEqual(200, response.status_code)
        self.assertIn('This field is required.'.format(url_code=self.url_code), response.content)

    def test_url_code_required(self):
        response = self.client.post(reverse('admin:ga_contract_contractauth_add'), data={
            'contract': self.contract.id,
        })
        self.assertEqual(200, response.status_code)
        self.assertIn('This field is required.'.format(url_code=self.url_code), response.content)
        self.assertIn('Url code is invalid. Please enter alphanumeric 8-255 characters.'.format(url_code=self.url_code), response.content)

    def test_url_code_duplicate(self):
        response = self.client.post(reverse('admin:ga_contract_contractauth_add'), data={
            'contract': self.contract_other.id,
            'url_code': self.url_code,
        })
        self.assertRedirects(response, reverse('admin:ga_contract_contractauth_changelist'))

        response = self.client.post(reverse('admin:ga_contract_contractauth_add'), data={
            'contract': self.contract.id,
            'url_code': self.url_code,
        })
        self.assertEqual(200, response.status_code)
        self.assertIn('Url code is duplicated. Please change url code.'.format(url_code=self.url_code), response.content)

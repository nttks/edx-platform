"""
Tests for course-selection feature
"""

from django.conf import settings
from django.core.urlresolvers import reverse

from opaque_keys.edx.keys import CourseKey

from biz.djangoapps.ga_contract.models import CONTRACT_TYPE_PF, CONTRACT_TYPE_OWNERS
from biz.djangoapps.ga_contract.tests.factories import ContractFactory
from biz.djangoapps.ga_manager.tests.factories import ManagerFactory
from biz.djangoapps.util import cache_utils
from biz.djangoapps.util.tests.testcase import BizViewTestBase


class CourseSelectionViewTest(BizViewTestBase):

    def setUp(self):
        super(CourseSelectionViewTest, self).setUp()
        self.setup_user()

    def _index_view(self):
        return reverse('biz:index')

    def _change_view(self):
        return reverse('biz:course_selection:change')

    def _create_manager(self, permissions):
        return ManagerFactory.create(
            org=self.gacco_organization,
            user=self.user,
            permissions=permissions
        )

    def _create_contract_for_pf(self):
        return self._create_contract(CONTRACT_TYPE_PF[0])

    def _create_contract_for_owners(self):
        return self._create_contract(CONTRACT_TYPE_OWNERS[0])

    def _create_contract(self, contract_type):
        return ContractFactory.create(
            contract_name='test',
            contract_type=contract_type,
            invitation_code='testtest',
            contractor_organization=self.gacco_organization,
            owner_organization=self.gacco_organization,
            created_by=self.user,
        )

    def _access_index(self, permission):
        manager = self._create_manager([permission])
        with self.skip_check_course_selection(current_manager=manager):
            return self.client.get(self._index_view())

    def test_index_platformer(self):
        response = self._access_index(self.platformer_permission)

        self.assertEqual(302, response.status_code)
        self.assertEqual('http://testserver{}'.format(reverse('biz:contract:index')), response['Location'])

    def test_index_aggregator_with_owner_contract(self):
        manager = self._create_manager([self.aggregator_permission])
        contract = self._create_contract_for_owners()
        with self.skip_check_course_selection(current_manager=manager, current_contract=contract):
            return self.client.get(self._index_view())

        self.assertEqual(302, response.status_code)
        self.assertEqual('http://testserver{}'.format(reverse('biz:contract:index')), response['Location'])

    def test_index_aggregator_with_pf_contract(self):
        manager = self._create_manager([self.aggregator_permission])
        contract = self._create_contract_for_pf()
        with self.skip_check_course_selection(current_manager=manager, current_contract=contract):
            return self.client.get(self._index_view())

        self.assertEqual(403, response.status_code)

    def test_index_director_with_pf_contract(self):
        manager = self._create_manager([self.director_permission])
        contract = self._create_contract_for_pf()
        with self.skip_check_course_selection(current_manager=manager, current_contract=contract):
            return self.client.get(self._index_view())

        self.assertEqual(302, response.status_code)
        self.assertEqual('http://testserver{}'.format(reverse('biz:achievement:index')), response['Location'])

    def test_index_director_with_owner_contract(self):
        manager = self._create_manager([self.director_permission])
        contract = self._create_contract_for_owners()
        with self.skip_check_course_selection(current_manager=manager, current_contract=contract):
            return self.client.get(self._index_view())

        self.assertEqual(403, response.status_code)

    def test_index_manager_with_pf_contract(self):
        manager = self._create_manager([self.manager_permission])
        contract = self._create_contract_for_pf()
        with self.skip_check_course_selection(current_manager=manager, current_contract=contract):
            return self.client.get(self._index_view())

        self.assertEqual(302, response.status_code)
        self.assertEqual('http://testserver{}'.format(reverse('biz:achievement:index')), response['Location'])

    def test_index_manager_with_owner_contract(self):
        manager = self._create_manager([self.manager_permission])
        contract = self._create_contract_for_owners()
        with self.skip_check_course_selection(current_manager=manager, current_contract=contract):
            return self.client.get(self._index_view())

        self.assertEqual(403, response.status_code)

    def test_index_aggregator_and_director_with_owner_contract(self):
        manager = self._create_manager([self.aggregator_permission, self.director_permission])
        contract = self._create_contract_for_owners()
        with self.skip_check_course_selection(current_manager=manager, current_contract=contract):
            return self.client.get(self._index_view())

        self.assertEqual(302, response.status_code)
        self.assertEqual('http://testserver{}'.format(reverse('biz:contract:index')), response['Location'])

    def test_index_aggregator_and_director_with_pf_contract(self):
        manager = self._create_manager([self.aggregator_permission, self.director_permission])
        contract = self._create_contract_for_pf()
        with self.skip_check_course_selection(current_manager=manager, current_contract=contract):
            return self.client.get(self._index_view())

        self.assertEqual(302, response.status_code)
        self.assertEqual('http://testserver{}'.format(reverse('biz:achievement:index')), response['Location'])

    def test_index_method_not_allowed(self):
        self.assertEqual(405, self.client.post(self._index_view()).status_code)

    def test_index_not_logged_in(self):
        self.logout()
        response = self.client.get(self._index_view())
        self.assertEqual(302, response.status_code)
        self.assertEqual(
            'http://testserver{}?next={}'.format(settings.LOGIN_URL, reverse('biz:index')),
            response['Location']
        )

    def test_change(self):
        # no cache at first
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.user))

        course_id = CourseKey.from_string('course-v1:org+course+run')
        with self.skip_check_course_selection():
            response = self.client.post(self._change_view(), {
                'org_id': 1,
                'contract_id': 2,
                'course_id': unicode(course_id),
            })

        # Vefiry response code and redirect_to
        self.assertEqual(302, response.status_code)
        self.assertEqual('http://testserver{}'.format(reverse('biz:index')), response['Location'])

        # Verify that cache is set for correct user
        self.assertEqual(('1', '2', unicode(course_id)), cache_utils.get_course_selection(self.user))

        # try second
        course_id_x = CourseKey.from_string('course-v1:org+courseX+run')
        with self.skip_check_course_selection():
            response = self.client.post(self._change_view(), {
                'org_id': 3,
                'contract_id': 4,
                'course_id': unicode(course_id_x),
            })

        # Vefiry response code and redirect_to
        self.assertEqual(302, response.status_code)
        self.assertEqual('http://testserver{}'.format(reverse('biz:index')), response['Location'])

        # Verify that cache has been updated for correct user
        self.assertEqual(('3', '4', unicode(course_id_x)), cache_utils.get_course_selection(self.user))

    def test_change_method_not_allowed(self):
        self.assertEqual(405, self.client.get(self._change_view()).status_code)

    def test_change_not_logged_in(self):
        self.logout()
        response = self.client.post(self._change_view(), {})
        self.assertEqual(302, response.status_code)
        self.assertEqual(
            'http://testserver{}?next={}'.format(
                settings.LOGIN_URL, reverse('biz:course_selection:change')
            ),
            response['Location']
        )

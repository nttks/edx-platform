"""
Tests for validators
"""
from mock import patch

from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
from biz.djangoapps.ga_contract.models import CONTRACT_TYPE_PF, CONTRACT_TYPE_OWNERS
from biz.djangoapps.ga_contract.tests.factories import ContractFactory, ContractDetailFactory
from biz.djangoapps.ga_manager.tests.factories import ManagerFactory
from biz.djangoapps.ga_organization.tests.factories import OrganizationFactory
from biz.djangoapps.util import validators
from biz.djangoapps.util.tests.testcase import BizTestBase
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


class ValidatorsTest(BizTestBase, ModuleStoreTestCase):
    """Test for Validators"""

    def setUp(self):
        super(ValidatorsTest, self).setUp()

        self.user = UserFactory.create()

        patcher_log = patch('biz.djangoapps.util.validators.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

    def _save_organization(self):
        return OrganizationFactory.create(
            org_name=get_random_string(8),
            org_code=get_random_string(8),
            creator_org=self.gacco_organization,
            created_by=self.user,
        )

    def _save_manager_for_platformer(self, org):
        return self._save_manager(org, [self.platformer_permission])

    def _save_manager_for_aggregator(self, org):
        return self._save_manager(org, [self.aggregator_permission])

    def _save_manager_for_director(self, org):
        return self._save_manager(org, [self.director_permission])

    def _save_manager(self, org, permissions):
        return ManagerFactory.create(
            org=org,
            user=self.user,
            permissions=permissions,
        )

    def _save_contract_for_pf(self, contractor_org, owner_org):
        return self._save_contract(CONTRACT_TYPE_PF[0], contractor_org, owner_org)

    def _save_contract_for_owners(self, contractor_org, owner_org):
        return self._save_contract(CONTRACT_TYPE_OWNERS[0], contractor_org, owner_org)

    def _save_contract(self, contract_type, contractor_org, owner_org):
        return ContractFactory.create(
            contract_name=get_random_string(8),
            contract_type=contract_type,
            invitation_code=get_random_string(8),
            contractor_organization=contractor_org,
            owner_organization=owner_org,
            created_by=self.user,
        )

    def _save_contract_detail(self, contract, course_id):
        return ContractDetailFactory.create(
            contract=contract,
            course_id=course_id,
        )

    def test_get_valid_organization(self):
        org = self._save_organization()
        valid_org = validators.get_valid_organization(org.id)
        self.assertEqual(org, valid_org)

    def test_get_valid_organization_when_org_not_found(self):
        invalid_org_id = 99999
        with self.assertRaises(ValidationError):
            validators.get_valid_organization(invalid_org_id)

    def test_get_valid_manager(self):
        org = self._save_organization()
        manager = self._save_manager_for_platformer(org)
        valid_manager = validators.get_valid_manager(self.user, org.id)
        self.assertEqual(manager, valid_manager)

    def test_get_valid_manager_when_manager_not_found(self):
        invalid_org_id = 99999
        with self.assertRaises(ValidationError):
            validators.get_valid_manager(self.user, invalid_org_id)

    def test_get_valid_contract_if_manager_is_aggregator(self):
        org = self._save_organization()
        org2 = self._save_organization()
        manager = self._save_manager_for_aggregator(org)
        contract = self._save_contract_for_owners(org, org2)
        valid_contract = validators.get_valid_contract(manager, contract.id)
        self.assertEqual(contract, valid_contract)

    def test_get_valid_contract_if_manager_is_director(self):
        org = self._save_organization()
        org2 = self._save_organization()
        manager = self._save_manager_for_director(org)
        contract = self._save_contract_for_pf(org, org2)
        valid_contract = validators.get_valid_contract(manager, contract.id)
        self.assertEqual(contract, valid_contract)

    def test_get_valid_contract_when_contract_not_found(self):
        org = self._save_organization()
        manager = self._save_manager_for_platformer(org)
        invalid_contract_id = 99999
        with self.assertRaises(ValidationError):
            validators.get_valid_contract(manager, invalid_contract_id)

    def test_get_valid_course_if_manager_is_director(self):
        org = self._save_organization()
        org2 = self._save_organization()
        manager = self._save_manager_for_director(org)
        contract = self._save_contract_for_pf(org, org2)
        course = CourseFactory.create()
        contract_detail = self._save_contract_detail(contract, course.id)
        valid_course = validators.get_valid_course(manager, contract, unicode(course.id))
        self.assertEqual(course, valid_course)

    def test_get_valid_course_when_course_not_found_in_modulestore(self):
        org = self._save_organization()
        org2 = self._save_organization()
        manager = self._save_manager_for_aggregator(org)
        contract = self._save_contract_for_owners(org, org2)
        invalid_course_id = 'invalid_course_id'
        with self.assertRaises(ValidationError):
            validators.get_valid_course(manager, contract, invalid_course_id)

    def test_get_valid_course_when_contract_detail_not_found(self):
        org = self._save_organization()
        org2 = self._save_organization()
        manager = self._save_manager_for_aggregator(org)
        contract = self._save_contract_for_owners(org, org2)
        course = CourseFactory.create()
        with self.assertRaises(ValidationError):
            validators.get_valid_course(manager, contract, unicode(course.id))

    def test_get_valid_course_when_contract_detail_duplicated(self):
        org = self._save_organization()
        org2 = self._save_organization()
        manager = self._save_manager_for_director(org)
        contract = self._save_contract_for_pf(org, org2)
        course = CourseFactory.create()
        contract_detail = self._save_contract_detail(contract, course.id)
        contract_detail2 = self._save_contract_detail(contract, course.id)
        validators.get_valid_course(manager, contract, unicode(course.id))
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has duplicated course details with the same course_id. contract_id={}, course_id={}".format(
                manager.id, contract.id, unicode(course.id)))

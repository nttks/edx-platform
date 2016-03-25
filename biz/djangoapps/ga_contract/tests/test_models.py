
import ddt

from student.tests.factories import UserFactory

from biz.djangoapps.ga_contract.models import (
    CONTRACT_TYPE_PF, CONTRACT_TYPE_OWNERS, CONTRACT_TYPE_OWNER_SERVICE, CONTRACT_TYPE_GACCO_SERVICE
)
from biz.djangoapps.ga_contract.tests.factories import ContractFactory
from biz.djangoapps.util.tests.testcase import BizTestBase


@ddt.ddt
class ContractTest(BizTestBase):

    @ddt.data(CONTRACT_TYPE_PF[0], CONTRACT_TYPE_OWNERS[0], CONTRACT_TYPE_OWNER_SERVICE[0])
    def test_is_spoc_available_true(self, contract_type):
        contract = ContractFactory.create(
            contractor_organization=self.gacco_organization,
            owner_organization=self.gacco_organization,
            contract_type=contract_type,
            created_by=UserFactory.create()
        )
        self.assertTrue(contract.is_spoc_available)

    @ddt.data(CONTRACT_TYPE_GACCO_SERVICE[0],)
    def test_is_spoc_available_false(self, contract_type):
        contract = ContractFactory.create(
            contractor_organization=self.gacco_organization,
            owner_organization=self.gacco_organization,
            contract_type=contract_type,
            created_by=UserFactory.create()
        )
        self.assertFalse(contract.is_spoc_available)

from datetime import timedelta
import factory

from factory.django import DjangoModelFactory

from biz.djangoapps.ga_contract.models import AdditionalInfo, Contract, ContractDetail, CONTRACT_TYPE_PF
from biz.djangoapps.util.datetime_utils import timezone_today


class ContractFactory(DjangoModelFactory):
    """Factory for the Contract model"""
    FACTORY_FOR = Contract

    contract_name = 'test contract'
    contract_type = CONTRACT_TYPE_PF[0]
    invitation_code = factory.Sequence(lambda n: 'invitation{0}'.format(n))
    start_date = timezone_today() - timedelta(days=1)
    end_date = timezone_today() + timedelta(days=1)


class ContractDetailFactory(DjangoModelFactory):
    """Factory for the ContractDetail model"""
    FACTORY_FOR = ContractDetail


class AdditionalInfoFactory(DjangoModelFactory):
    """Factory for the AdditionalInfo model"""
    FACTORY_FOR = AdditionalInfo

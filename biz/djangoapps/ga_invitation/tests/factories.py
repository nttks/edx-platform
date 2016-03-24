import factory

from factory.django import DjangoModelFactory

from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting, ContractRegister


class ContractRegisterFactory(DjangoModelFactory):
    """Factory for the ContractRegister model"""
    FACTORY_FOR = ContractRegister


class AdditionalInfoSettingFactory(DjangoModelFactory):
    """Factory for the AdditionalInfoSetting model"""
    FACTORY_FOR = AdditionalInfoSetting

    value = factory.Sequence(lambda n: 'value{0}'.format(n))

import factory

from factory.django import DjangoModelFactory

from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting, ContractRegister


class ContractRegisterFactory(DjangoModelFactory):
    """Factory for the ContractRegister model"""
    class Meta(object):
        model = ContractRegister


class AdditionalInfoSettingFactory(DjangoModelFactory):
    """Factory for the AdditionalInfoSetting model"""
    class Meta(object):
        model = AdditionalInfoSetting

    value = factory.Sequence(lambda n: 'value{0}'.format(n))

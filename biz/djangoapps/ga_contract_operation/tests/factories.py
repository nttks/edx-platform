
import factory
from factory.django import DjangoModelFactory

from student.tests.factories import UserFactory

from biz.djangoapps.ga_contract_operation.models import ContractMail, ContractTaskHistory, ContractTaskTarget, StudentRegisterTaskTarget


class ContractTaskHistoryFactory(DjangoModelFactory):
    """Factory for the ContractTaskHistory model"""

    class Meta(object):
        model = ContractTaskHistory

    requester = factory.SubFactory(UserFactory)


class ContractTaskTargetFactory(DjangoModelFactory):
    """Factory for the ContractTaskTarget model"""

    class Meta(object):
        model = ContractTaskTarget


class StudentRegisterTaskTargetFactory(DjangoModelFactory):
    """Factory for the StudentRegisterTaskTarget model"""

    class Meta(object):
        model = StudentRegisterTaskTarget


class ContractMailFactory(DjangoModelFactory):
    """Factory for the ContractMail model"""

    class Meta(object):
        model = ContractMail

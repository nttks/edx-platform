
import factory
from factory.django import DjangoModelFactory

from student.tests.factories import UserFactory

from biz.djangoapps.ga_contract_operation.models import (
    ContractMail, ContractReminderMail,
    ContractTaskHistory, ContractTaskTarget, StudentRegisterTaskTarget, StudentUnregisterTaskTarget,
)


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


class StudentUnregisterTaskTargetFactory(DjangoModelFactory):
    """Factory for the StudentUnregisterTaskTarget model"""

    class Meta(object):
        model = StudentUnregisterTaskTarget


class ContractMailFactory(DjangoModelFactory):
    """Factory for the ContractMail model"""

    class Meta(object):
        model = ContractMail


class ContractReminderMailFactory(DjangoModelFactory):
    """Factory for the ContractReminderMail model"""

    class Meta(object):
        model = ContractReminderMail

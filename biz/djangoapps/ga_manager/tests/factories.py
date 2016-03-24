
import factory
from factory.django import DjangoModelFactory

from biz.djangoapps.ga_manager.models import Manager, ManagerPermission


class ManagerPermissionFactory(DjangoModelFactory):
    """Factory for the ManagerPermission model"""
    FACTORY_FOR = ManagerPermission


class ManagerFactory(DjangoModelFactory):
    """Factory for the Manager model"""
    FACTORY_FOR = Manager

    @factory.post_generation
    def permissions(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for permission in extracted:
                self.manager_permissions.add(permission)

from factory.django import DjangoModelFactory

from biz.djangoapps.ga_organization.models import Organization


class OrganizationFactory(DjangoModelFactory):
    """Factory for the Organization model"""
    FACTORY_FOR = Organization

    org_name = 'test organization'

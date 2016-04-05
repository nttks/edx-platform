from factory.django import DjangoModelFactory

from biz.djangoapps.ga_organization.models import Organization


class OrganizationFactory(DjangoModelFactory):
    """Factory for the Organization model"""
    class Meta(object):
        model = Organization

    org_name = 'test organization'

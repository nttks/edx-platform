from factory.django import DjangoModelFactory

from openedx.core.djangoapps.ga_ratelimitbackend.models import TrustedClient


class TrustedClientFactory(DjangoModelFactory):
    """
    Factory for the TrustedClient model.
    """
    FACTORY_FOR = TrustedClient

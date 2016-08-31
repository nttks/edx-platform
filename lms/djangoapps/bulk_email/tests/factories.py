"""
Provides factories for bulk_email models.
"""
from factory.django import DjangoModelFactory

from bulk_email.models import Optout


class OptoutFactory(DjangoModelFactory):
    class Meta(object):
        model = Optout


from factory.django import DjangoModelFactory

from biz.djangoapps.ga_login.models import BizUser


class BizUserFactory(DjangoModelFactory):
    """Factory for the BizUser model"""

    class Meta(object):
        model = BizUser

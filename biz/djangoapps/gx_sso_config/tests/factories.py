from factory.django import DjangoModelFactory
from biz.djangoapps.gx_sso_config.models import SsoConfig

class SsoConfigFactory(DjangoModelFactory):
    class Meta(object):
        model = SsoConfig

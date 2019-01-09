from factory.django import DjangoModelFactory
from biz.djangoapps.gx_register_api.models import APIContractMail

class APIContractMailFactory(DjangoModelFactory):
    class Meta(object):
        model = APIContractMail
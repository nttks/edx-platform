from factory.django import DjangoModelFactory
from biz.djangoapps.gx_register_api.models import APIContractMail, APIGatewayKey

class APIContractMailFactory(DjangoModelFactory):
    class Meta(object):
        model = APIContractMail


class APIGatewayKeyFactory(DjangoModelFactory):
    class Meta(object):
        model = APIGatewayKey
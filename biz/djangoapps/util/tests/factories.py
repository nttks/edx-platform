"""Base factory for BIZ_MONGO """

from django.conf import settings
from factory import Factory


class BizMongoFactory(Factory):

    init_args = []

    @classmethod
    def _create(cls, target_class, *args, **kwargs):
        _init_args = kwargs['init_args']
        del kwargs['init_args']

        if _init_args:
            instance = target_class(*[None for _ in _init_args])
        else:
            instance = target_class()

        return instance.set_documents(kwargs)

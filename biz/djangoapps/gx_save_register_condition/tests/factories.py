from factory.django import DjangoModelFactory

from biz.djangoapps.gx_save_register_condition.models import ParentCondition, ChildCondition, ReflectConditionTaskHistory


class ParentConditionFactory(DjangoModelFactory):
    """Factory for the ParentCondition model"""

    class Meta(object):
        model = ParentCondition


class ChildConditionFactory(DjangoModelFactory):
    """Factory for the ChildCondition model"""

    class Meta(object):
        model = ChildCondition


class ReflectConditionTaskHistoryFactory(DjangoModelFactory):
    """Factory for the ReflectConditionTaskHistory model"""

    class Meta(object):
        model = ReflectConditionTaskHistory


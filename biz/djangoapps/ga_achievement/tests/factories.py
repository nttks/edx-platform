"""Factories for achievement"""
from factory.django import DjangoModelFactory

from biz.djangoapps.ga_achievement.models import ScoreBatchStatus
from biz.djangoapps.ga_achievement.score_store import ScoreStore
from biz.djangoapps.util.tests.factories import BizMongoFactory


class ScoreFactory(BizMongoFactory):

    FACTORY_FOR = ScoreStore

    init_args = ['contract_id', 'course_id']


class ScoreBatchStatusFactory(DjangoModelFactory):
    """Factory for the ContractDetail model"""
    FACTORY_FOR = ScoreBatchStatus

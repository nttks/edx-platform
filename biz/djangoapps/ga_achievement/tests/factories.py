"""Factories for achievement"""
from factory.django import DjangoModelFactory

from biz.djangoapps.ga_achievement.models import PlaybackBatchStatus, ScoreBatchStatus
from biz.djangoapps.ga_achievement.achievement_store import ScoreStore, PlaybackStore
from biz.djangoapps.util.tests.factories import BizMongoFactory


class ScoreFactory(BizMongoFactory):
    """Factory for the ScoreStore model"""
    class Meta(object):
        model = ScoreStore

    init_args = ['contract_id', 'course_id']


class PlaybackFactory(BizMongoFactory):
    """Factory for the PlaybackStore model"""
    class Meta(object):
        model = PlaybackStore

    init_args = ['course_id', 'target_id']


class ScoreBatchStatusFactory(DjangoModelFactory):
    """Factory for the ScoreBatchStatus model"""
    class Meta(object):
        model = ScoreBatchStatus


class PlaybackBatchStatusFactory(DjangoModelFactory):
    """Factory for the PlaybackBatchStatus model"""
    class Meta(object):
        model = PlaybackBatchStatus

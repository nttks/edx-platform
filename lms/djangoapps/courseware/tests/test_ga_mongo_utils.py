from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings

from lms.djangoapps.courseware.ga_mongo_utils import PlaybackFinishConnection


def _playback_finish_store_config():
    """
    Replace db name to test_biz. db that begin with test_ will be removed by
    scripts/delete-mongo-test-dbs.js in the end of the test process.
    """
    if hasattr(settings, 'PLAYBACK_FINISH_MONGO'):
        _playback_finish_mongo = settings.PLAYBACK_FINISH_MONGO.copy()
        for key, conf in _playback_finish_mongo.items():
            _playback_finish_mongo[key]['db'] = 'test_edxapp'
        return _playback_finish_mongo
    else:
        return None


class PlaybackFinishTestBase(TestCase):
    PLAYBACK_FINISH_MONGO = _playback_finish_store_config()

    def setUp(self):
        if self.PLAYBACK_FINISH_MONGO:
            settings_override = override_settings(PLAYBACK_FINISH_MONGO=self.PLAYBACK_FINISH_MONGO)
            settings_override.__enter__()
            self.addCleanup(settings_override.__exit__, None, None, None)

            self.addCleanup(self._drop_mongo_collections)

        super(PlaybackFinishTestBase, self).setUp()

    def _drop_mongo_collections(self):
        for config in settings.PLAYBACK_FINISH_MONGO.values():
            PlaybackFinishConnection(**config).database.drop_collection(config['collection'])
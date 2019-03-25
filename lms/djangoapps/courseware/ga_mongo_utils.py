"""
MongoDB add mongodb operation method by the need.
"""
import logging
import pymongo

from django.conf import settings

from mongodb_proxy import MongoProxy

log = logging.getLogger(__name__)


class PlaybackFinishConnection(object):
    def __init__(
        self, db, collection, host, port=27017, tz_aware=True, user=None, password=None,
        retry_wait_time=0.1, **kwargs
    ):
        if kwargs.get('replicaSet') is None:
            kwargs.pop('replicaSet', None)
            mongo_class = pymongo.MongoClient
        else:
            mongo_class = pymongo.MongoReplicaSetClient

        _client = mongo_class(
            host=host,
            port=port,
            tz_aware=tz_aware,
            **kwargs
        )
        self.database = MongoProxy(
            pymongo.database.Database(_client, db),
            wait_time=retry_wait_time
        )
        if user is not None and password is not None:
            self.database.authenticate(user, password)


class PlaybackFinishConnectionStore(object):
    def __init__(self, store_config):
        self._db_connection = PlaybackFinishConnection(**store_config)
        self._db = self._db_connection.database
        self._collection = self._db[store_config['collection']]


class PlaybackFinishStore(PlaybackFinishConnectionStore):
    def __init__(self):
        self.store_config = settings.PLAYBACK_FINISH_MONGO['playback_finish_connection']
        super(PlaybackFinishStore, self).__init__(self.store_config)

    def find_record(self, user_id, course_id):
        return list(self._collection.find({"user_id": user_id, "course_id": course_id}))

    def find_data(self, user_id, course_id, block_id):
        return list(self._collection.find({
            "user_id": user_id, "course_id": course_id, "module_list.block_id": block_id}))

    def find_module(self, user_id, course_id, block_id):
        result = None
        find_result = self.find_data(user_id, course_id, block_id)
        if find_result:
            for module in find_result[0]['module_list']:
                if module['block_id'] == block_id:
                    result = module
                    break
        return result

    def find_status_true_data(self, user_id, course_id, block_id):
        return list(self._collection.find({
            "user_id": user_id, "course_id": course_id, "module_list": {'$elemMatch': {'block_id': block_id,
                                                                                       'status': True}}}))

    def set_record(self, posts):
        """
        Data insert into MongoDB

        :param posts: nanikana
        :return: _id
        """
        return self._collection.insert(posts)

    def update_record(self, find_result, updates):
        return self._collection.update(find_result, updates)

    def find_status_data_by_course_id(self, course_id):
        return list(self._collection.find({"course_id": course_id}))

    def find_status_false_data(self, user_id, course_id, block_id):
        return list(self._collection.find({
            "user_id": user_id, "course_id": course_id, "module_list": {'$elemMatch': {'block_id': block_id,
                                                                                       'status': False}}}))
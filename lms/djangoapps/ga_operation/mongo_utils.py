"""
MongoDB operation for GaOperation.
Add mongodb operation method by the need.
"""
from collections import OrderedDict
import logging

from django.conf import settings

from mongodb_proxy import autoretry_read
from mongodb_proxy import MongoProxy
from pymongo import ASCENDING
import pymongo

log = logging.getLogger(__name__)


class GaOperationMongoConnection(object):
    def __init__(
        self, db, collection, host, port=27017, tz_aware=True, user=None, password=None,
        retry_wait_time=0.1, **kwargs
    ):
        """
        Create & open the connection, authenticate, and provide pointers to the collections
        """
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


class GaOperationStore(object):
    """
    Class for a MongoDB operation
    """

    def __init__(self, store_config):
        """
        Referring to the MongoDB Connection of GaOperationMongoConnection.
        Create a collection for MongoDB.

        :param store_config: setting of mongodb
        :return:
        """
        try:
            self._db_connection = GaOperationMongoConnection(**store_config)
            self._db = self._db_connection.database
            self._collection = self._db[store_config['collection']]
        except Exception as e:
            log.error("Error occurred while connecting MongoDB: %s" % e)
            raise

    @autoretry_read()
    def get_documents(self, conditions={}, excludes={'_id': False}, sort_column='_id', sort=ASCENDING):
        """
        Get the data of MongoDB

        :param conditions: MongoDB Condition for Dict
        :param excludes: _id flag of exclusion
        :param sort_column: Keys to sort
        :param sort: Sorting method
        :return: Conversion of pymongo.cursor.Cursor type to list
        """
        try:
            return list(
                self._collection.find(conditions, excludes, as_class=OrderedDict).sort(sort_column, sort)
            )
        except Exception as e:
            log.error("Error occurred while find MongoDB: %s" % e)
            raise

    @autoretry_read()
    def get_count(self, conditions={}):
        """
        Get the count of list

        :param conditions: MongoDB Condition for Dict
        :return: int
        """
        try:
            return self._collection.find(conditions).count(True)
        except Exception as e:
            log.error("Error occurred while get count MongoDB: %s" % e)
            raise


class CommentStore(GaOperationStore):
    def __init__(self):
        self._store_config = settings.GA_OPERATION_MONGO['comment']
        super(CommentStore, self).__init__(self._store_config)
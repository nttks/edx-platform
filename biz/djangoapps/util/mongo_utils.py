"""
MongoDB operation for Biz.
Add mongodb operation method by the need.
"""
from bson.code import Code
from collections import OrderedDict
from datetime import datetime
import logging
import pytz
from mongodb_proxy import autoretry_read
from pymongo import ASCENDING

from biz.djangoapps.util.biz_mongo_connection import BizMongoConnection

log = logging.getLogger(__name__)

DEFAULT_DATETIME = datetime(9999, 1, 1, 0, 0, 0, 0, tzinfo=pytz.utc)


class BizStore(object):
    """
    Class for a MongoDB operation
    """

    def __init__(self, store_config, key_conditions={}, key_index_columns=[]):
        """
        Referring to the MongoDB Connection of BizMongoConnection.
        Create a collection for MongoDB.

        :param store_config: setting of mongodb
        :param key_conditions: dict of conditions
        :param key_index_columns: list of index column
        :return:
        """
        try:
            self._db_connection = BizMongoConnection(**store_config)
            self._db = self._db_connection.database
            self._collection = self._db[store_config['collection']]
        except Exception as e:
            log.error("Error occurred while connecting MongoDB: %s" % e)
            raise
        self._key_conditions = key_conditions
        self._key_index_columns = key_index_columns

    @autoretry_read()
    def get_document(self, conditions={}, excludes={'_id': False}):
        """
        Get the data of MongoDB

        :param conditions: MongoDB Condition for Dict
        :param excludes: _id flag of exclusion
        :return: Conversion of pymongo.cursor.Cursor type to list
        """
        conditions.update(self._key_conditions)
        try:
            return self._collection.find_one(conditions, excludes, as_class=OrderedDict)
        except Exception as e:
            log.error("Error occurred while find MongoDB: %s" % e)
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
        conditions.update(self._key_conditions)
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
        conditions.update(self._key_conditions)
        try:
            return self._collection.find(conditions).count(True)
        except Exception as e:
            log.error("Error occurred while get count MongoDB: %s" % e)
            raise

    @autoretry_read()
    def aggregate(self, key_field_name, value_field_name, conditions={}):
        """
        Aggregate the amount by grouping the specified key

        :param key_field_name: field name for grouping
        :param value_field_name: field name for aggregation
        :param conditions: dict for conditions
        :return: dict
            e.g.)
            {
                u'key1': 100.0,
                u'key2': 200.0,
                u'key3': 300.0,
            }
        """
        mapper = Code(u'''
            function() {{
                emit(
                    this.{key_field_name},
                    this.{value_field_name}
                );
            }}
        ''').format(
            key_field_name=key_field_name,
            value_field_name=value_field_name,
        )
        reducer = Code(u'''
            function(key, values) {
                var sum = 0;
                values.forEach(function(value) {
                    sum += value;
                });
                return sum;
            }
        ''')
        conditions.update(self._key_conditions)
        try:
            results = list(self._collection.map_reduce(mapper, reducer, 'results', query=conditions).find())
            return dict([(result['_id'], result['value']) for result in results])
        except Exception as e:
            log.error("Error occurred while processing map reduce to MongoDB: %s" % e)
            raise

    @autoretry_read()
    def set_documents(self, posts):
        """
        Data insert into MongoDB

        :param posts: dict data for inserting
        :return: _id
        """
        try:
            return self._collection.insert(posts, check_keys=False)
        except Exception as e:
            log.error("Error occurred while insert MongoDB: %s" % e)
            raise

    @autoretry_read()
    def ensure_indexes(self, index_columns=[]):
        """
        Add Index

        :param index_columns: list type ex)index_columns['column1', 'column2']
        :return:
        """
        indexes = self._key_index_columns[:]
        indexes.extend(index_columns)
        try:
            return [self._collection.create_index([(index, ASCENDING)]) for index in indexes]
        except Exception as e:
            log.error("Error occurred while ensure indexes MongoDB: %s" % e)
            raise

    @autoretry_read()
    def drop_indexes(self):
        """
        Drop Index

        :return:
        """
        self._collection.drop_indexes()

    @autoretry_read()
    def remove_documents(self, conditions={}):
        """
        Remove Documents

        :param conditions: MongoDB Condition for Dict
        :return: None
        """
        conditions.update(self._key_conditions)
        try:
            return self._collection.remove(conditions)
        except Exception as e:
            log.error("Error occurred while remove documents MongoDB: %s" % e)
            raise

"""
Tests for biz_mongo_connection
"""
from pymongo.errors import OperationFailure

from biz.djangoapps.util.biz_mongo_connection import BizMongoConnection
from biz.djangoapps.util.tests.testcase import TestCase

from mongodb_proxy import MongoProxy


class BizMongoConnectionTest(TestCase):

    def set_config(self):
        self._store_config = {
            'db': 'test',
            'collection': 'test',
            'ssl': False,
            'host': 'localhost',
            'user': 'edxapp',
            'password': None,
            'port': 27017
        }

    def test_biz_mongo_connection(self):
        self.set_config()
        self._db_connection = BizMongoConnection(**self._store_config)

        str_database = self._db_connection.database.__str__()
        self.assertIsInstance(self._db_connection.database, MongoProxy)
        self.assertTrue(self._store_config['host'] in str_database)
        self.assertTrue(str(self._store_config['port']) in str_database)
        self.assertTrue(self._store_config['db'] in str_database)

    def user_password_biz_mongo_connection(self):
        self.set_config()
        self._store_config['db'] = 'score'
        self._store_config['password'] = 'password'
        self._db_connection = BizMongoConnection(**self._store_config)

    def test_user_password_biz_mongo_connection_exception(self):
        with self.assertRaises(OperationFailure):
            self.user_password_biz_mongo_connection()

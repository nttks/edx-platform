"""
Tests for mongo_utils
"""
from collections import OrderedDict
import copy
from mock import MagicMock

from pymongo.errors import AutoReconnect

from biz.djangoapps.util.mongo_utils import BizStore
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from biz.djangoapps.ga_achievement.score_store import (
    SCORE_STORE_FIELD_CONTRACT_ID, SCORE_STORE_FIELD_COURSE_ID, SCORE_STORE_FIELD_NAME, SCORE_STORE_FIELD_USERNAME,
    SCORE_STORE_FIELD_EMAIL, SCORE_STORE_FIELD_STUDENT_STATUS
)


class BizStoreTest(BizStoreTestBase):

    def _setup_normal_config_data(self):
        self._test_store_config = {
            'db': 'test',
            'collection': 'test',
            'ssl': False,
            'host': 'localhost',
            'user': 'edxapp',
            'password': None,
            'port': 27017
        }

    def _set_documents(self):
        self._documents = []

        od1 = OrderedDict()
        od1[SCORE_STORE_FIELD_CONTRACT_ID] = 1
        od1[SCORE_STORE_FIELD_COURSE_ID] = 'test'
        od1[SCORE_STORE_FIELD_NAME] = 'test1'
        od1[SCORE_STORE_FIELD_USERNAME] = 'user_test1'
        od1[SCORE_STORE_FIELD_EMAIL] = 'test1@example.com'

        od2 = OrderedDict()
        od2[SCORE_STORE_FIELD_CONTRACT_ID] = 1
        od2[SCORE_STORE_FIELD_COURSE_ID] = 'test'
        od2[SCORE_STORE_FIELD_NAME] = 'test2'
        od2[SCORE_STORE_FIELD_USERNAME] = 'user_test1'
        od2[SCORE_STORE_FIELD_EMAIL] = 'test2@example.com'

        self._documents.append(od1)
        self._documents.append(od2)

    def _drop_mongo_collection(self):
        self._bizstore._collection.drop()

    def set_normal(self):
        self._setup_normal_config_data()
        self._set_documents()

        self.key_conditions = {
            SCORE_STORE_FIELD_CONTRACT_ID: 1,
            SCORE_STORE_FIELD_COURSE_ID: 'test'
        }
        self.key_index_columns = [SCORE_STORE_FIELD_CONTRACT_ID, SCORE_STORE_FIELD_COURSE_ID]

    def test_bizstore(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self.assertEqual(self._bizstore._key_conditions, self.key_conditions)
        self.assertEqual(self._bizstore._key_index_columns, self.key_index_columns)

        self._drop_mongo_collection()

    def test_set_get_documents(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self._bizstore.set_documents(self._documents)
        get_documents = self._bizstore.get_documents()

        for i, item in enumerate(get_documents):
            self.assertEqual(self._documents[i][SCORE_STORE_FIELD_NAME], item[SCORE_STORE_FIELD_NAME])
            self.assertEqual(self._documents[i][SCORE_STORE_FIELD_USERNAME], item[SCORE_STORE_FIELD_USERNAME])
            self.assertEqual(self._documents[i][SCORE_STORE_FIELD_EMAIL], item[SCORE_STORE_FIELD_EMAIL])

        self._drop_mongo_collection()

    def test_get_count(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        self._bizstore.set_documents(self._documents)
        count_documents = self._bizstore.get_count()

        count_set_documents = len(self._documents)
        self.assertEqual(count_set_documents, count_documents)

        self._drop_mongo_collection()

    def test_get_fields(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        self._bizstore.set_documents(self._documents)
        documents = self._bizstore.get_documents()
        fields = self._bizstore.get_fields(documents)

        for field in fields:
            self.assertIn(field, self._documents[0].keys())

        self._drop_mongo_collection()

    def test_ensure_indexes(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        self._bizstore.ensure_indexes([SCORE_STORE_FIELD_USERNAME])
        indexes = self._bizstore._collection.index_information()
        index_key = SCORE_STORE_FIELD_USERNAME + '_1'
        self.assertIn(index_key, indexes.keys())

        self._drop_mongo_collection()

    def test_drop_indexes(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        self._bizstore.ensure_indexes([SCORE_STORE_FIELD_USERNAME])
        indexes = self._bizstore._collection.index_information()
        index_key = SCORE_STORE_FIELD_USERNAME + '_1'
        self.assertIn(index_key, indexes.keys())

        self._bizstore.drop_indexes()
        not_indexes = self._bizstore._collection.index_information()
        self.assertNotIn(index_key, not_indexes.keys())

        self._drop_mongo_collection()

    def test_remove_documents(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self._bizstore.set_documents(self._documents)
        get_documents = self._bizstore.get_documents()

        for i, item in enumerate(get_documents):
            self.assertEqual(self._documents[i][SCORE_STORE_FIELD_NAME], item[SCORE_STORE_FIELD_NAME])
            self.assertEqual(self._documents[i][SCORE_STORE_FIELD_USERNAME], item[SCORE_STORE_FIELD_USERNAME])
            self.assertEqual(self._documents[i][SCORE_STORE_FIELD_EMAIL], item[SCORE_STORE_FIELD_EMAIL])

        self._bizstore.remove_documents()
        get_remove_documents = self._bizstore.get_documents()
        self.assertEqual(0, len(get_remove_documents))

        self._drop_mongo_collection()

    def _wrong_setup_config_data(self):
        self._test_store_config = {
            'db': 'test',
            'collection': 'test',
            'ssl': False,
            'host': 'localhost',
            'user': 'edxapp',
            'password': None,
            'port': 0
        }

    def wrong_setup(self):
        self._wrong_setup_config_data()
        self._set_documents()

        self.key_conditions = {
            SCORE_STORE_FIELD_CONTRACT_ID: 1,
            SCORE_STORE_FIELD_COURSE_ID: 'test'
        }
        self.key_index_columns = [SCORE_STORE_FIELD_CONTRACT_ID, SCORE_STORE_FIELD_COURSE_ID]

    def wrong_bizstore(self):
        self.wrong_setup()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self.assertEqual(self._bizstore._key_conditions, self.key_conditions)
        self.assertEqual(self._bizstore._key_index_columns, self.key_index_columns)

        self._drop_mongo_collection()

    def wrong_set_documents(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        cp_documents = copy.copy(self._documents)
        self._documents.append(cp_documents)

        self._bizstore.set_documents(self._documents)
        get_documents = self._bizstore.get_documents()

        for i, item in enumerate(get_documents):
            self.assertEqual(self._documents[i][SCORE_STORE_FIELD_NAME], item[SCORE_STORE_FIELD_NAME])
            self.assertEqual(self._documents[i][SCORE_STORE_FIELD_USERNAME], item[SCORE_STORE_FIELD_USERNAME])
            self.assertEqual(self._documents[i][SCORE_STORE_FIELD_EMAIL], item[SCORE_STORE_FIELD_EMAIL])

        self._drop_mongo_collection()

    def wrong_get_count(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        self._bizstore.set_documents(self._documents)
        count_documents = self._bizstore.get_count()

        count_set_documents = len(self._documents)
        self.assertEqual(count_set_documents, count_documents)

        self._drop_mongo_collection()

    def test_dict_get_fields(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        dict_documents = {SCORE_STORE_FIELD_STUDENT_STATUS: 'TEST'}
        self._bizstore.set_documents(dict_documents)
        documents = self._bizstore.get_documents()
        fields = self._bizstore.get_fields(documents)

        for field in fields:
            self.assertIn(field, self._documents[0].keys())

        self._drop_mongo_collection()

    def test_zero_get_fields(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        documents = OrderedDict()
        fields = self._bizstore.get_fields(documents)

        self.assertIs(0, len(fields))

    def test_bizstore_raise_exception(self):
        with self.assertRaises(Exception):
            self.wrong_bizstore()

    def test_set_documents_raise_exception(self):
        with self.assertRaises(Exception):
            self.wrong_set_documents()

    def test_get_documents_exception(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self._bizstore._collection.find = MagicMock(side_effect=_Exception())
        with self.assertRaises(_Exception):
            self._bizstore.get_documents()

        self.assertEqual(1, self._bizstore._collection.find.call_count)

    def test_get_documents_auto_retry(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self._bizstore._collection.find = MagicMock(side_effect=AutoReconnect())
        with self.assertRaises(AutoReconnect):
            self._bizstore.get_documents()

        # Verify that autoretry_read decorator has been applied.
        self.assertEqual(5, self._bizstore._collection.find.call_count)


class _Exception(Exception):
    """Exception for exception-based test case"""
    pass

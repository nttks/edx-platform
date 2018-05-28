"""
Tests for mongo_utils
"""
import copy
import random
from collections import OrderedDict
from ddt import data, ddt, unpack
from mock import MagicMock

from django.test.utils import override_settings
from pymongo.errors import AutoReconnect

from biz.djangoapps.util.mongo_utils import BizStore
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from biz.djangoapps.ga_achievement.achievement_store import ScoreStore


@ddt
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
        od1[ScoreStore.FIELD_CONTRACT_ID] = 1
        od1[ScoreStore.FIELD_COURSE_ID] = 'test'
        od1[ScoreStore.FIELD_LOGIN_CODE] = 'test_login_code1'
        od1[ScoreStore.FIELD_FULL_NAME] = 'test1'
        od1[ScoreStore.FIELD_USERNAME] = 'user_test1'
        od1[ScoreStore.FIELD_EMAIL] = 'test1@example.com'

        od2 = OrderedDict()
        od2[ScoreStore.FIELD_CONTRACT_ID] = 1
        od2[ScoreStore.FIELD_COURSE_ID] = 'test'
        od2[ScoreStore.FIELD_LOGIN_CODE] = 'test_login_code2'
        od2[ScoreStore.FIELD_FULL_NAME] = 'test2'
        od2[ScoreStore.FIELD_USERNAME] = 'user_test2'
        od2[ScoreStore.FIELD_EMAIL] = 'test2@example.com'

        self._documents.append(od1)
        self._documents.append(od2)

    def _drop_mongo_collection(self):
        self._bizstore._collection.drop()

    def set_normal(self):
        self._setup_normal_config_data()
        self._set_documents()

        self.key_conditions = {
            ScoreStore.FIELD_CONTRACT_ID: 1,
            ScoreStore.FIELD_COURSE_ID: 'test'
        }
        self.key_index_columns = [ScoreStore.FIELD_CONTRACT_ID, ScoreStore.FIELD_COURSE_ID]

    def test_bizstore(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self.assertEqual(self._bizstore._key_conditions, self.key_conditions)
        self.assertEqual(self._bizstore._key_index_columns, self.key_index_columns)

        self._drop_mongo_collection()

    def test_set_get_document(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self._bizstore.set_documents(self._documents)
        get_document = self._bizstore.get_document({ScoreStore.FIELD_FULL_NAME: 'test2'})

        self.assertEqual(self._documents[1][ScoreStore.FIELD_LOGIN_CODE], get_document[ScoreStore.FIELD_LOGIN_CODE])
        self.assertEqual(self._documents[1][ScoreStore.FIELD_FULL_NAME], get_document[ScoreStore.FIELD_FULL_NAME])
        self.assertEqual(self._documents[1][ScoreStore.FIELD_USERNAME], get_document[ScoreStore.FIELD_USERNAME])
        self.assertEqual(self._documents[1][ScoreStore.FIELD_EMAIL], get_document[ScoreStore.FIELD_EMAIL])

        self._drop_mongo_collection()

    @data(
        (0, 0, 2),
        (0, 1, 1),
        (1, 0, 1),
        (1, 1, 1),
        (2, 0, 0),
        (2, 1, 0),
    )
    @unpack
    def test_set_get_documents(self, offset, limit, expect_record_count):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self._bizstore.set_documents(self._documents)
        get_documents = self._bizstore.get_documents(offset=offset, limit=limit)

        for i, item in enumerate(get_documents):
            self.assertEqual(self._documents[i+offset][ScoreStore.FIELD_LOGIN_CODE], item[ScoreStore.FIELD_LOGIN_CODE])
            self.assertEqual(self._documents[i+offset][ScoreStore.FIELD_FULL_NAME], item[ScoreStore.FIELD_FULL_NAME])
            self.assertEqual(self._documents[i+offset][ScoreStore.FIELD_USERNAME], item[ScoreStore.FIELD_USERNAME])
            self.assertEqual(self._documents[i+offset][ScoreStore.FIELD_EMAIL], item[ScoreStore.FIELD_EMAIL])

        self.assertEqual(len(get_documents), expect_record_count)

        self._drop_mongo_collection()

    def test_get_count(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        self._bizstore.set_documents(self._documents)
        count_documents = self._bizstore.get_count()

        count_set_documents = len(self._documents)
        self.assertEqual(count_set_documents, count_documents)

        self._drop_mongo_collection()

    def test_ensure_indexes(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        self._bizstore.ensure_indexes([ScoreStore.FIELD_USERNAME])
        indexes = self._bizstore._collection.index_information()
        index_key = ScoreStore.FIELD_USERNAME + '_1'
        self.assertIn(index_key, indexes.keys())

        self._drop_mongo_collection()

    def test_drop_indexes(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        self._bizstore.ensure_indexes([ScoreStore.FIELD_USERNAME])
        indexes = self._bizstore._collection.index_information()
        index_key = ScoreStore.FIELD_USERNAME + '_1'
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
            self.assertEqual(self._documents[i][ScoreStore.FIELD_LOGIN_CODE], item[ScoreStore.FIELD_LOGIN_CODE])
            self.assertEqual(self._documents[i][ScoreStore.FIELD_FULL_NAME], item[ScoreStore.FIELD_FULL_NAME])
            self.assertEqual(self._documents[i][ScoreStore.FIELD_USERNAME], item[ScoreStore.FIELD_USERNAME])
            self.assertEqual(self._documents[i][ScoreStore.FIELD_EMAIL], item[ScoreStore.FIELD_EMAIL])

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
            ScoreStore.FIELD_CONTRACT_ID: 1,
            ScoreStore.FIELD_COURSE_ID: 'test'
        }
        self.key_index_columns = [ScoreStore.FIELD_CONTRACT_ID, ScoreStore.FIELD_COURSE_ID]

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
            self.assertEqual(self._documents[i][ScoreStore.FIELD_LOGIN_CODE], item[ScoreStore.FIELD_LOGIN_CODE])
            self.assertEqual(self._documents[i][ScoreStore.FIELD_FULL_NAME], item[ScoreStore.FIELD_FULL_NAME])
            self.assertEqual(self._documents[i][ScoreStore.FIELD_USERNAME], item[ScoreStore.FIELD_USERNAME])
            self.assertEqual(self._documents[i][ScoreStore.FIELD_EMAIL], item[ScoreStore.FIELD_EMAIL])

        self._drop_mongo_collection()

    def wrong_get_count(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)
        self._bizstore.set_documents(self._documents)
        count_documents = self._bizstore.get_count()

        count_set_documents = len(self._documents)
        self.assertEqual(count_set_documents, count_documents)

        self._drop_mongo_collection()

    def test_bizstore_raise_exception(self):
        with self.assertRaises(Exception):
            self.wrong_bizstore()

    def test_set_documents_raise_exception(self):
        with self.assertRaises(Exception):
            self.wrong_set_documents()

    def test_get_document_exception(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self._bizstore._collection.find_one = MagicMock(side_effect=_Exception())
        with self.assertRaises(_Exception):
            self._bizstore.get_document()

        self.assertEqual(1, self._bizstore._collection.find_one.call_count)

    def test_get_document_auto_retry(self):
        self.set_normal()
        self._bizstore = BizStore(self._test_store_config, self.key_conditions, self.key_index_columns)

        self._bizstore._collection.find_one = MagicMock(side_effect=AutoReconnect())
        with self.assertRaises(AutoReconnect):
            self._bizstore.get_document()

        # Verify that autoretry_read decorator has been applied.
        self.assertEqual(5, self._bizstore._collection.find_one.call_count)

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


class BizStoreAggregateTest(BizStoreTestBase):

    def setUp(self):
        super(BizStoreAggregateTest, self).setUp()
        self.test_store = BizStore(self.BIZ_MONGO.values()[0])
        self._create_data()

    def _create_data(self):
        self.insert_documents = [
            {'user': 'user1', 'gender': 'male', 'subject': 'math', 'score': 10},
            {'user': 'user1', 'gender': 'male', 'subject': 'science', 'score': 20},
            {'user': 'user2', 'gender': 'male', 'subject': 'math', 'score': 30},
            {'user': 'user2', 'gender': 'male', 'subject': 'science', 'score': 40},
            {'user': 'user3', 'gender': 'female', 'subject': 'math', 'score': 50},
            {'user': 'user3', 'gender': 'female', 'subject': 'science', 'score': 60},
        ]
        self.test_store.set_documents(self.insert_documents)

    def test_aggregate(self):
        summary = self.test_store.aggregate('subject', 'score')
        self.assertDictEqual({u'science': 120.0, u'math': 90.0}, summary)

    def test_aggregate_with_query(self):
        summary = self.test_store.aggregate('subject', 'score', {'gender': 'male'})
        self.assertDictEqual({u'science': 60.0, u'math': 40.0}, summary)

    def test_aggregate_exception(self):
        self.test_store._collection.aggregate = MagicMock(side_effect=_Exception())
        with self.assertRaises(_Exception):
            self.test_store.aggregate('subject', 'score')
        self.assertEqual(1, self.test_store._collection.aggregate.call_count)

    def test_aggregate_auto_retry(self):
        self.test_store._collection.aggregate = MagicMock(side_effect=AutoReconnect())
        with self.assertRaises(AutoReconnect):
            self.test_store.aggregate('subject', 'score')
        self.assertEqual(5, self.test_store._collection.aggregate.call_count)


@override_settings(AGGREGATE_FETCH_LIMIT=1)
class BizStoreAggregateSumTest(BizStoreTestBase):

    def setUp(self):
        super(BizStoreAggregateSumTest, self).setUp()
        self.test_store = BizStore(self.BIZ_MONGO.values()[0])
        self.test_store.set_documents([
            {'user': 'user1', 'gender': 'male', 'subject': 'math', 'score': 10},
            {'user': 'user1', 'gender': 'male', 'subject': 'science', 'score': 20},
            {'user': 'user2', 'gender': 'male', 'subject': 'math', 'score': 30},
            {'user': 'user2', 'gender': 'male', 'subject': 'science', 'score': 40},
            {'user': 'user3', 'gender': 'female', 'subject': 'math', 'score': 50},
            {'user': 'user3', 'gender': 'female', 'subject': 'science', 'score': 60},
        ])

    def test_aggregate_sum(self):
        self.assertDictEqual({
            u'science': 120.0,
            u'math': 90.0,
        }, self.test_store.aggregate_sum(['subject'], 'score'))

    def test_aggregate_sum_with_query(self):
        self.assertDictEqual({
            u'science': 60.0,
            u'math': 40.0,
        }, self.test_store.aggregate_sum(['subject'], 'score', {'gender': 'male'}))

    def test_aggregate_sum_exception(self):
        self.test_store._collection.aggregate = MagicMock(side_effect=_Exception())
        with self.assertRaises(_Exception):
            self.test_store.aggregate_sum(['subject'], 'score')
        self.assertEqual(1, self.test_store._collection.aggregate.call_count)

    def test_aggregate_sum_auto_retry(self):
        self.test_store._collection.aggregate = MagicMock(side_effect=AutoReconnect())
        with self.assertRaises(AutoReconnect):
            self.test_store.aggregate_sum(['subject'], 'score')
        self.assertEqual(5, self.test_store._collection.aggregate.call_count)

    def test_aggregate_sum_multiple(self):
        self.assertDictEqual({
            u'science___male': 60.0,
            u'science___female': 60.0,
            u'math___male': 40.0,
            u'math___female': 50.0,
        }, self.test_store.aggregate_sum(['subject', 'gender'], 'score'))

    def test_aggregate_sum_multiple_with_query(self):
        self.assertDictEqual({
            u'science___male': 40.0,
            u'science___female': 60.0,
            u'math___male': 30.0,
            u'math___female': 50.0,
        }, self.test_store.aggregate_sum(['subject', 'gender'], 'score', {'score': {'$gte': 30}}))


@ddt
@override_settings(AGGREGATE_FETCH_LIMIT=100)
class BizStoreAggregateSumLimitTest(BizStoreTestBase):

    def setUp(self):
        super(BizStoreAggregateSumLimitTest, self).setUp()
        self.test_store = BizStore(self.BIZ_MONGO.values()[0])

    @data(99, 100, 101, 199, 200, 201, 999, 1000, 1001)
    def test_aggregate_sum(self, user_count):
        subjects = ['math', 'science', 'geography']
        for s in subjects:
            self.test_store.set_documents([
                {
                    'user': 'user{}'.format(i),
                    'subject': s,
                    'score': random.randrange(100)
                } for i in range(user_count)
            ])
        self.assertEqual(user_count, len(self.test_store.aggregate_sum(['user'], 'score')))
        self.assertEqual(user_count * len(subjects), len(self.test_store.aggregate_sum(['user', 'subject'], 'score')))

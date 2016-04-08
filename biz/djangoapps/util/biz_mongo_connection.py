"""
Segregation of pymongo functions from the data modeling mechanisms for BizStore in mongo_utils.
"""
import pymongo

from mongodb_proxy import MongoProxy


class BizMongoConnection(object):
    """
    Segregation of pymongo functions from the data modeling mechanisms for BizStore in mongo_utils.
    """
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

"""
Tests for model of ratelimitbackend
"""

from django.core.cache import cache
from django.test import TestCase

from ..models import TrustedClient, KEY_TRUSTED_CLIENT_LIST
from .factories import TrustedClientFactory


class TrustedClientTest(TestCase):

    TEST_ADDRESS = '88.88.88.88'

    def setUp(self):
        TrustedClientFactory.create(ip_address=self.TEST_ADDRESS)

    def assertListAndCached(self, address_list):
        self.assertListEqual(address_list, TrustedClient.get_ip_address_list())
        self.assertListEqual(address_list, cache.get(KEY_TRUSTED_CLIENT_LIST))

    def test_get_ip_address_list_from_cache(self):
        self.assertIsNone(cache.get(KEY_TRUSTED_CLIENT_LIST))

        # First call
        self.assertListAndCached([self.TEST_ADDRESS])
        expired = cache._expire_info.get(cache.make_key(KEY_TRUSTED_CLIENT_LIST))

        # Second call
        self.assertListAndCached([self.TEST_ADDRESS])
        # Not be re-set in the cache
        self.assertEqual(expired, cache._expire_info.get(cache.make_key(KEY_TRUSTED_CLIENT_LIST)))

    def test_clear_cache_when_create(self):
        self.assertIsNone(cache.get(KEY_TRUSTED_CLIENT_LIST))

        # First call
        self.assertListAndCached([self.TEST_ADDRESS])
        expired = cache._expire_info.get(cache.make_key(KEY_TRUSTED_CLIENT_LIST))

        TrustedClientFactory.create(ip_address='111.111.111.111')

        # cache cleared
        self.assertIsNone(cache.get(KEY_TRUSTED_CLIENT_LIST))

        self.assertListAndCached([self.TEST_ADDRESS, '111.111.111.111'])
        self.assertNotEqual(expired, cache._expire_info.get(cache.make_key(KEY_TRUSTED_CLIENT_LIST)))

    def test_clear_cache_when_delete(self):
        self.assertIsNone(cache.get(KEY_TRUSTED_CLIENT_LIST))

        # First call
        self.assertListAndCached([self.TEST_ADDRESS])
        expired = cache._expire_info.get(cache.make_key(KEY_TRUSTED_CLIENT_LIST))

        TrustedClient.objects.get(ip_address=self.TEST_ADDRESS).delete()

        # cache cleared
        self.assertIsNone(cache.get(KEY_TRUSTED_CLIENT_LIST))

        self.assertListAndCached([])
        self.assertNotEqual(expired, cache._expire_info.get(cache.make_key(KEY_TRUSTED_CLIENT_LIST)))

"""
Tests for ratelimitbackend
"""
from mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from openedx.core.djangoapps.ga_ratelimitbackend.backends import RateLimitMixin


class RateLimitMixinTest(TestCase):

    def test_fields_default(self):
        self.assertEqual(5, RateLimitMixin().minutes)
        self.assertEqual(30, RateLimitMixin().requests)

    @override_settings(RATE_LIMIT_MINUTES=8, RATE_LIMIT_REQUESTS=88)
    def test_fields_override(self):
        self.assertEqual(8, RateLimitMixin().minutes)
        self.assertEqual(88, RateLimitMixin().requests)

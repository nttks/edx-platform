"""
Tests for hash utilities
"""
from django.test import TestCase

from biz.djangoapps.util import hash_utils


class HashUtilsTest(TestCase):
    """Test for hash utilities"""

    def test_get_course_with_course_key(self):
        self.assertEqual('13c779faa1efb6845af350f158c9f53203b21e8688204011087c5d037dc3caac', hash_utils.to_target_id(1))

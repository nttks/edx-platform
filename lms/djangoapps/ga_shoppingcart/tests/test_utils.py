
from django.test import TestCase
from django.test.utils import override_settings

from ..utils import get_tax


class UtilsTest(TestCase):

    @override_settings(PAYMENT_TAX=8)
    def test_get_tax(self):
        self.assertEqual(0, get_tax(0))
        self.assertEqual(0, get_tax(1))
        self.assertEqual(0, get_tax(12))
        self.assertEqual(1, get_tax(13))

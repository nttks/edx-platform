"""
Tests for json_utils
"""
import json

from django.utils.translation import ugettext_lazy as _

from biz.djangoapps.util import json_utils
from biz.djangoapps.util.tests.testcase import BizTestBase


class LazyEncoderTest(BizTestBase):

    def setUp(self):
        super(LazyEncoderTest, self).setUp()
        self.encoder = json_utils.LazyEncoder()

    def test_encode_promise(self):
        self.assertEqual('Test', self.encoder.default(_('Test')))

    def test_fallthrough(self):
        with self.assertRaises(TypeError):
            self.encoder.default(None)

        with self.assertRaises(TypeError):
            self.encoder.default({})

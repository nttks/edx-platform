"""
Tests for html_utils.py
"""

from unittest import TestCase

from openedx.core.lib import ga_html_utils as html_utils


class HtmlUtilsTest(TestCase):

    def test_get_circle_number(self):
        # from 1 to 5 are supported
        self.assertEqual('&#9312;', html_utils.get_circle_number(1))
        self.assertEqual('&#9313;', html_utils.get_circle_number(2))
        self.assertEqual('&#9314;', html_utils.get_circle_number(3))
        self.assertEqual('&#9315;', html_utils.get_circle_number(4))
        self.assertEqual('&#9316;', html_utils.get_circle_number(5))

        # unsupported
        with self.assertRaises(AttributeError):
            html_utils.get_circle_number(0)

        with self.assertRaises(AttributeError):
            html_utils.get_circle_number(6)

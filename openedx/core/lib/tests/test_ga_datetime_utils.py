"""
Tests for datetime_utils.py
"""
from datetime import datetime
import pytz
from unittest import TestCase

from django.test.utils import override_settings

from openedx.core.lib import ga_datetime_utils as datetime_utils


class DateTimeUtilsTest(TestCase):

    @override_settings(TIME_ZONE='Asia/Tokyo')
    def test_to_timezone(self):
        # naive
        self.assertEqual(
            datetime(2015, 12, 31, 15, 0, 0),
            datetime_utils.to_timezone(datetime(2015, 12, 31, 15, 0, 0))
        )
        # aware UTC
        self.assertEqual(
            datetime(2015, 12, 31, 15, 0, 0, tzinfo=pytz.utc),
            datetime_utils.to_timezone(datetime(2016, 1, 1, 0, 0, 0, tzinfo=pytz.timezone('Asia/Tokyo')))
        )

        self.assertEqual(
            datetime(2015, 12, 31, 15, 0, 0, tzinfo=pytz.utc),
            datetime_utils.to_timezone(datetime(2015, 12, 31, 15, 0, 0, tzinfo=pytz.utc), pytz.utc)
        )

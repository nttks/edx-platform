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

    def test_format_for_csv(self):
        with override_settings(TIME_ZONE='Asia/Tokyo'):
            # naive
            self.assertEqual(
                '2016-01-01 00:00:00.000000',
                datetime_utils.format_for_csv(datetime(2016, 1, 1, 0, 0, 0))
            )
            # aware
            self.assertEqual(
                '2016-01-01 00:00:00.000000 JST',
                datetime_utils.format_for_csv(datetime(2016, 1, 1, 0, 0, 0, tzinfo=pytz.timezone('Asia/Tokyo')))
            )
            self.assertEqual(
                '2016-01-01 09:00:00.000000 JST',
                datetime_utils.format_for_csv(datetime(2016, 1, 1, 0, 0, 0, tzinfo=pytz.utc))
            )

        with override_settings(TIME_ZONE='Europe/Paris'):
            # naive
            self.assertEqual(
                '2016-01-01 00:00:00.000000',
                datetime_utils.format_for_csv(datetime(2016, 1, 1, 0, 0, 0))
            )
            # aware
            self.assertEqual(
                '2015-12-31 16:00:00.000000 CET',
                datetime_utils.format_for_csv(datetime(2016, 1, 1, 0, 0, 0, tzinfo=pytz.timezone('Asia/Tokyo')))
            )
            self.assertEqual(
                '2016-01-01 01:00:00.000000 CET',
                datetime_utils.format_for_csv(datetime(2016, 1, 1, 0, 0, 0, tzinfo=pytz.utc))
            )

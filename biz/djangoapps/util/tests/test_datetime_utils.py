"""
Tests for datetime_utils
"""

from datetime import datetime, date
from mock import patch
import pytz

from django.test.utils import override_settings

from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.tests.testcase import BizTestBase


class DateTimeUtilsTest(BizTestBase):

    def setUp(self):
        from django.utils import timezone
        # _localtime is global property. Clear it because it may have been set by the other testcase.
        timezone._localtime = None
        super(DateTimeUtilsTest, self).setUp()

    @override_settings(TIME_ZONE='Asia/Tokyo')
    def test_timezone_now(self):
        _timezone = pytz.timezone('Asia/Tokyo')
        with patch(
            'django.utils.timezone.now',
            side_effect=lambda: datetime(2015, 12, 31, 15, 0, 0).replace(tzinfo=pytz.utc)
        ):
            now = datetime_utils.timezone_now()
            self.assertEqual(datetime(2016, 1, 1, 0, 0, 0, tzinfo=_timezone), now)
            self.assertEqual(_timezone, now.tzinfo)

    @override_settings(TIME_ZONE='Asia/Tokyo')
    def test_timezone_today(self):
        with patch(
            'django.utils.timezone.now',
            side_effect=lambda: datetime(2015, 12, 31, 15, 0, 0).replace(tzinfo=pytz.utc)
        ):
            self.assertEqual(date(2016, 1, 1), datetime_utils.timezone_today())

    @override_settings(TIME_ZONE='Asia/Tokyo')
    def test_timezone_timezone_yesterday(self):
        with patch(
            'django.utils.timezone.now',
            side_effect=lambda: datetime(2015, 12, 31, 15, 0, 0).replace(tzinfo=pytz.utc)
        ):
            self.assertEqual(date(2015, 12, 31), datetime_utils.timezone_yesterday())

    @override_settings(TIME_ZONE='Asia/Tokyo')
    def test_min_and_max_of_today(self):
        _timezone = pytz.timezone('Asia/Tokyo')
        with patch(
            'django.utils.timezone.now',
            side_effect=lambda: datetime(2015, 12, 31, 20, 0, 0).replace(tzinfo=pytz.utc)
        ):
            today_min, today_max = datetime_utils.min_and_max_of_today()
            self.assertEqual(datetime(2016, 1, 1, 0, 0, 0, tzinfo=_timezone), today_min)
            self.assertEqual(datetime(2016, 1, 1, 23, 59, 59, 999999, tzinfo=_timezone), today_max)

    @override_settings(TIME_ZONE='Asia/Tokyo')
    def test_min_and_max_of_date(self):
        target_day_min, target_day_max = datetime_utils.min_and_max_of_date(
            datetime(2015, 12, 31, 20, 0, 0, tzinfo=pytz.utc).date(), 5)
        self.assertEqual(datetime(2016, 1, 5, 0, 0, 0, tzinfo=pytz.timezone('Asia/Tokyo')), target_day_min)
        self.assertEqual(datetime(2016, 1, 5, 23, 59, 59, 999999, tzinfo=pytz.timezone('Asia/Tokyo')), target_day_max)

        # TypeError
        with self.assertRaises(TypeError):
            datetime_utils.min_and_max_of_date(datetime(2015, 12, 31, 20, 0, 0, tzinfo=pytz.utc), 5)

    @override_settings(TIME_ZONE='Asia/Tokyo')
    def test_to_jst(self):
        _timezone = pytz.timezone('Asia/Tokyo')
        self.assertEqual(
            datetime(2015, 12, 31, 15, 0, 0),
            datetime_utils.to_jst(datetime(2015, 12, 31, 15, 0, 0))
        )
        self.assertEqual(
            datetime(2015, 12, 31, 15, 0, 0, tzinfo=pytz.utc),
            datetime_utils.to_jst(datetime(2016, 1, 1, 0, 0, 0, tzinfo=pytz.timezone('Asia/Tokyo')))
        )

    def test_format_for_w2ui(self):
        # datetime (has timezone)
        self.assertEqual(
            '2016/01/01 12:34:56 JST',
            datetime_utils.format_for_w2ui(datetime(2016, 1, 1, 12, 34, 56, tzinfo=pytz.timezone('Asia/Tokyo')))
        )
        # datetime (no timezone)
        self.assertEqual(
            '2016/01/01 12:34:56',
            datetime_utils.format_for_w2ui(datetime(2016, 1, 1, 12, 34, 56))
        )
        # date
        self.assertEqual(
            '2016/01/01',
            datetime_utils.format_for_w2ui(date(2016, 1, 1))
        )
        # other type
        with self.assertRaises(TypeError):
            datetime_utils.format_for_w2ui('2016-01-01')

    def test_seconds_to_time_format(self):
        # int, rounded up
        self.assertEqual(
            '0:00',
            datetime_utils.seconds_to_time_format(0)
        )
        self.assertEqual(
            '0:01',
            datetime_utils.seconds_to_time_format(1)
        )
        self.assertEqual(
            '0:01',
            datetime_utils.seconds_to_time_format(60)
        )
        self.assertEqual(
            '0:02',
            datetime_utils.seconds_to_time_format(61)
        )
        self.assertEqual(
            '1:00',
            datetime_utils.seconds_to_time_format(3599)
        )
        self.assertEqual(
            '1:00',
            datetime_utils.seconds_to_time_format(3600)
        )
        self.assertEqual(
            '1:01',
            datetime_utils.seconds_to_time_format(3601)
        )

        # int, no rounded up
        self.assertEqual(
            '0:00',
            datetime_utils.seconds_to_time_format(0, False)
        )
        self.assertEqual(
            '0:00',
            datetime_utils.seconds_to_time_format(1, False)
        )
        self.assertEqual(
            '0:01',
            datetime_utils.seconds_to_time_format(60, False)
        )
        self.assertEqual(
            '0:01',
            datetime_utils.seconds_to_time_format(61, False)
        )
        self.assertEqual(
            '0:59',
            datetime_utils.seconds_to_time_format(3599, False)
        )
        self.assertEqual(
            '1:00',
            datetime_utils.seconds_to_time_format(3600, False)
        )
        self.assertEqual(
            '1:00',
            datetime_utils.seconds_to_time_format(3601, False)
        )

        # float, rounded up
        self.assertEqual(
            '0:00',
            datetime_utils.seconds_to_time_format(0.0)
        )
        self.assertEqual(
            '0:01',
            datetime_utils.seconds_to_time_format(1.0)
        )
        self.assertEqual(
            '0:01',
            datetime_utils.seconds_to_time_format(60.0)
        )
        self.assertEqual(
            '0:02',
            datetime_utils.seconds_to_time_format(61.0)
        )
        self.assertEqual(
            '1:00',
            datetime_utils.seconds_to_time_format(3599.0)
        )
        self.assertEqual(
            '1:00',
            datetime_utils.seconds_to_time_format(3600.0)
        )
        self.assertEqual(
            '1:01',
            datetime_utils.seconds_to_time_format(3601.0)
        )

        # float, no rounded up
        self.assertEqual(
            '0:00',
            datetime_utils.seconds_to_time_format(0.0, False)
        )
        self.assertEqual(
            '0:00',
            datetime_utils.seconds_to_time_format(1.0, False)
        )
        self.assertEqual(
            '0:01',
            datetime_utils.seconds_to_time_format(60.0, False)
        )
        self.assertEqual(
            '0:01',
            datetime_utils.seconds_to_time_format(61.0, False)
        )
        self.assertEqual(
            '0:59',
            datetime_utils.seconds_to_time_format(3599.0, False)
        )
        self.assertEqual(
            '1:00',
            datetime_utils.seconds_to_time_format(3600.0, False)
        )
        self.assertEqual(
            '1:00',
            datetime_utils.seconds_to_time_format(3601.0, False)
        )

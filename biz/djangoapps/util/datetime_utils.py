"""
Cache utilities
"""
from datetime import date, datetime
import math

from django.utils import timezone


def timezone_now():
    """
    Get current datetime with server timezone

    :return: current datetime with server timezone
    """
    return timezone.now().astimezone(timezone.get_default_timezone())


def timezone_today():
    """
    Get current date with server timezone

    :return: current date with server timezone
    """
    return timezone_now().date()


def to_jst(_datetime):
    """
    Convert datetime object to JST. If specified datetime is not aware, then just return it.

    :param _datetime: datetime object
    :return: datetime object with server timezone (i.e. JST)
    """
    if timezone.is_naive(_datetime):
        return _datetime
    else:
        return _datetime.astimezone(timezone.get_default_timezone())


def format_for_w2ui(_date_or_datetime):
    """
    Format date or datetime object to string that can be parsed in w2ui.

    :param _date_or_datetime: date or datetime object
    :return: strings that are formatted for w2ui
    """
    if isinstance(_date_or_datetime, datetime):
        _format = '%Y/%m/%d %H:%M:%S'
        if timezone.is_aware(_date_or_datetime):
            _format += ' %Z'
    elif isinstance(_date_or_datetime, date):
        _format = '%Y/%m/%d'
    else:
        raise TypeError('parameter must be instance of date or datetime. {}'.format(type(_date_or_datetime)))
    return _date_or_datetime.strftime(_format)


def seconds_to_time_format(seconds, rounded_up=True):
    """
    Convert seconds to 'h:mm' string.

    :param seconds: seconds (int or float)
    :param rounded_up: if True, apply rounding up to the minutes
    :return: 'h:mm' string
    """
    if rounded_up:
        minutes = math.floor(seconds / 60) + math.ceil(float(seconds) % 60 / 60)
    else:
        minutes = math.floor(seconds / 60)
    return '%d:%02d' % (math.floor(minutes / 60), minutes % 60)

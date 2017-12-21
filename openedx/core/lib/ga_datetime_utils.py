"""
Datetime utilities
"""
from django.utils import timezone


def to_timezone(datetime_obj, tz=None):
    """
    Convert datetime object to the specified time zone. If specified datetime is not aware,
    then just return it. And if timezone has not been specified, then use it from settings.

    :param datetime_obj: datetime object
    :param tz: timezone object
    :return: datetime object with specified timezone.
    """
    if timezone.is_naive(datetime_obj):
        return datetime_obj
    else:
        if tz is None:
            tz = timezone.get_default_timezone()
        return datetime_obj.astimezone(tz)


def format_for_csv(datetime_obj):
    """
    Convert datetime object to string formatted for CSV.

    :param datetime_obj: datetime object
    :return: string formatted for CSV (ex: '2017-10-23 17:06:45.013823 JST')
    """
    _format = '%Y-%m-%d %H:%M:%S.%f'
    if timezone.is_aware(datetime_obj):
        _format += ' %Z'
    return to_timezone(datetime_obj).strftime(_format)

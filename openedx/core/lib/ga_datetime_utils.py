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

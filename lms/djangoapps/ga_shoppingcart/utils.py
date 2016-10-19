"""
Utility methods for ga_shoppingcart
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

# Hack for Studio. This module is referenced from common/djangoapps/student/views.py.
try:
    from shoppingcart.processors.helpers import get_processor_config
    SC_SESSION_TIMEOUT = get_processor_config().get('SESSION_TIMEOUT', 600)
except:
    SC_SESSION_TIMEOUT = 600


def get_order_keep_time():
    return timezone.now() - timedelta(seconds=SC_SESSION_TIMEOUT)


def get_tax(price):
    return int(price * settings.PAYMENT_TAX / 100)

"""
Utility methods for ga_shoppingcart
"""
import logging

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from ga_shoppingcart.exceptions import InvalidOrder

log = logging.getLogger(__name__)


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


def check_order_can_purchase(order):
    """
    Check whether available for purchase processing of the specified Order.

    - Order status must be `paying`
    - Within SC_SESSION_TIMEOUT from all of the OrderItem has been created
    """
    if order.status != 'paying':
        log.warning("Order status is not paying. user_id={user_id}, order_id={order_id}".format(
            user_id=order.user.id, order_id=order.id
        ))
        raise InvalidOrder()

    order_items = order.orderitem_set.all()

    is_paying = (order.status == 'paying') and all([item.status == 'paying' for item in order_items])

    if not is_paying:
        log.warning("Order status is not paying. user_id={user_id}, order_id={order_id}".format(
            user_id=order.user.id, order_id=order.id
        ))
        raise InvalidOrder()

    _order_keep_time = get_order_keep_time()
    is_alive = all([item.created >= _order_keep_time for item in order_items])

    if not is_alive:
        log.warning("Order has invalid item. user_id={user_id}, order_id={order_id}".format(
            user_id=order.user.id, order_id=order.id
        ))
        raise InvalidOrder()

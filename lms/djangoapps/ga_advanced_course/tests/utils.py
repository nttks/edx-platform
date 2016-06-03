
from datetime import datetime, timedelta
import pytz

from django.utils import timezone

from shoppingcart.models import Order, OrderItem

from ga_shoppingcart.models import AdvancedCourseItem


def _purchase_ticket(user, ticket, status, purchase_time=None, payment_method='0'):
    cart = Order.get_cart_for_user(user)
    cart.clear()
    AdvancedCourseItem.add_to_order(cart, ticket)

    cart.status = status
    if status == 'purchased':
        cart.purchase_time = purchase_time if purchase_time else datetime.now(pytz.utc)
        cart.processor_reply_dump = '{{"p022": "{}"}}'.format(payment_method)
    cart.save()

    for item in OrderItem.objects.filter(order=cart).select_subclasses():
        if status == 'purchased':
            item.purchase_item()
        elif status == 'paying':
            item.start_purchase()

    return cart


def purchase_ticket(user, ticket, purchase_time=None, payment_method='0'):
    return _purchase_ticket(user, ticket, 'purchased', purchase_time, payment_method)


def start_purchase_ticket(user, ticket):
    return _purchase_ticket(user, ticket, 'paying')


def make_ticket_to_out_of_sale(ticket):
    ticket.sell_by_date = timezone.now() - timedelta(seconds=1)
    ticket.save()

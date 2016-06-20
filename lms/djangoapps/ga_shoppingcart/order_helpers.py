"""
Helper methods for models of shoppingcart.
"""

import logging

from django.conf import settings

log = logging.getLogger(__name__)


def purchase(order, ccnum='', cardtype='', processor_reply_dump='', override=True):
    """
    Call to mark specified order as purchased. If order is already marked as purchased,
    then just override meta information if override is True.
    """
    if order.status == 'purchased':
        log.info('Order({}) is already purchased.'.format(order.id))
        if settings.FEATURES['STORE_BILLING_INFO']:
            if ccnum and override:
                order.bill_to_ccnum = ccnum
            if cardtype and override:
                order.bill_to_cardtype = cardtype
            if processor_reply_dump and override:
                order.processor_reply_dump = processor_reply_dump
            log.info('Update of the payment information only.')
            order.save()
    else:
        # if order is not purchased, then process purchase.
        log.info('Order({}) is not purchased yet. Run the purchase process.'.format(order.id))
        order.purchase(ccnum=ccnum, cardtype=cardtype, processor_reply_dump=processor_reply_dump)

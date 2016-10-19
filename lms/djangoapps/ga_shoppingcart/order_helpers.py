"""
Helper methods for models of shoppingcart.
"""

import logging

from django.conf import settings
from django.utils import translation

from lang_pref import LANGUAGE_KEY
from lang_pref.api import released_languages
from openedx.core.djangoapps.user_api.preferences.api import get_user_preference

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


def set_language_from_order(order):
    user_pref = get_user_preference(order.user, LANGUAGE_KEY)
    if user_pref:
        released_language_codes = [language[0] for language in released_languages()]
        if user_pref in released_language_codes:
            translation.activate(user_pref)

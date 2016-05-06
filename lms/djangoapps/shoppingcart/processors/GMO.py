"""
Implementation of the GMO processor
"""

import hashlib
import json
import logging
from collections import OrderedDict

from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext as _

from microsite_configuration import microsite

from .exceptions import *
from .helpers import get_processor_config
from ..models import Order, OrderItem

from ga_shoppingcart import order_helpers

log = logging.getLogger(__name__)


def create_order_id(order):
    return "{prefix}-{order_id}".format(prefix=get_processor_config()['ORDER_ID_PREFIX'], order_id=order.id)


def parse_order_id(gmo_order_id):
    values = gmo_order_id.rsplit('-', 1)

    if len(values) != 2 or values[0] != get_processor_config()['ORDER_ID_PREFIX']:
        raise CCProcessorDataException("OrderID[{}] received from the GMO is invalid.".format(gmo_order_id))

    try:
        return int(values[1])
    except (ValueError, TypeError):
        raise CCProcessorDataException("OrderID[{}] received from the GMO is invalid.".format(gmo_order_id))


def process_postpay_callback(_params):
    """
    Handle a response from the payment processor.
    """
    try:
        params = ResultParams(_params)
        # First we need to check whther an error has occured at GMO.
        # If an error has occured, the after processing can not be purformed.
        if params.has_error():
            raise CCProcessorException(
                "error has occured at GMO error_code={error_code}, error_detail_code={error_detail_code}".format(
                    error_code=params.error_code, error_detail_code=params.error_detail_code
                )
            )

        params.verify_signatures()
        params.verify_params()

        # compare an order in database and parameters received
        order = payment_accepted(parse_order_id(params.order_id), params.amount, params.tax, params.currency)

        _record_purchase(params, order)
        return {
            'success': True,
            'order': order,
            'error_html': ''
        }
    except CCProcessorException as error:
        log.exception('error processing GMO postpay callback')
        _order = _get_order_from_reponse_with_no_exception(params)
        # if we have the order and the id, log it
        if _order:
            _record_payment_info(params, _order)
        else:
            log.error(params.get_dumps())
        return {
            'success': False,
            'order': _order,
            'error_html': _get_processor_exception_html(error, _order)
        }


def processor_hash(value):
    hash_type = get_processor_config().get('HASH_TYPE')
    if hash_type == 'MD5':
        return hashlib.md5(value).hexdigest()
    elif hash_type == 'SHA256':
        return hashlib.sha256(value).hexdigest()
    elif hash_type == 'SHA512':
        return hashlib.sha512(value).hexdigest()
    else:
        raise CCProcessorException("Unknown hash_type {hash_type}".format(hash_type=hash_type))


def sign(params):
    """
    Sign the parameters dictionary so GMO can validate our identity.

    Returns:
        dict: The same parameters dict, with a signed key calculated from the other values.

    """
    params['signature'] = processor_hash(''.join([
        params['shop_id'],
        params['order_id'],
        str(params['amount']),
        str(params['tax']),
        get_processor_config().get('SHOP_PASSWORD'),
        params['datetime'],
    ]))

    return params


def get_signed_purchase_params(cart, callback_url=None, extra_data=None):
    """
    This method will return a digitally signed set of GMO parameters

    Args:
        cart (Order): The order model representing items in the user's cart.

    Keyword Args:
        callback_url : The URL that GMO should POST to when the user completes a purchase.
                       callback_url should tuple success-callback and cancel-callback.

        extra_data (list): Additional data to include as merchant-defined data fields.

    Returns:
        dict

    """
    return sign(get_purchase_params(cart, callback_url=callback_url, extra_data=extra_data))


def get_purchase_params(cart, callback_url=None, extra_data=None):
    """
    This method will build out a dictionary of parameters needed by GMO to complete the transaction

    """

    if type(callback_url) == tuple:
        callback_url1 = callback_url[0]
        callback_url2 = callback_url[1] if len(callback_url) >= 2 else callback_url[0]
    else:
        callback_url1 = callback_url
        callback_url2 = callback_url

    params = PurchaseParams()

    params['shop_id'] = get_processor_config().get('ACCESS_KEY')
    params['order_id'] = create_order_id(cart)
    params['amount'] = int(cart.total_cost)
    params['tax'] = int(cart.total_tax)
    params['currency'] = cart.currency
    params['datetime'] = timezone.now().strftime("%Y%m%d%H%M%S")
    params['return_url'] = callback_url1
    params['cancel_url'] = callback_url2
    params['max_retry'] = get_processor_config().get('MAX_RETRY')
    params['session_timeout'] = get_processor_config().get('SESSION_TIMEOUT')
    params['encode'] = 'utf-8'
    params['show_confirm'] = get_processor_config().get('SHOW_CONFIRM')
    params['use_credit'] = 1
    params['use_docomo'] = 1
    params['job'] = 'CAPTURE'

    if extra_data is not None:
        # set additional that data we have defined
        for num, item in enumerate(extra_data, start=1):
            key = 'client_field_{}'.format(num)
            params[key] = item

    return params


def get_purchase_endpoint():
    """
    Return the URL of the payment end-point for GMO.
    """
    return get_processor_config().get('PURCHASE_ENDPOINT', '')


def payment_accepted(order_id, auth_amount, auth_tax, currency):
    """
    Check that GMO has accepted the payment.
    """
    if not currency:
        currency = 'JPY'
    currency = currency.lower()

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        raise CCProcessorDataException(_("The payment processor accepted an order whose number is not in our system."))

    if (
        auth_amount == int(order.total_cost) and
        auth_tax == int(order.total_tax) and
        currency == order.currency
    ):
        return order
    else:
        raise CCProcessorWrongAmountException(
            _(
                u"The amount charged by the processor {charged_amount} {charged_tax} {charged_amount_currency} is different "
                u"than the total cost of the order {total_cost} {total_tax} {total_cost_currency}."
            ).format(
                charged_amount=auth_amount,
                charged_amount_currency=currency,
                charged_tax=auth_tax,
                total_cost=int(order.total_cost),
                total_tax=int(order.total_tax),
                total_cost_currency=order.currency
            )
        )


def _record_purchase(params, order):
    """
    Record the purchase and run purchased_callbacks
    """

    # size of column `bill_to_ccnum` of model `Order` is 8
    ccnum = params.card_number[-8:] if params.is_card() else ''
    cardtype = params.card_type if params.is_card() else ''

    if settings.FEATURES.get("LOG_POSTPAY_CALLBACKS"):
        log.info(
            "Order %d purchased with params: %s", order.id, params.get_dumps()
        )

    # Mark the order as purchased and store the billing information
    order_helpers.purchase(
        order,
        ccnum=ccnum,
        cardtype=cardtype,
        processor_reply_dump=params.get_dumps()
    )


def _record_payment_info(params, order):
    """
    Record the purchase and run purchased_callbacks
    """
    if settings.FEATURES.get("LOG_POSTPAY_CALLBACKS"):
        log.info(
            "Order %d processed (but not completed) with params: %s", order.id, params.get_dumps()
        )

    order.processor_reply_dump = params.get_dumps()
    order.save()


def _get_order_from_reponse_with_no_exception(params):
    """
    Returns Order from response.
    This function is intended for error handling and never raise exception.
    """
    try:
        order_id = params.order_id
        if order_id:
            order_id = parse_order_id(order_id)
            return Order.objects.get(id=order_id)
    except:
        # Just logging and do nothing
        log.exception("Failed to get order from response.")
    return None


def _get_processor_exception_html(exception, order):
    """
    Return HTML indicating that an error occurred.

    Args:
        exception (CCProcessorException): The exception that occurred.

    Returns:
        unicode: The rendered HTML.

    """
    message = _(
        u"Sorry! Your payment could not be processed because an unexpected exception occurred. "
        u"Please contact us through the Help."
    )
    if order:
        order_items = OrderItem.objects.filter(order=order).select_subclasses()
        if order_items.count() == 1 and order_items[0].item_page:
            message += _(
                u"Please click <a href=\"{item_page_link}\">here</a> if you go back to the purchase page."
            ).format(
                item_page_link=order_items[0].item_page
            )
    return _format_error_html(message)


def _format_error_html(msg):
    """ Format an HTML error message """
    return u'<p class="error_msg">{msg}</p>'.format(msg=msg)


class PurchaseParams(OrderedDict):

    params_config_key = 'PURCHASE_PARAMS_MAP'

    attr_map = {
        'p001': 'shop_id',
        'p002': 'order_id',
        'p003': 'amount',
        'p004': 'tax',
        'p005': 'currency',
        'p006': 'datetime',
        'p007': 'signature',
        'p008': 'return_url',
        'p009': 'cancel_url',
        'p010': 'client_field_1',
        'p011': 'client_field_2',
        'p012': 'client_field_3',
        'p014': 'max_retry',
        'p015': 'session_timeout',
        'p016': 'encode',
        'p018': 'show_confirm',
        'p019': 'use_credit',
        'p028': 'use_docomo',
        'p040': 'job',
    }

    def __init__(self, *args, **kwargs):
        super(PurchaseParams, self).__init__(*args, **kwargs)
        self.attrs = {}
        _params_key_map = get_processor_config().get(self.params_config_key)
        for param_key, attr_key in self.attr_map.items():
            if param_key not in _params_key_map:
                raise CCProcessorException('Missing parameter {} in processor config {}.'.format(
                    param_key, self.params_config_key)
                )
            self.attrs[attr_key] = _params_key_map[param_key]

    def __getitem__(self, key):
        return super(PurchaseParams, self).__getitem__(self._resolve_key(key))

    def __setitem__(self, key, value, PREV=0, NEXT=1, dict_setitem=dict.__setitem__):
        super(PurchaseParams, self).__setitem__(self._resolve_key(key), value, PREV, NEXT, dict_setitem)

    def _resolve_key(self, key):
        if key in self.attrs:
            return self.attrs[key]
        else:
            return key


class AbstractReadParams(object):

    params_config_key = None
    attr_map = {}

    def __init__(self, params):
        self.params = params  # it is necessary to hold in order to dump
        self.attrs = {}
        _params_key = get_processor_config().get(self.params_config_key)
        for param_key, attr_key in self.attr_map.items():
            if param_key not in _params_key:
                raise CCProcessorException('Missing parameter {} in processor config {}.'.format(
                    param_key, self.params_config_key)
                )
            _key = _params_key[param_key]
            self.attrs[attr_key] = params.get(_key)

    def __getattr__(self, name):
        if name not in self.attrs:
            raise AttributeError('{} object has no attribute {}'.format(type(self).__name__, name))
        return self.attrs[name]

    def get_dumps(self):
        return json.dumps(self.params)


class ResultParams(AbstractReadParams):

    params_config_key = 'RESULT_PARAMS_MAP'

    attr_map = {
        'p001': 'shop_id',
        'p003': 'amount',
        'p004': 'tax',
        'p005': 'currency',
        'p006': 'access_id',
        'p008': 'order_id',
        'p009': 'card_type',
        'p010': 'payment_method',
        'p011': 'payment_times',
        'p012': 'approve',
        'p013': 'transaction_id',
        'p014': 'transaction_date',
        'p015': 'signature',
        'p016': 'error_code',
        'p017': 'error_detail_code',
        'p022': 'payment_type',
        'p048': 'card_number',
    }

    def is_card(self):
        return self.payment_type == '0'

    def is_docomo(self):
        return self.payment_type == '9'

    def has_error(self):
        return bool(self.error_code.strip())

    def verify_params(self):
        """
        Validate that we have the paramters we expect and can convert them to the appropriate types.
        Usually validating the signature is sufficient to validate that these fields exist,
        but we need to check an additional several parameters.
        """
        if not self.is_card() and not self.is_docomo():
            raise CCProcessorDataException(_(
                u"The payment processor did not support payment_type {}".format(self.payment_type)
            ))

        required_params = [('amount', int), ('tax', int), ('currency', str), ]
        for key, key_type in required_params:
            if not hasattr(self, key) or getattr(self, key) is None:
                raise CCProcessorDataException(
                    u"The payment processor did not return a required parameter: {}".format(key)
                )
            try:
                setattr(self, key, key_type(getattr(self, key)))
            except (ValueError, TypeError):
                raise CCProcessorDataException(
                    u"The payment processor returned a badly-typed value {value} for parameter {parameter}.".format(
                        value=getattr(self, key), parameter=key
                    )
                )

    def verify_signatures(self):
        """
        Use the signature we receive in the POST back from GMO to verify
        the identity of the sender (GMO) and that the contents of the message
        have not been tampered with.
        """
        if self.is_card():
            _signature = processor_hash(''.join([
                self.order_id,
                self.card_type,
                self.payment_method,
                self.payment_times,
                self.approve,
                self.transaction_id,
                self.transaction_date,
                get_processor_config().get('SHOP_PASSWORD'),
            ]))
        elif self.is_docomo():
            _signature = processor_hash(''.join([
                self.order_id,
                self.access_id,
                self.transaction_date,
                get_processor_config().get('SHOP_PASSWORD'),
            ]))
        else:
            _signature = None

        if self.signature != _signature:
            raise CCProcessorSignatureException()

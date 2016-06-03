"""
Implementation of the GMO notification
"""
import logging

from shoppingcart.processors.GMO import parse_order_id, payment_accepted, AbstractReadParams
from shoppingcart.processors.exceptions import CCProcessorException
from shoppingcart.processors.helpers import get_processor_config

from ga_shoppingcart import order_helpers

NOTIFICATION_STATUS_CAPTURE = 'CAPTURE'
NOTIFICATION_STATUS_VOID = 'VOID'
NOTIFICATION_STATUS_CANCEL = 'CANCEL'
NOTIFICATION_STATUS_REQSUCCESS = 'REQSUCCESS'
NOTIFICATION_STATUS_RETURN = 'RETURN'
NOTIFICATION_STATUS_RETURNX = 'RETURNX'
NOTIFICATION_JOB_CAPTURE = 'CAPTURE'
NOTIFICATION_JOB_VOID = 'VOID'
NOTIFICATION_JOB_CANCEL = 'CANCEL'
NOTIFICATION_JOB_RETURN = 'RETURN'
NOTIFICATION_JOB_RETURNX = 'RETURNX'

JOB_CANCEL_CARD = [
    NOTIFICATION_JOB_VOID,
    NOTIFICATION_JOB_RETURN,
    NOTIFICATION_JOB_RETURNX,
]

JOB_CANCEL_DCM = [
    NOTIFICATION_JOB_CANCEL,
]

STATUS_CANCEL_CARD = [
    NOTIFICATION_STATUS_VOID,
    NOTIFICATION_STATUS_RETURN,
    NOTIFICATION_STATUS_RETURNX,
]

STATUS_CANCEL_DCM = [
    NOTIFICATION_STATUS_CANCEL,
]

IGNORED_NOTIFICATION_STATUSES = [
    NOTIFICATION_STATUS_REQSUCCESS,
]

log = logging.getLogger(__name__)


def process_notification(_params):
    """
    Process the notification data that was passed from the GMO.
    """
    params = _NotificationParams(_params)
    if params.shop_id != get_processor_config().get('ACCESS_KEY'):
        raise CCProcessorException("Invalid ACCESS_KEY {}".format(params.shop_id))

    if params.has_error():
        raise CCProcessorException(
            "error has occurred at GMO error_code={error_code}, error_detail_code={error_detail_code}".format(
                error_code=params.error_code, error_detail_code=params.error_detail_code
            )
        )

    params.verify_params()

    if params.is_capture():
        _process_capture(params)
    elif params.is_cancel():
        _process_cancel(params)
    else:
        log.warning(
            "We received an unknown notification. order_id={order_id}, job={job}, status={status}".format(
                order_id=params.order_id,
                job=params.job,
                status=params.status
            )
        )


def _process_capture(params):
    """
    Do the processing of the CAPTURE.

    :param params: parameters wrapped by _NotificationParams
    """
    if params.is_capture_success():
        log.info('We received the notification of the CAPTURE success.')
        order = _payment_accepted(params)
        order_helpers.purchase(order, processor_reply_dump=params.get_dumps(), override=False)
    elif params.is_capture_ignore():
        # nothing to do
        log.info('We received the notification of the CAPTURE, but do nothing.')
    else:
        raise CCProcessorException('Illegal state has been notified. CAPTURE has failed.')


def _process_cancel(params):
    """
    Do the processing of the cancel.

    :param params: parameters wrapped by _NotificationParams
    """
    if params.is_cancel_success():
        log.info('We received the notification of the CANCEL success.')
        order = _payment_accepted(params)
        order.refund()
    else:
        raise CCProcessorException('Illegal state has been notified. CANCEL has failed.')


def _payment_accepted(params):
    _amount = params.amount
    _tax = params.tax
    _currency = params.currency

    if params.is_docomo() and params.is_cancel():
        _amount = params.docomo_cancel_amount
        _tax = params.docomo_cancel_tax

    if _currency == 'JPN':
        # GMO notification programs returns JPN the currency code of the Japanese Yen.
        _currency = 'JPY'

    return payment_accepted(
        parse_order_id(params.order_id),
        _amount,
        _tax,
        _currency
    )


class _NotificationParams(AbstractReadParams):

    params_config_key = 'NOTIFICATION_PARAMS_MAP'

    attr_map = {
        'p001': 'shop_id',
        'p005': 'order_id',
        'p006': 'status',
        'p007': 'job',
        'p008': 'amount',
        'p009': 'tax',
        'p010': 'currency',
        'p017': 'error_code',
        'p018': 'error_detail_code',
        'p019': 'payment_type',
        'p913': 'docomo_cancel_amount',
        'p914': 'docomo_cancel_tax',
    }

    def has_error(self):
        return bool(self.error_code.strip())

    def is_card(self):
        return self.payment_type == '0'

    def is_docomo(self):
        return self.payment_type == '9'

    def is_capture(self):
        return self.job == NOTIFICATION_JOB_CAPTURE

    def is_capture_success(self):
        return self.is_capture() and self.status == NOTIFICATION_STATUS_CAPTURE

    def is_capture_ignore(self):
        return self.is_capture() and self.status in IGNORED_NOTIFICATION_STATUSES

    def is_cancel(self):
        return (
            self.is_card() and self.job in JOB_CANCEL_CARD
        ) or (
            self.is_docomo() and self.job in JOB_CANCEL_DCM
        )

    def is_cancel_success(self):
        return self.is_cancel() and (
            (self.is_card() and self.status in STATUS_CANCEL_CARD) or
            (self.is_docomo() and self.status in STATUS_CANCEL_DCM)
        )

    def verify_params(self):
        """
        Validate that we have the paramters we expect and can convert them to the appropriate types.
        """
        if self.is_docomo() and self.is_cancel():
            required_params = [('docomo_cancel_amount', int), ('docomo_cancel_tax', int), ('currency', str), ]
        else:
            required_params = [('amount', int), ('tax', int), ('currency', str), ]

        for key, key_type in required_params:
            if not hasattr(self, key) or getattr(self, key) is None:
                raise CCProcessorException(
                    u"The payment processor did not return a required parameter: {}".format(key)
                )
            try:
                setattr(self, key, key_type(getattr(self, key)))
            except (ValueError, TypeError):
                raise CCProcessorException(
                    u"The payment processor returned a badly-typed value {value} for parameter {parameter}.".format(
                        value=getattr(self, key), parameter=key
                    )
                )

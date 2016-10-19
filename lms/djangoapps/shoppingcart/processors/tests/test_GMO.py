
import hashlib
import math
from mock import patch
import ddt

from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone, translation

from opaque_keys.edx.keys import CourseKey
from student.tests.factories import UserFactory

from ga_advanced_course.tests.factories import AdvancedF2FCourseFactory, AdvancedCourseTicketFactory
from ga_shoppingcart.models import AdvancedCourseItem

from shoppingcart.models import Order, OrderItem
from shoppingcart.processors.exceptions import CCProcessorException, CCProcessorDataException
from shoppingcart.processors.GMO import (
    process_postpay_callback,
    get_signed_purchase_params,
    sign,
    PurchaseParams,
    ResultParams,
)


PURCHASE_PARAMS_MAP = {p: p for p in ['p{}'.format(str(i).zfill(3)) for i in range(1, 100)]}
RESULT_PARAMS_MAP = {p: p for p in ['p{}'.format(str(i).zfill(3)) for i in range(1, 100)]}


@override_settings(
    CC_PROCESSOR_NAME='GMO',
    CC_PROCESSOR={
        'GMO': {
            'ACCESS_KEY': 'test_access_key',
            'SHOP_PASSWORD': 'test_shop_password',
            'PURCHASE_ENDPOINT': 'test_purchase_endpoint',
            'HASH_TYPE': 'MD5',
            'MAX_RETRY': 3,
            'SESSION_TIMEOUT': 600,
            'SHOW_CONFIRM': 1,
            'ORDER_ID_PREFIX': 'ga-test',
            'PURCHASE_PARAMS_MAP': PURCHASE_PARAMS_MAP,
            'RESULT_PARAMS_MAP': RESULT_PARAMS_MAP
        }
    },
    PAYMENT_TAX=8
)
@ddt.ddt
class GMOTest(TestCase):

    PRICE = 1000
    CALLBACK_URL = (
        '/test_callback_url',
        '/test_cancel_callback_url',
    )
    EXTRA_DATA = [
        'test extra item 1',
        'test extra item 2',
        'test extra item 3',
    ]

    def setUp(self):
        self.course_id = CourseKey.from_string('course-v1:org+course_{}+run'.format(self._testMethodName))
        self.user = UserFactory.create()
        self.ticket = AdvancedCourseTicketFactory.create(
            advanced_course=AdvancedF2FCourseFactory.create(course_id=self.course_id),
            price=self.PRICE
        )
        self.order = Order.get_cart_for_user(self.user)
        self.item = AdvancedCourseItem.add_to_order(self.order, self.ticket)
        self.order.start_purchase()

    def _assert_dump_recorded(self, order):
        """
        Verify that this order does have a dump of information from thepayment processor.
        """
        self.assertNotEqual(order.processor_reply_dump, '')

    def _assert_error_html(self, result, has_order=True):
        self.assertIn(
            'Sorry! Your payment could not be processed because an unexpected exception occurred.',
            result['error_html']
        )
        if has_order:
            self.assertIn('if you go back to the purchase page', result['error_html'])
        else:
            self.assertNotIn('if you go back to the purchase page', result['error_html'])

    def _signed_callback_params(
        self, order_id=None, price=None, tax=None, currency=None, ptype='0', signature=None,
        error_code='', error_detail_code=''
    ):
        params = {
            'p001': '11111111111',
            'p002': 'CAPTURE',
            'p003': price if price else self.PRICE,
            'p004': tax if tax else int(math.floor(self.PRICE * 8 / 100)),
            'p005': currency if currency else 'jpy',
            'p006': '61111111111',
            'p007': '71111111111',
            'p008': order_id if order_id else 'ga-test-{}'.format(self.order.id),
            'p009': '91111111111',
            'p010': '1',
            'p011': '0',
            'p012': '121111111111',
            'p013': '131111111111',
            'p014': '20160129123456',
            'p016': error_code,
            'p017': error_detail_code,
            'p018': 'test extra item 1',
            'p019': 'test extra item 2',
            'p020': 'test extra item 3',
            'p022': ptype,
        }

        if not signature:
            if params['p022'] == '0':
                signature = hashlib.md5(''.join([
                    params['p008'], params['p009'], params['p010'], params['p011'],
                    params['p012'], params['p013'], params['p014'], 'test_shop_password',
                ])).hexdigest()
            elif params['p022'] == '9':
                signature = hashlib.md5(''.join([
                    params['p008'], params['p006'], params['p014'], 'test_shop_password',
                ])).hexdigest()
        params['p015'] = signature

        if params['p022'] == '0':
            params['p048'] = '****1111'

        return params

    @ddt.data('ja', 'ja-jp', 'en', 'es')
    def test_get_signed_purchase_params(self, lang_code):
        # pseudo language settings
        translation.activate(lang_code)

        params = get_signed_purchase_params(self.order, self.CALLBACK_URL, self.EXTRA_DATA)

        # Check parameter exists
        for key in [
            'p001', 'p002', 'p003', 'p004', 'p005', 'p006', 'p007', 'p008', 'p009', 'p010', 'p011', 'p012',
            'p014', 'p015', 'p016', 'p018', 'p019', 'p028', 'p039', 'p040',
        ]:
            self.assertTrue(key in params)

        self.assertEqual(params['p001'], 'test_access_key')
        self.assertEqual(params['p002'], 'ga-test-{}'.format(self.order.id))
        self.assertEqual(params['p003'], 1000)
        self.assertEqual(params['p004'], 80)
        self.assertEqual(params['p005'], 'jpy')
        _signature = hashlib.md5(
            ''.join([
                'test_access_key', 'ga-test-{}'.format(self.order.id),
                '1000', '80', 'test_shop_password', params['p006']
            ])
        ).hexdigest()
        self.assertEqual(params['p007'], _signature)
        self.assertEqual(params['p008'], self.CALLBACK_URL[0])
        self.assertEqual(params['p009'], self.CALLBACK_URL[1])
        self.assertEqual(params['p010'], 'test extra item 1')
        self.assertEqual(params['p011'], 'test extra item 2')
        self.assertEqual(params['p012'], 'test extra item 3')
        self.assertEqual(params['p014'], 3)
        self.assertEqual(params['p015'], 600)
        self.assertEqual(params['p016'], 'utf-8')
        self.assertEqual(params['p018'], 1)
        self.assertEqual(params['p019'], 1)
        self.assertEqual(params['p028'], 1)
        # template has been determined by language
        if lang_code == 'ja' or lang_code == 'ja-jp':
            self.assertEqual(params['p039'], 1)
        else:
            self.assertEqual(params['p039'], 2)
        self.assertEqual(params['p040'], 'CAPTURE')

    @patch.object(AdvancedCourseItem, 'purchased_callback')
    @patch.object(OrderItem, 'pdf_receipt_display_name')
    def test_process_postpay_callback_success(self, pdf_receipt_display_name, purchased_callback):
        # Simulate a callback from GMO indicating that payment was successful
        params = self._signed_callback_params()

        result = process_postpay_callback(params)

        # Expect that the item's purchased callback was invoked
        purchased_callback.assert_called_with()

        self.assertTrue(result['success'])
        self.assertEqual(result['error_html'], '')
        self.assertEqual('purchased', result['order'].status)
        self.assertEqual('91111111111', result['order'].bill_to_cardtype)
        self._assert_dump_recorded(result['order'])

    def test_process_postpay_callback_error(self):
        params = self._signed_callback_params()
        params['p016'] = 'ERROR'

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        self._assert_error_html(result)

    def test_process_postpay_callback_invalid_signature(self):
        params = self._signed_callback_params(signature='invalid_signature')

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        self._assert_error_html(result)

    @ddt.data('p008', 'p009', 'p010', 'p011', 'p012', 'p013', 'p014')
    def test_process_postpay_callback_invalid_signature_card(self, invalid_param):
        params = self._signed_callback_params()
        params[invalid_param] = 'invalid_value'

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        has_order = invalid_param != 'p008'
        self._assert_error_html(result, has_order)

    @ddt.data('p006', 'p008', 'p014')
    def test_process_postpay_callback_invalid_signature_docomo(self, invalid_param):
        params = self._signed_callback_params(ptype='9')
        params[invalid_param] = 'invalid_value'

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        has_order = invalid_param != 'p008'
        self._assert_error_html(result, has_order)

    @ddt.data('1', '2', '3', '4', '5', '6', '7', '8', 'B', 'C', 'E', 'F', 'G', 'I', 'J', 'K', 'L', 'O')
    def test_process_postpay_callback_invalid_ptype(self, ptype):
        params = self._signed_callback_params(ptype=ptype)

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        self._assert_error_html(result)

    @ddt.data('p003', 'p004', 'p005')
    def test_process_postpay_callback_missing_param(self, missing_param):
        params = self._signed_callback_params()
        del params[missing_param]

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        has_order = missing_param != 'p008'
        self._assert_error_html(result, has_order)

    def test_process_postpay_callback_invalid_order(self):
        params = self._signed_callback_params(order_id='99999')

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        self._assert_error_html(result, False)

    def test_process_postpay_callback_wrong_amount(self):
        params = self._signed_callback_params(price=99999)

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        self._assert_error_html(result)

    def test_process_postpay_callback_invalid_amount(self):
        params = self._signed_callback_params(price='invalid_price')

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        self._assert_error_html(result)

    def test_process_postpay_callback_wrong_tax(self):
        params = self._signed_callback_params(tax=99999)

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        self._assert_error_html(result)

    def test_process_postpay_callback_invalid_tax(self):
        params = self._signed_callback_params(tax='invalid_tax')

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        self._assert_error_html(result)

    def test_process_postpay_callback_wrong_currency(self):
        params = self._signed_callback_params(currency='USD')

        result = process_postpay_callback(params)

        self.assertFalse(result['success'])
        self._assert_error_html(result)


@override_settings(
    CC_PROCESSOR_NAME='GMO',
    CC_PROCESSOR={
        'GMO': {
            'PURCHASE_PARAMS_MAP': {
                'p001': 'param1',
                'p002': 'param2',
                'p003': 'param3',
                'p004': 'param4',
                'p005': 'param5',
                'p006': 'param6',
                'p007': 'param7',
                'p008': 'param8',
                'p009': 'param9',
                'p010': 'param10',
                'p011': 'param11',
                'p012': 'param12',
                'p014': 'param14',
                'p015': 'param15',
                'p016': 'param16',
                'p018': 'param18',
                'p019': 'param19',
                'p028': 'param28',
                'p039': 'param39',
                'p040': 'param40',
            },
        }
    }
)
@ddt.ddt
class PurchaseParamsTest(TestCase):

    def test_unresolved_key(self):
        """
        Verify that the same operation as normal dict in the case of unresolved key
        """
        params = PurchaseParams()
        params['key'] = 'value'
        self.assertEqual('value', params['key'])

    def test_missing_configuration(self):
        """
        Verify that exception occur if do not have the required key settings.
        """
        from ..helpers import get_processor_config
        _purchase_params_map = get_processor_config().get('PURCHASE_PARAMS_MAP').copy()
        del _purchase_params_map['p040']
        with override_settings(
            CC_PROCESSOR={
                'GMO': {
                    'PURCHASE_PARAMS_MAP': _purchase_params_map,
                }
            }
        ):
            with self.assertRaises(CCProcessorException) as context:
                PurchaseParams()

            self.assertEqual(
                "Missing parameter p040 in processor config PURCHASE_PARAMS_MAP.",
                context.exception.message
            )

    def test_resolved_keys(self):
        params = PurchaseParams()
        params['shop_id'] = 'test_shop_id'
        params['order_id'] = 'test_order_id'
        params['amount'] = '1000'
        params['tax'] = '80'
        params['currency'] = 'JPY'
        params['datetime'] = '20160401123456'
        params['signature'] = 'test_signature'
        params['return_url'] = 'http://example.com/return_url'
        params['cancel_url'] = 'http://example.com/cancel_url'
        params['client_field_1'] = 'test_client_field_1'
        params['client_field_2'] = 'test_client_field_2'
        params['client_field_3'] = 'test_client_field_3'
        params['max_retry'] = '10'
        params['session_timeout'] = '600'
        params['encode'] = 'utf-8'
        params['show_confirm'] = '1'
        params['use_credit'] = '2'
        params['use_docomo'] = '3'
        params['template'] = 9
        params['job'] = 'test_job'

        self.assertEqual('test_shop_id', params['param1'])
        self.assertEqual('test_shop_id', params['shop_id'])

        self.assertEqual('test_order_id', params['param2'])
        self.assertEqual('test_order_id', params['order_id'])

        self.assertEqual('1000', params['param3'])
        self.assertEqual('1000', params['amount'])

        self.assertEqual('80', params['param4'])
        self.assertEqual('80', params['tax'])

        self.assertEqual('JPY', params['param5'])
        self.assertEqual('JPY', params['currency'])

        self.assertEqual('20160401123456', params['param6'])
        self.assertEqual('20160401123456', params['datetime'])

        self.assertEqual('test_signature', params['param7'])
        self.assertEqual('test_signature', params['signature'])

        self.assertEqual('http://example.com/return_url', params['param8'])
        self.assertEqual('http://example.com/return_url', params['return_url'])

        self.assertEqual('http://example.com/cancel_url', params['param9'])
        self.assertEqual('http://example.com/cancel_url', params['cancel_url'])

        self.assertEqual('test_client_field_1', params['param10'])
        self.assertEqual('test_client_field_1', params['client_field_1'])

        self.assertEqual('test_client_field_2', params['param11'])
        self.assertEqual('test_client_field_2', params['client_field_2'])

        self.assertEqual('test_client_field_3', params['param12'])
        self.assertEqual('test_client_field_3', params['client_field_3'])

        self.assertEqual('10', params['param14'])
        self.assertEqual('10', params['max_retry'])

        self.assertEqual('600', params['param15'])
        self.assertEqual('600', params['session_timeout'])

        self.assertEqual('utf-8', params['param16'])
        self.assertEqual('utf-8', params['encode'])

        self.assertEqual('1', params['param18'])
        self.assertEqual('1', params['show_confirm'])

        self.assertEqual('2', params['param19'])
        self.assertEqual('2', params['use_credit'])

        self.assertEqual('3', params['param28'])
        self.assertEqual('3', params['use_docomo'])

        self.assertEqual(9, params['param39'])
        self.assertEqual(9, params['template'])

        self.assertEqual('test_job', params['param40'])
        self.assertEqual('test_job', params['job'])


@override_settings(
    CC_PROCESSOR_NAME='GMO',
    CC_PROCESSOR={
        'GMO': {
            'RESULT_PARAMS_MAP': {
                'p001': 'param_shop_id',
                'p003': 'param_amount',
                'p004': 'param_tax',
                'p005': 'param_currency',
                'p006': 'param_access_id',
                'p008': 'param_order_id',
                'p009': 'param_card_type',
                'p010': 'param_payment_method',
                'p011': 'param_payment_times',
                'p012': 'param_approve',
                'p013': 'param_transaction_id',
                'p014': 'param_transaction_date',
                'p015': 'param_signature',
                'p016': 'param_error_code',
                'p017': 'param_error_detail_code',
                'p022': 'param_payment_type',
                'p048': 'param_card_number',
            },
        }
    }
)
@ddt.ddt
class ResultParamsTest(TestCase):

    def setUp(self):
        super(ResultParamsTest, self).setUp()
        self.response = {
            'param_shop_id': 'test_shop_id',
            'param_amount': '1000',
            'param_tax': '80',
            'param_currency': 'JPY',
            'param_access_id': 'test_access_id',
            'param_order_id': 'test_order_id',
            'param_card_type': 'test_card_type',
            'param_payment_method': 'test_payment_method',
            'param_payment_times': '5',
            'param_approve': 'test_approve',
            'param_transaction_id': 'test_transaction_id',
            'param_transaction_date': '20160401123456999',
            'param_signature': 'test_signature',
            'param_error_code': 'E001',
            'param_error_detail_code': 'E001001',
            'param_payment_type': '0',
            'param_card_number': '************1111',
        }

    def test_attributes(self):
        param = ResultParams(self.response)
        self.assertEqual('test_shop_id', param.shop_id)
        self.assertEqual('1000', param.amount)
        self.assertEqual('80', param.tax)
        self.assertEqual('JPY', param.currency)
        self.assertEqual('test_access_id', param.access_id)
        self.assertEqual('test_order_id', param.order_id)
        self.assertEqual('test_card_type', param.card_type)
        self.assertEqual('test_payment_method', param.payment_method)
        self.assertEqual('5', param.payment_times)
        self.assertEqual('test_approve', param.approve)
        self.assertEqual('test_transaction_id', param.transaction_id)
        self.assertEqual('20160401123456999', param.transaction_date)
        self.assertEqual('test_signature', param.signature)
        self.assertEqual('E001', param.error_code)
        self.assertEqual('E001001', param.error_detail_code)
        self.assertEqual('0', param.payment_type)
        self.assertEqual('************1111', param.card_number)

    def test_payment_type(self):
        param_card = ResultParams({
            'param_payment_type': '0'
        })
        self.assertTrue(param_card.is_card())
        self.assertFalse(param_card.is_docomo())

        param_docomo = ResultParams({
            'param_payment_type': '9'
        })
        self.assertFalse(param_docomo.is_card())
        self.assertTrue(param_docomo.is_docomo())

    def test_has_error(self):
        param = ResultParams({
            'param_error_code': 'E001'
        })
        self.assertTrue(param.has_error())

        param_no_error = ResultParams({
            'param_error_code': ''
        })
        self.assertFalse(param_no_error.has_error())

    @ddt.data('0', '9')
    def test_verify_params(self, payment_type):
        param = ResultParams({
            'param_amount': '1000',
            'param_tax': '80',
            'param_currency': 'JPY',
            'param_payment_type': payment_type,
        })

        # Before, amount and tax is string
        self.assertEqual('1000', param.amount)
        self.assertEqual('80', param.tax)

        param.verify_params()

        # After, amount and tax to be int
        self.assertEqual(1000, param.amount)
        self.assertEqual(80, param.tax)

    def test_verify_params_invalid_payment_type(self):
        param = ResultParams({
            'param_payment_type': '999',
        })

        with self.assertRaises(CCProcessorDataException) as cm:
            param.verify_params()

        self.assertEqual(
            u"The payment processor did not support payment_type 999",
            cm.exception.message
        )

    @ddt.data('amount', 'tax', 'currency')
    def test_verify_params_missing_param(self, missing_param):
        _response = {
            'param_amount': '1000',
            'param_tax': '80',
            'param_currency': 'JPY',
            'param_payment_type': '0',
        }
        del _response['param_{}'.format(missing_param)]

        param = ResultParams(_response)

        with self.assertRaises(CCProcessorDataException) as cm:
            param.verify_params()

        self.assertEqual(
            u"The payment processor did not return a required parameter: {}".format(missing_param),
            cm.exception.message
        )

    @ddt.data('amount', 'tax')
    def test_verify_params_invalid_int_param(self, invalid_param):
        _response = {
            'param_amount': '1000',
            'param_tax': '80',
            'param_currency': 'JPY',
            'param_payment_type': '0',
        }
        _response['param_{}'.format(invalid_param)] = 'invalid_int_value'

        param = ResultParams(_response)

        with self.assertRaises(CCProcessorDataException) as cm:
            param.verify_params()

        self.assertEqual(
            u"The payment processor returned a badly-typed value {} for parameter {}.".format(
                'invalid_int_value', invalid_param
            ),
            cm.exception.message
        )

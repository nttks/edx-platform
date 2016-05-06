
from collections import OrderedDict
import ddt
import json
from mock import patch

from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.utils import override_settings

from opaque_keys.edx.keys import CourseKey
from shoppingcart.models import Order, OrderItem
from shoppingcart.processors.GMO import create_order_id
from student.tests.factories import UserFactory

from ga_advanced_course.tests.factories import AdvancedF2FCourseFactory, AdvancedCourseTicketFactory
from ga_shoppingcart.models import AdvancedCourseItem


@override_settings(
    CC_PROCESSOR_NAME='GMO',
    CC_PROCESSOR={
        'GMO': {
            'ACCESS_KEY': 'test_access_key',
            'ORDER_ID_PREFIX': 'ga-test',
            'NOTIFICATION_PARAMS_MAP': {
                'p001': 'param_shop_id',
                'p005': 'param_order_id',
                'p006': 'param_status',
                'p007': 'param_job',
                'p008': 'param_amount',
                'p009': 'param_tax',
                'p010': 'param_currency',
                'p017': 'param_error_code',
                'p018': 'param_error_detail_code',
                'p019': 'param_payment_type',
            }
        }
    }
)
@ddt.ddt
class NotificationViewTest(TestCase):

    PRICE = 1000
    TAX = 80

    def setUp(self):
        super(NotificationViewTest, self).setUp()
        self.course_id = CourseKey.from_string('course-v1:org+course_{}+run'.format(self._testMethodName))
        self.user = UserFactory.create()
        self.ticket = AdvancedCourseTicketFactory.create(
            advanced_course=AdvancedF2FCourseFactory.create(course_id=self.course_id),
            price=self.PRICE
        )
        self.order = Order.get_cart_for_user(self.user)
        self.item = AdvancedCourseItem.add_to_order(self.order, self.ticket)
        self.order.start_purchase()

        self.params = OrderedDict({
            'param_shop_id': 'test_access_key',
            'param_order_id': create_order_id(self.order),
            'param_amount': str(self.order.total_cost),
            'param_tax': str(self.order.total_tax),
            'param_currency': 'JPN',
            'param_error_code': '',
            'param_error_detail_code': '',
            'param_payment_type': '0',
        })

    def _access_notify(self, data):
        return self.client.post(reverse('ga_shoppingcart:notify'), data=data)

    def _assert_response(self, response, logger, success=True):
        self.assertEqual(200, response.status_code)
        self.assertEqual('0', response.content)

        if success:
            logger.info.assert_called_with("Success to process of notification from GMO.")
        else:
            logger.exception.assert_called_with("Failed to process of notification from GMO.")

    @patch('ga_shoppingcart.views.log')
    @patch('ga_shoppingcart.notifications.log')
    @patch('ga_shoppingcart.order_helpers.log')
    @patch.object(AdvancedCourseItem, 'purchased_callback')
    @ddt.data(
        ('0', 'CAPTURE', 'CAPTURE'),
        ('9', 'CAPTURE', 'CAPTURE'),
    )
    @ddt.unpack
    def test_notify_capture(self, payment_type, job, status, purchased_callback, o_logger, n_logger, v_logger):
        self.params.update({
            'param_payment_type': payment_type,
            'param_status': status,
            'param_job': job,
        })

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger)

        order = Order.objects.get(pk=self.order.id)
        self.assertEqual('purchased', order.status)
        self.assertItemsEqual(self.params, json.loads(order.processor_reply_dump))

        purchased_callback.assert_called_with()
        n_logger.info.assert_called_with("We received the notification of the CAPTURE success.")
        o_logger.info.assert_called_with(
            "Order({}) is not purchased yet. Run the purchase process.".format(self.order.id)
        )

    @patch('ga_shoppingcart.views.log')
    @patch('ga_shoppingcart.notifications.log')
    @patch('ga_shoppingcart.order_helpers.log')
    @patch.object(AdvancedCourseItem, 'purchased_callback')
    @ddt.data(
        ('0', 'CAPTURE', 'CAPTURE'),
        ('9', 'CAPTURE', 'CAPTURE'),
    )
    @ddt.unpack
    def test_notify_capture_already_purchased(
        self, payment_type, job, status, purchased_callback, o_logger, n_logger, v_logger
    ):
        self.params.update({
            'param_payment_type': payment_type,
            'param_status': status,
            'param_job': job,
        })

        # Make status of order to be purchased
        self.order.status = 'purchased'
        self.order.processor_reply_dump = 'processor_reply_dump'
        self.order.save()
        for item in self.order.orderitem_set.all():
            item.status = 'purchased'
            item.save()

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger)

        order = Order.objects.get(pk=self.order.id)
        self.assertEqual('purchased', order.status)
        # Verify that processor_reply_dump has not been overwritten
        self.assertEqual('processor_reply_dump', order.processor_reply_dump)

        purchased_callback.assert_not_called()
        n_logger.info.assert_called_with("We received the notification of the CAPTURE success.")
        o_logger.info.assert_called_with("Update of the payment information only.")

    @patch('ga_shoppingcart.views.log')
    @patch('ga_shoppingcart.notifications.log')
    def test_notify_capture_ignore(self, n_logger, v_logger):
        # docomo paying notify REQSUCCESS
        self.params.update({
            'param_payment_type': '9',
            'param_status': 'REQSUCCESS',
            'param_job': 'CAPTURE',
        })

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger)

        order = Order.objects.get(pk=self.order.id)
        self.assertEqual('paying', order.status)
        self.assertEqual('', order.processor_reply_dump)

        n_logger.info.assert_called_with("We received the notification of the CAPTURE, but do nothing.")

    @patch('ga_shoppingcart.views.log')
    def test_notify_capture_unknown_status(self, v_logger):
        self.params.update({
            'param_status': 'TEST',
            'param_job': 'CAPTURE',
        })

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger, success=False)

    @patch('ga_shoppingcart.views.log')
    @patch('ga_shoppingcart.notifications.log')
    @ddt.data(
        ('0', 'VOID', 'VOID'),
        ('0', 'RETURN', 'RETURN'),
        ('0', 'RETURNX', 'RETURNX'),
        ('9', 'CANCEL', 'CANCEL'),
    )
    @ddt.unpack
    def test_notify_cancel(self, payment_type, job, status, n_logger, v_logger):
        self.params.update({
            'param_payment_type': payment_type,
            'param_status': status,
            'param_job': job,
        })

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger)

        order = Order.objects.get(pk=self.order.id)
        self.assertEqual('refunded', order.status)

        n_logger.info.assert_called_with("We received the notification of the CANCEL success.")

    @patch('ga_shoppingcart.views.log')
    @ddt.data(
        ('0', 'VOID', 'TEST'),
        ('0', 'RETURN', 'TEST'),
        ('0', 'RETURNX', 'TEST'),
        ('9', 'CANCEL', 'TEST'),
    )
    @ddt.unpack
    def test_notify_cancel_unknown_status(self, payment_type, job, status, v_logger):
        self.params.update({
            'param_payment_type': payment_type,
            'param_status': status,
            'param_job': job,
        })

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger, success=False)

    @patch('ga_shoppingcart.views.log')
    def test_notify_invalid_shop_id(self, v_logger):
        self.params.update({
            'param_shop_id': 'invalid_shop_id',
            'param_status': 'CAPTURE',
            'param_job': 'CAPTURE',
        })

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger, success=False)

    @patch('ga_shoppingcart.views.log')
    def test_notify_has_error(self, v_logger):
        self.params.update({
            'param_status': 'CAPTURE',
            'param_job': 'CAPTURE',
            'param_error_code': 'E001'
        })

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger, success=False)

    @patch('ga_shoppingcart.views.log')
    @ddt.data(
        ('invalid', '80'),
        ('1000', 'invalid'),
    )
    @ddt.unpack
    def test_notify_invalid_params(self, amount, tax, v_logger):
        self.params.update({
            'param_amount': amount,
            'param_tax': tax,
        })

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger, success=False)

    @patch('ga_shoppingcart.views.log')
    @ddt.data('param_amount', 'param_tax', 'param_currency')
    def test_notify_missing_params(self, param, v_logger):
        del self.params[param]
        self.params.update({
            'param_status': 'CAPTURE',
            'param_job': 'CAPTURE',
        })

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger, success=False)

    @patch('ga_shoppingcart.views.log')
    @ddt.data(
        ('1001', '80', 'JPN'),
        ('1000', '81', 'JPN'),
        ('1000', '80', 'USD'),
    )
    @ddt.unpack
    def test_notify_mismatch_params(self, amount, tax, currency, v_logger):
        self.params.update({
            'param_status': 'CAPTURE',
            'param_job': 'CAPTURE',
            'param_amount': amount,
            'param_tax': tax,
            'param_currency': currency,
        })

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger, success=False)

# -*- coding: utf-8 -*-

from collections import OrderedDict
import ddt
import json
from datetime import timedelta
from mock import patch

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import get_language

from course_modes.models import CourseMode
from courseware.tests.helpers import LoginEnrollmentTestCase
from dark_lang.models import DarkLangConfig
from lang_pref import LANGUAGE_KEY
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.user_api.preferences.api import set_user_preference
from shoppingcart.models import Order, OrderItem
from shoppingcart.processors.GMO import create_order_id
from student.tests.factories import CourseModeFactory, UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ga_advanced_course.tests.factories import AdvancedF2FCourseFactory, AdvancedCourseTicketFactory
from ga_shoppingcart.models import AdvancedCourseItem, PersonalInfo, PersonalInfoSetting
from ga_shoppingcart.tests.utils import get_order_from_advanced_course, get_order_from_paid_course


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
                'p913': 'param_docomo_cancel_amount',
                'p914': 'param_docomo_cancel_tax',
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
            'param_amount': str(int(self.order.total_cost)),
            'param_tax': str(int(self.order.total_tax)),
            'param_currency': 'JPN',
            'param_error_code': '',
            'param_error_detail_code': '',
            'param_payment_type': '0',
            'param_docomo_cancel_amount': str(int(self.order.total_cost)),
            'param_docomo_cancel_tax': str(int(self.order.total_tax)),
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
        ('0', 'CAPTURE', 'CAPTURE', 'ja-jp'),
        ('9', 'CAPTURE', 'CAPTURE', 'en'),
        ('0', 'CAPTURE', 'CAPTURE', None),
    )
    @ddt.unpack
    def test_notify_capture(self, payment_type, job, status, lang_code, purchased_callback, o_logger, n_logger, v_logger):
        self.params.update({
            'param_payment_type': payment_type,
            'param_status': status,
            'param_job': job,
        })

        if lang_code:
            DarkLangConfig(
                released_languages=('en, ja-jp'),
                changed_by=self.user,
                enabled=True
            ).save()
            set_user_preference(self.user, LANGUAGE_KEY, lang_code)

        response = self._access_notify(self.params)

        self._assert_response(response, v_logger)
        # Verify current language
        self.assertEqual(lang_code if lang_code else settings.LANGUAGE_CODE, get_language())

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
        # For assertion, to override the amount of do not use
        if payment_type == '0':
            self.params.update({
                'param_docomo_cancel_amount': '0',
                'param_docomo_cancel_tax': '0',
            })
        elif payment_type == '9':
            self.params.update({
                'param_amount': '0',
                'param_tax': '0',
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


class GaShoppingcartViewTest(LoginEnrollmentTestCase, ModuleStoreTestCase):
    def __init__(self, method_name):
        super(GaShoppingcartViewTest, self).__init__(methodName=method_name)
        self.valid_params = {
            'full_name': 'test',
            'kana': u'カナ',
            'postal_code': '1234567',
            'address_line_1': 'address1',
            'address_line_2': 'address2',
            'phone_number': '0312345678',
            'gaccatz_check': 'pc',
            'free_entry_field_1': 'field1',
            'free_entry_field_2': 'field2',
            'free_entry_field_3': 'field3',
            'free_entry_field_4': 'field4',
            'free_entry_field_5': 'field5',
        }
        self.invalid_params = {}

    def setUp(self):
        """ Create a user and course. """
        super(GaShoppingcartViewTest, self).setUp()
        self.course_for_advanced = CourseFactory.create(
            metadata={
                'is_f2f_course': True,
                'is_f2f_course_sell': True,
            }
        )
        self.course_for_paid = CourseFactory.create()
        self.course_mode = CourseModeFactory(mode_slug='no-id-professional',
                                             course_id=self.course_for_paid.id,
                                             min_price=1, sku='')

    @staticmethod
    def _create_personal_input_setting(order_id):
        item = OrderItem.objects.get_subclass(order_id=order_id)
        p = PersonalInfoSetting()
        if isinstance(item, AdvancedCourseItem):
            p.advanced_course_id = item.advanced_course_ticket.advanced_course_id
        else:
            p.course_mode = CourseMode.objects.get(
                course_id=item.course_id,
                mode_slug=item.mode,
            )
        p.save()

    def _get_choose_ticket(self, course, advanced_course_id):
        return self._access_page(reverse('advanced_course:choose_ticket', args=[course.id, advanced_course_id]))

    def _access_page(self, path, method='GET', data={}):
        if method.upper() == 'POST':
            return self.client.post(path, data)
        elif method.upper() == 'GET':
            return self.client.get(path)
        else:
            raise ValueError('Unknown Method {}'.format(method))

    @staticmethod
    def _form_view(order_id):
        return reverse('ga_shoppingcart:input_personal_info', args=[order_id])

    @staticmethod
    def _create_ticket(advanced_course, count):
        return [
            AdvancedCourseTicketFactory.create(
                advanced_course=advanced_course,
                display_name='ticket {}'.format(i)
            )
            for i in range(count)
        ]

    @staticmethod
    def _create_advanced_courses(course, count, active=True):
        return [
            AdvancedF2FCourseFactory.create(
                course_id=course.id,
                display_name='display_name {}'.format(i),
                is_active=active
            )
            for i in range(count)
        ]

    @staticmethod
    def _become_outdated_order_item(order):
        order_items = order.orderitem_set.all()
        try:
            from shoppingcart.processors.helpers import get_processor_config
            SC_SESSION_TIMEOUT = get_processor_config().get('SESSION_TIMEOUT', 600)
        except:
            SC_SESSION_TIMEOUT = 600
        for item in order_items:
            item.created = item.created - timedelta(seconds=SC_SESSION_TIMEOUT)
            item.save()

    def _get_expect_personal_info_data(self, order):
        return {
            'address_line_1': u'address1',
            'address_line_2': u'address2',
            'choice_id': 1,
            'free_entry_field_1': None,
            'free_entry_field_2': None,
            'free_entry_field_3': None,
            'free_entry_field_4': None,
            'free_entry_field_5': None,
            'full_name': u'test',
            'gaccatz_check': u'pc',
            'kana': None,
            'order_id': order.id,
            'phone_number': u'0312345678',
            'postal_code': u'1234567',
            'user_id': self.user.id
        }

    @staticmethod
    def _get_actual_personal_info_data(order):
        p = PersonalInfo.objects.get(order_id=order.id)
        actual_personal_info_data = p.__dict__.copy()
        del actual_personal_info_data['_state']
        del actual_personal_info_data['id']
        return actual_personal_info_data

    def _assert_personal_input(self, order):
        actual_personal_info_data = self._get_actual_personal_info_data(order)
        expect_personal_info_data = self._get_expect_personal_info_data(order)
        self.assertDictEqual(actual_personal_info_data, expect_personal_info_data)


class InputPersonalInfoFormPreviewTest(GaShoppingcartViewTest):
    def test_preview_get_via_advanced_course(self):
        self.setup_user()
        self.enroll(self.course_for_advanced)
        order, advanced_course = get_order_from_advanced_course(self.course_for_advanced, self.user)
        self._create_personal_input_setting(order.id)
        self._get_choose_ticket(self.course_for_advanced, advanced_course.id)

        response = self._access_page(self._form_view(order.id))

        self.assertEqual(200, response.status_code)

    def test_preview_get_via_advanced_course_404(self):
        self.setup_user()
        self.enroll(self.course_for_advanced)
        order, advanced_course = get_order_from_advanced_course(self.course_for_advanced, self.user)
        self._create_personal_input_setting(order.id)
        self._get_choose_ticket(self.course_for_advanced, advanced_course.id)
        self._become_outdated_order_item(order)

        response = self._access_page(self._form_view(order.id))

        self.assertEqual(404, response.status_code)

    def test_preview_get_via_paid_course(self):
        self.setup_user()
        self.enroll(self.course_for_paid)
        order = get_order_from_paid_course(self.course_mode, self.course_for_paid, self.user)
        self._create_personal_input_setting(order.id)

        response = self._access_page(self._form_view(order.id))

        self.assertEqual(200, response.status_code)

    def test_preview_get_via_paid_course_404(self):
        self.setup_user()
        self.enroll(self.course_for_paid)
        order = get_order_from_paid_course(self.course_mode, self.course_for_paid, self.user)
        self._create_personal_input_setting(order.id)
        self._become_outdated_order_item(order)

        response = self._access_page(self._form_view(order.id))

        self.assertEqual(404, response.status_code)

    @patch('ga_shoppingcart.views.InputPersonalInfoFormPreview.security_hash', return_value='dummy_hash')
    def test_preview_post_form_valid(self, security_hash_mock):
        self.setup_user()
        self.enroll(self.course_for_paid)
        order = get_order_from_paid_course(self.course_mode, self.course_for_paid, self.user)
        self._create_personal_input_setting(order.id)

        response = self._access_page(self._form_view(order.id), 'POST', self.valid_params)

        self.assertEquals(200, response.status_code)
        self.assertTrue(security_hash_mock.called)
        self.assertIn('name="hash"', response.content)
        self.assertIn('value="dummy_hash"', response.content)

    @patch('ga_shoppingcart.views.InputPersonalInfoFormPreview.security_hash', return_value='dummy_hash')
    def test_preview_post_form_invalid(self, security_hash_mock):
        self.setup_user()
        self.enroll(self.course_for_paid)
        order = get_order_from_paid_course(self.course_mode, self.course_for_paid, self.user)
        self._create_personal_input_setting(order.id)

        response = self._access_page(self._form_view(order.id), 'POST', self.invalid_params)

        self.assertEqual(200, response.status_code)
        self.assertFalse(security_hash_mock.called)
        self.assertNotIn('name="hash"', response.content)
        self.assertNotIn('value="dummy_hash"', response.content)

    @patch('ga_shoppingcart.views.InputPersonalInfoFormPreview.security_hash', return_value='dummy_hash')
    def test_preview_post_turn_back_input_form(self, security_hash_mock):
        cancel_params = self.valid_params.copy()
        cancel_params.update({'cancel': 'true'})
        self.setup_user()
        self.enroll(self.course_for_paid)
        order = get_order_from_paid_course(self.course_mode, self.course_for_paid, self.user)
        self._create_personal_input_setting(order.id)

        response = self._access_page(self._form_view(order.id), 'POST', cancel_params)

        self.assertEquals(200, response.status_code)
        self.assertFalse(security_hash_mock.called)
        self.assertNotIn('name="hash"', response.content)
        self.assertNotIn('value="dummy_hash"', response.content)

    @patch('ga_shoppingcart.views.InputPersonalInfoFormPreview._check_security_hash', return_value=True)
    def test_post_post_form_valid_for_advanced_course(self, _check_security_hash_mock):
        valid_params_stage2 = self.valid_params.copy()
        valid_params_stage2.update({'stage': 2})
        self.setup_user()
        self.enroll(self.course_for_paid)
        order, advanced_course = get_order_from_advanced_course(self.course_for_advanced, self.user)
        self._create_personal_input_setting(order.id)

        response = self._access_page(self._form_view(order.id), 'POST', valid_params_stage2)

        self.assertEquals(200, response.status_code)
        self.assertIn(str(reverse('advanced_course:checkout')), response.content)
        _check_security_hash_mock.assert_called()
        self._assert_personal_input(order)

    @patch('ga_shoppingcart.views.InputPersonalInfoFormPreview._check_security_hash', return_value=True)
    def test_post_post_form_valid_for_paid_course(self, _check_security_hash_mock):
        valid_params_stage2 = self.valid_params.copy()
        valid_params_stage2.update({'stage': 2})
        self.setup_user()
        self.enroll(self.course_for_paid)
        order = get_order_from_paid_course(self.course_mode, self.course_for_paid, self.user)
        self._create_personal_input_setting(order.id)

        response = self._access_page(self._form_view(order.id), 'POST', valid_params_stage2)

        self.assertEquals(200, response.status_code)
        self.assertIn(str(reverse('verify_student_checkout')), response.content)
        _check_security_hash_mock.assert_called()
        self._assert_personal_input(order)

    @patch('ga_shoppingcart.views.InputPersonalInfoFormPreview.done')
    @patch('ga_shoppingcart.views.InputPersonalInfoFormPreview._check_security_hash', return_value=True)
    def test_post_post_form_invalid(self, _check_security_hash_mock, done_mock):
        invalid_params_stage2 = self.invalid_params.copy()
        invalid_params_stage2.update({'stage': 2})
        self.setup_user()
        self.enroll(self.course_for_paid)
        order = get_order_from_paid_course(self.course_mode, self.course_for_paid, self.user)
        self._create_personal_input_setting(order.id)

        response = self._access_page(self._form_view(order.id), 'POST', invalid_params_stage2)

        self.assertEquals(200, response.status_code)
        _check_security_hash_mock.assert_not_called()
        done_mock.assert_not_called()
        self.assertIn('name="stage"', response.content)
        self.assertIn('value="1"', response.content)

    @patch('ga_shoppingcart.views.InputPersonalInfoFormPreview.done')
    @patch('ga_shoppingcart.views.InputPersonalInfoFormPreview._check_security_hash', return_value=False)
    def test_post_post_security_hash_failed(self, _check_security_hash_mock, done_mock):
        valid_params_stage2 = self.valid_params.copy()
        valid_params_stage2.update({'stage': 2})
        self.setup_user()
        self.enroll(self.course_for_paid)
        order, advanced_course = get_order_from_advanced_course(self.course_for_advanced, self.user)
        self._create_personal_input_setting(order.id)

        response = self._access_page(self._form_view(order.id), 'POST', valid_params_stage2)

        self.assertEquals(200, response.status_code)
        self.assertIn('name="stage"', response.content)
        self.assertIn('value="2"', response.content)
        _check_security_hash_mock.assert_called()
        done_mock.assert_not_called()



from datetime import timedelta
import ddt
import json
from mock import patch

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils import timezone

from courseware.tests.helpers import LoginEnrollmentTestCase
from shoppingcart.models import OrderItem
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ga_shoppingcart.models import AdvancedCourseItem, PersonalInfoSetting
from ga_shoppingcart.utils import SC_SESSION_TIMEOUT

from ga_advanced_course.models import AdvancedCourseTypes
from ga_advanced_course.tests.factories import AdvancedF2FCourseFactory, AdvancedCourseTicketFactory
from ga_advanced_course.tests.utils import purchase_ticket, start_purchase_ticket, make_ticket_to_out_of_sale


@ddt.ddt
class CourseCheckMixin(object):

    def get_course_check_response(self):
        raise NotImplementedError()

    @ddt.data(
        (True, False),
        (False, True),
        (False, False),
    )
    @ddt.unpack
    def test_course_not_f2f(self, is_f2f_course, is_f2f_course_sell):
        self.setup_user()

        self.course.is_f2f_course = is_f2f_course
        self.course.is_f2f_course_sell = is_f2f_course_sell
        self.update_course(self.course, self.user.id)

        self.enroll(self.course)

        response = self.get_course_check_response()

        self.assertEqual(404, response.status_code)

    def test_course_not_enrolled(self):
        self.setup_user()

        self._assert_redirect_to_course_about(
            self.get_course_check_response()
        )

    def test_course_not_enrollable(self):
        self.setup_user()
        self.enroll(self.course)

        # Make enrollment start to the future
        self.course.enrollment_start = timezone.now() + timedelta(days=1)
        self.update_course(self.course, self.user.id)

        response = self.get_course_check_response()

        self.assertEqual(404, response.status_code)


class TicketCheckMixin(object):

    def get_ticket_check_response(self, advanced_courses, tickets):
        raise NotImplementedError()

    def test_ticket_purchased(self):
        advanced_courses = self._create_advanced_courses(self.course, 2)
        tickets = self._create_ticket(advanced_courses[0], 2)

        self.setup_user()
        self.enroll(self.course)

        # purchase
        purchase_ticket(self.user, tickets[0])

        response = self.get_ticket_check_response(advanced_courses, tickets)

        self._assert_redirect_to_courses(response, advanced_courses[0])

    def test_ticket_full(self):
        advanced_courses = self._create_advanced_courses(self.course, 2)
        tickets = self._create_ticket(advanced_courses[0], 2)

        # Make course to be full
        for _ in range(advanced_courses[0].capacity):
            purchase_ticket(UserFactory.create(), tickets[0])

        self.setup_user()
        self.enroll(self.course)

        response = self.get_ticket_check_response(advanced_courses, tickets)

        self._assert_redirect_to_courses(response, advanced_courses[0])

    def test_ticket_full_with_paying(self):
        advanced_courses = self._create_advanced_courses(self.course, 2)
        tickets = self._create_ticket(advanced_courses[0], 2)

        # Make advanced_course to full
        for _ in range(advanced_courses[0].capacity - 1):
            purchase_ticket(UserFactory.create(), tickets[0])
        start_purchase_ticket(UserFactory.create(), tickets[1])

        self.setup_user()
        self.enroll(self.course)

        response = self.get_ticket_check_response(advanced_courses, tickets)

        self._assert_redirect_to_courses(response, advanced_courses[0])

    def test_ticket_end_of_sale(self):
        advanced_courses = self._create_advanced_courses(self.course, 2)
        tickets = self._create_ticket(advanced_courses[0], 2)

        # Make ticket to be end-of-sale
        for ticket in tickets:
            make_ticket_to_out_of_sale(ticket)

        self.setup_user()
        self.enroll(self.course)

        response = self.get_ticket_check_response(advanced_courses, tickets)

        self._assert_redirect_to_courses(response, advanced_courses[0])


class OrderCheckMixin(object):

    def get_order_check_response(self, order_id):
        raise NotImplementedError()

    def test_order_not_exists(self):
        advanced_course = self._create_advanced_courses(self.course, 1)[0]
        self._create_ticket(advanced_course, 2)[0]

        self.setup_user()

        response = self.get_order_check_response(99999)

        self.assertEqual(404, response.status_code)

    def test_order_not_paying(self):
        advanced_course = self._create_advanced_courses(self.course, 1)[0]
        ticket = self._create_ticket(advanced_course, 2)[0]

        self.setup_user()

        order = purchase_ticket(self.user, ticket)

        # purchased
        response = self.get_order_check_response(order.id)

        self.assertEqual(404, response.status_code)

        # cart
        order.status = 'cart'
        order.save()

        response = self.get_order_check_response(order.id)

        self.assertEqual(404, response.status_code)

        # refunded
        order.status = 'refunded'
        order.save()

        response = self.get_order_check_response(order.id)

        self.assertEqual(404, response.status_code)

    def test_order_by_another_user(self):
        advanced_course = self._create_advanced_courses(self.course, 1)[0]
        ticket = self._create_ticket(advanced_course, 2)[0]

        self.setup_user()

        order = start_purchase_ticket(UserFactory.create(), ticket)

        response = self.get_order_check_response(order.id)

        self.assertEqual(404, response.status_code)

    def test_order_invalid(self):
        advanced_course = self._create_advanced_courses(self.course, 1)[0]
        ticket = self._create_ticket(advanced_course, 2)[0]

        self.setup_user()

        order = start_purchase_ticket(self.user, ticket)
        _item = order.orderitem_set.all()[0]
        _item.created = _item.created - timedelta(seconds=SC_SESSION_TIMEOUT)
        _item.save()

        response = self.get_order_check_response(order.id)

        self.assertEqual(404, response.status_code)


class AdvancedCourseViewTest(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Base Class for views of advanced course.
    """
    def setUp(self):
        super(AdvancedCourseViewTest, self).setUp()

        self.course = CourseFactory.create(
            metadata={
                'is_f2f_course': True,
                'is_f2f_course_sell': True,
            }
        )

    def _create_advanced_courses(self, course, count, active=True):
        return [
            AdvancedF2FCourseFactory.create(
                course_id=course.id,
                display_name='display_name {}'.format(i),
                is_active=active
            )
            for i in range(count)
        ]

    def _create_ticket(self, advanced_course, count):
        return [
            AdvancedCourseTicketFactory.create(
                advanced_course=advanced_course,
                display_name='ticket {}'.format(i)
            )
            for i in range(count)
        ]

    def _access_page(self, path, method='GET', data={}):
        if method.upper() == 'POST':
            return self.client.post(path, data)
        elif method.upper() == 'GET':
            return self.client.get(path)
        else:
            raise ValueError('Unknown Method {}'.format(method))

    def _assert_redirect(self, response, path):
        self.assertEqual(302, response.status_code)
        self.assertTrue(response['Location'].endswith(path))

    def _assert_redirect_to_course_about(self, response, course=None):
        if not course:
            course = self.course
        self._assert_redirect(response, reverse('about_course', args=[course.id.to_deprecated_string()]))

    def _assert_redirect_to_courses(self, response, advanced_course, course=None):
        if not course:
            course = self.course
        path = reverse('advanced_course:courses_{}'.format(advanced_course.course_type), args=[course.id])
        self._assert_redirect(response, path)

    def _assert_redirect_to_choose_ticket(self, response, ticket, course=None):
        if not course:
            course = self.course
        path = reverse('advanced_course:choose_ticket', args=[course.id, ticket.id])
        self._assert_redirect(response, path)

    def _create_personal_input_setting(self, advanced_course):
        p = PersonalInfoSetting()
        p.advanced_course = advanced_course
        p.save()


@ddt.ddt
class AdvancedCourseChooseViewTest(AdvancedCourseViewTest):
    """
    Tests for choose_advanced_course
    """
    def _get_choose_advanced_course(self, course):
        return self._access_page(reverse('advanced_course:choose', args=[course.id]))

    @ddt.data(
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    )
    @ddt.unpack
    def test_choose_advanced_course(self, is_f2f_course, is_f2f_course_sell):
        self.setup_user()

        self.course.is_f2f_course = is_f2f_course
        self.course.is_f2f_course_sell = is_f2f_course_sell
        self.update_course(self.course, self.user.id)

        self.enroll(self.course)

        response = self._get_choose_advanced_course(self.course)
        expected_count = 1 + (1 if is_f2f_course and is_f2f_course_sell else 0)

        self.assertEqual(200, response.status_code)
        self.assertIn("Enroll course selection", response.content)
        self.assertIn("Thank you for an enroll. This course has {} courses.".format(expected_count), response.content)
        if is_f2f_course and is_f2f_course_sell:
            self.assertIn("Face-to-Face Course", response.content)
        else:
            self.assertNotIn("Face-to-Face Course", response.content)
        self.assertIn("Online Course (Free of charge)", response.content)

    def test_choose_advanced_course_not_enrolled(self):
        self.setup_user()

        self._assert_redirect_to_course_about(
            self._get_choose_advanced_course(self.course)
        )

    def test_choose_advanced_course_not_course_enrollable(self):
        self.setup_user()
        self.enroll(self.course)

        # Make enrollment start to the future
        self.course.enrollment_start = timezone.now() + timedelta(days=1)
        self.update_course(self.course, self.user.id)

        response = self._get_choose_advanced_course(self.course)

        self.assertEqual(404, response.status_code)


class AdvancedCourseF2FCoursesViewTest(CourseCheckMixin, AdvancedCourseViewTest):
    """
    Test for advanced_courses_face_to_face
    """

    def _get_advanced_courses(self, course, course_type=AdvancedCourseTypes.F2F):
        return self._access_page(reverse('advanced_course:courses_{}'.format(course_type), args=[course.id]))

    def get_course_check_response(self):
        return self._get_advanced_courses(self.course)

    def test_advanced_courses(self):
        advanced_courses = self._create_advanced_courses(self.course, 2)

        self.setup_user()
        self.enroll(self.course)

        response = self._get_advanced_courses(self.course)

        self.assertEqual(200, response.status_code)
        self.assertIn("Details of Face to face course", response.content)
        self.assertNotIn("purchase_error", response.content)

        for course in advanced_courses:
            self.assertIn(course.display_name, response.content)

    def test_advanced_courses_not_exists(self):
        advanced_courses = self._create_advanced_courses(self.course, 2, active=False)

        self.setup_user()
        self.enroll(self.course)

        response = self._get_advanced_courses(self.course)

        self.assertEqual(404, response.status_code)


class AdvancedCourseChooseTicketViewTest(CourseCheckMixin, TicketCheckMixin, AdvancedCourseViewTest):
    """
    Tests for choose_ticket
    """
    def _get_choose_ticket(self, course, advanced_course_id):
        return self._access_page(reverse('advanced_course:choose_ticket', args=[course.id, advanced_course_id]))

    def get_course_check_response(self):
        advanced_courses = self._create_advanced_courses(self.course, 2)
        return self._get_choose_ticket(self.course, advanced_courses[0].id)

    def get_ticket_check_response(self, advanced_courses, tickets):
        return self._get_choose_ticket(self.course, advanced_courses[0].id)

    def test_choose_ticket(self):
        advanced_courses = self._create_advanced_courses(self.course, 2)
        self._create_ticket(advanced_courses[0], 2)

        self.setup_user()
        self.enroll(self.course)

        response = self._get_choose_ticket(self.course, advanced_courses[0].id)

        self.assertEqual(200, response.status_code)
        self.assertIn("Ticket Selection", response.content)
        self.assertIn(advanced_courses[0].display_name, response.content)
        self.assertNotIn('purchase_error', response.content)

    def test_choose_ticket_not_exists(self):
        advanced_courses = self._create_advanced_courses(self.course, 2, active=False)
        self._create_ticket(advanced_courses[0], 2)

        self.setup_user()
        self.enroll(self.course)

        response = self._get_choose_ticket(self.course, advanced_courses[0].id)

        self.assertEqual(404, response.status_code)

    def test_choose_ticket_bad_course_id(self):
        advanced_courses = self._create_advanced_courses(self.course, 2)
        self._create_ticket(advanced_courses[0], 2)

        bad_course = CourseFactory.create(
            metadata={
                'is_f2f_course': True,
                'is_f2f_course_sell': True,
            }
        )
        bad_advanced_courses = self._create_advanced_courses(bad_course, 2)
        self._create_ticket(bad_advanced_courses[0], 2)

        self.setup_user()
        self.enroll(self.course)

        response = self._get_choose_ticket(self.course, bad_advanced_courses[0].id)

        self.assertEqual(404, response.status_code)


class AdvancedCoursePurchaseTicketViewTest(CourseCheckMixin, TicketCheckMixin, AdvancedCourseViewTest):
    """
    Tests for purchase_ticket
    """
    def _get_purchase_ticket(self, course, ticket_id):
        path = reverse('advanced_course:purchase_ticket', args=[course.id, ticket_id])
        return self._access_page(path)

    def _assert_purchase_ticket_response(self, response, ticket, user, viewname):
        item = OrderItem.objects.get_subclass(
            user=user.id,
            status='paying',
            order__status='paying'
        )

        self.assertTrue(isinstance(item, AdvancedCourseItem))
        self.assertEqual(item.advanced_course_ticket, ticket)

        path = reverse(viewname, args=[item.id])
        self._assert_redirect(response, path)

    def get_course_check_response(self):
        advanced_course = self._create_advanced_courses(self.course, 2)[0]
        tickets = self._create_ticket(advanced_course, 2)
        return self._get_purchase_ticket(self.course, tickets[0].id)

    def get_ticket_check_response(self, advanced_courses, tickets):
        return self._get_purchase_ticket(self.course, tickets[0].id)

    def test_purchase_ticket(self):
        advanced_course = self._create_advanced_courses(self.course, 2)[0]
        ticket = self._create_ticket(advanced_course, 2)[0]

        # Make advanced_course to full just before
        for _ in range(advanced_course.capacity - 1):
            purchase_ticket(UserFactory.create(), ticket)

        self.setup_user()
        self.enroll(self.course)

        response = self._get_purchase_ticket(self.course, ticket.id)

        self._assert_purchase_ticket_response(response, ticket, self.user, 'advanced_course:checkout_ticket')

    def test_purchase_ticket_when_required_personal_info(self):
        advanced_course = self._create_advanced_courses(self.course, 2)[0]
        ticket = self._create_ticket(advanced_course, 2)[0]
        self._create_personal_input_setting(advanced_course)

        # Make advanced_course to full just before
        for _ in range(advanced_course.capacity - 1):
            purchase_ticket(UserFactory.create(), ticket)

        self.setup_user()
        self.enroll(self.course)

        response = self._get_purchase_ticket(self.course, ticket.id)

        self._assert_purchase_ticket_response(response, ticket, self.user, 'ga_shoppingcart:input_personal_info')

    def test_purchase_ticket_not_exists(self):
        advanced_course = self._create_advanced_courses(self.course, 2, active=False)[0]
        ticket = self._create_ticket(advanced_course, 2)[0]

        self.setup_user()
        self.enroll(self.course)

        response = self._get_purchase_ticket(self.course, ticket.id)

        self.assertEqual(404, response.status_code)

    def test_purchaseticket_bad_course_id(self):
        advanced_courses = self._create_advanced_courses(self.course, 2)
        self._create_ticket(advanced_courses[0], 2)

        bad_course = CourseFactory.create(
            metadata={
                'is_f2f_course': True,
                'is_f2f_course_sell': True,
            }
        )
        bad_advanced_courses = self._create_advanced_courses(bad_course, 2)
        ticket = self._create_ticket(bad_advanced_courses[0], 2)[0]

        self.setup_user()
        self.enroll(self.course)

        response = self._get_purchase_ticket(self.course, bad_advanced_courses[0].id)

        self.assertEqual(404, response.status_code)

    def test_ticket_end_of_sale(self):
        advanced_course = self._create_advanced_courses(self.course, 2)[0]
        ticket = self._create_ticket(advanced_course, 2)[0]

        # Make ticket to be out-of-sale
        make_ticket_to_out_of_sale(ticket)

        self.setup_user()
        self.enroll(self.course)

        response = self._get_purchase_ticket(self.course, ticket.id)

        self._assert_redirect_to_choose_ticket(response, ticket)


class AdvancedCourseCheckoutTicketViewTest(OrderCheckMixin, AdvancedCourseViewTest):
    """
    Tests for checkout_ticket
    """
    def _access_checkout_ticket(self, order_id, method='GET'):
        path = reverse('advanced_course:checkout_ticket', args=[order_id])
        return self._access_page(path, method)

    def get_order_check_response(self, order_id):
        return self._access_checkout_ticket(order_id)

    def test_checkout_ticket(self):
        advanced_course = self._create_advanced_courses(self.course, 1)[0]
        ticket = self._create_ticket(advanced_course, 2)[0]

        self.setup_user()

        order = start_purchase_ticket(self.user, ticket)

        response = self._access_checkout_ticket(order.id)

        self.assertEqual(200, response.status_code)
        self.assertIn('Processing', response.content)

    def test_checkout_ticket_not_allowed_method(self):
        advanced_course = self._create_advanced_courses(self.course, 1)[0]
        ticket = self._create_ticket(advanced_course, 2)[0]

        self.setup_user()

        order = start_purchase_ticket(self.user, ticket)

        response = self._access_checkout_ticket(order.id, method='POST')

        self.assertEqual(405, response.status_code)


class AdvancedCourseCheckoutViewTest(OrderCheckMixin, AdvancedCourseViewTest):
    """
    Tests for checkout
    """
    def _access_checkout(self, order_id, method='POST'):
        path = reverse('advanced_course:checkout')
        return self._access_page(path, method, {'order_id': order_id})

    def get_order_check_response(self, order_id):
        return self._access_checkout(order_id)

    def test_checkout(self):

        def _mock_get_signed_purchase_params(cart, callback_url=None, extra_data=None):
            return {
                'order_id': cart.id, 'callback_url': callback_url, 'extra_data': extra_data
            }

        advanced_course = self._create_advanced_courses(self.course, 1)[0]
        ticket = self._create_ticket(advanced_course, 2)[0]

        self.setup_user()

        order = start_purchase_ticket(self.user, ticket)

        with patch(
            'ga_advanced_course.views.get_signed_purchase_params',
            side_effect=_mock_get_signed_purchase_params
        ) as mock:
            response = self._access_checkout(order.id)
            self.assertEqual(1, mock.call_count)

        self.assertEqual(200, response.status_code)

        content = json.loads(response.content)
        self.assertEqual(settings.CC_PROCESSOR_NAME, content['payment_processor_name'])
        self.assertEqual('/shoppingcart/payment_fake', content['payment_page_url'])
        self.assertItemsEqual({
            'order_id': order.id,
            'callback_url': (
                reverse('shoppingcart.views.postpay_callback'),
                reverse('advanced_course:courses_face_to_face', args=[self.course.id])
            ),
            'extra_data': [
                '{} {}'.format(advanced_course.display_name, ticket.display_name),
                str(self.course.id),
                self.user.id
            ]
        }, content['payment_form_data'])

    def test_checkout_not_allowed_method(self):
        advanced_course = self._create_advanced_courses(self.course, 1)[0]
        ticket = AdvancedCourseTicketFactory.create(advanced_course=advanced_course)

        self.setup_user()

        order = start_purchase_ticket(self.user, ticket)

        response = self._access_checkout(order.id, method='GET')

        self.assertEqual(405, response.status_code)

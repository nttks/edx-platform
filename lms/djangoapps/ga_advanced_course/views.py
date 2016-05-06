"""
Views for advanced courses
"""

from functools import wraps
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST

from courseware.courses import course_image_url, get_course_with_access
from courseware.views import registered_for_course
from edxmako.shortcuts import render_to_response
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from shoppingcart.models import Order
from shoppingcart.processors import (
    get_signed_purchase_params, get_purchase_endpoint
)
from util.json_request import JsonResponse, JsonResponseBadRequest

from ga_advanced_course.exceptions import InvalidOrder
from ga_advanced_course.status import AdvancedCourseStatus
from ga_advanced_course.models import AdvancedCourseTypes, AdvancedCourse, AdvancedCourseTicket
from ga_advanced_course.utils import (
    is_advanced_course_purchased,
    is_advanced_course_full,
    is_advanced_course_end_of_sale,
    check_order_can_purchase,
    disable_upsell,
)
from ga_shoppingcart.models import AdvancedCourseItem

log = logging.getLogger(__name__)


def _get_course_with_access(user, action, course_key, depth=0, check_if_enrolled=False):
    """
    Get modulestore's course by course_id (not only str but also CourseKey)

    :param course_id: course_id (str or CourseKey): Id for the course
    :return: A course object
    """
    if not isinstance(course_key, CourseKey):
        try:
            course_key = CourseKey.from_string(course_key)
        except InvalidKeyError:
            raise Http404("Invalid course_id({})".format(unicode(course_key)))

    return get_course_with_access(user, action, course_key, depth, check_if_enrolled)


def _get_f2f_course_with_access(user, action, course_key, depth=0, check_if_enrolled=False):
    course = _get_course_with_access(user, action, course_key, depth, check_if_enrolled)
    if not (course.is_f2f_course and course.is_f2f_course_sell):
        raise Http404()
    return course


def _redirect_to_advanced_courses(course_id, course_type):
    return redirect(reverse('advanced_course:courses_{}'.format(course_type), args=[course_id]))


def _get_advanced_course(advanced_course_id):
    try:
        return AdvancedCourse.get_advanced_course(advanced_course_id)
    except AdvancedCourse.DoesNotExist:
        log.warning("No advanced course. advanced_course_id={}".format(advanced_course_id))
        raise Http404


def _get_advanced_course_ticket(ticket_id):
    try:
        return AdvancedCourseTicket.get_by_id(ticket_id)
    except AdvancedCourseTicket.DoesNotExist:
        log.warning("No advanced course ticket. ticket_id={ticket_id}".format(ticket_id=ticket_id))
        raise Http404()


def _get_user_paying_cart(user, order_id):
    """
    Returns order object related with specified user and order_id.

    An order must be available and status of order must be `paying`.
    And order must have been created by specified user.
    """
    try:
        order = Order.objects.get(pk=order_id, status='paying')
    except Order.DoesNotExist:
        log.warning(
            "No paying order for user_id={user_id}, order_id={order_id}".format(
                user_id=user.id, order_id=order_id
            )
        )
        raise Http404()

    if user != order.user:
        log.warning("User and order not match user={user_id}, order_user={order_user_id}".format(
            user_id=user.id, order_user_id=order.user.id
        ))
        raise Http404()

    try:
        check_order_can_purchase(order)
    except InvalidOrder:
        # TODO it should be notified of the message to the user. But now, only purchase immediately.
        # In the future, we have plan to implement re-authentication and implement notify page at the same time.
        raise Http404()

    return order


def _check_for_purchase(request, advanced_course, tickets):
    # If the following conditions are true, user can not press the subscribe button on ths list page.
    # But there is likely to be executed in the time difference.
    if is_advanced_course_purchased(request.user, advanced_course):
        log.warning(
            'User ({user_id}) try to choose tickets of advanced course ({advanced_course_id}), but aleady purchased.'.format(
                user_id=request.user.id, advanced_course_id=advanced_course.id
            )
        )
        messages.warning(request, _("Tickets are already purchased."))
        return False
    elif is_advanced_course_full(advanced_course):
        log.warning(
            'User ({user_id}) try to choose tickets of advanced course ({advanced_course_id}), but aleady full.'.format(
                user_id=request.user.id, advanced_course_id=advanced_course.id
            )
        )
        messages.warning(request, _("Sorry, could not buy a ticket because it reached a capacity."))
        return False
    elif is_advanced_course_end_of_sale(advanced_course, tickets):
        log.warning(
            'User ({user_id}) try to choose tickets of advanced course ({advanced_course_id}), but end of sale.'.format(
                user_id=request.user.id, advanced_course_id=advanced_course.id
            )
        )
        messages.warning(request, _("Sorry, could not buy a ticket because all of tickets are end of sale."))
        return False
    else:
        return True


def require_enroll(is_f2f=False, use_course=True):
    """
    View decorator that whether the course is present and user is enrolled.
    """
    def decorator(func):
        @wraps(func)
        def wrapped(request, *args, **kwargs):  # pylint: disable=missing-docstring
            # course_id must exist in kwargs, but will be removed later in here.
            course_id = kwargs['course_id']
            if is_f2f:
                course = _get_f2f_course_with_access(request.user, 'enroll', course_id)
            else:
                course = _get_course_with_access(request.user, 'enroll', course_id)
            if registered_for_course(course, request.user):
                del kwargs['course_id']
                # course adds only if is necessary in view
                if use_course:
                    kwargs['course'] = course
                return func(request, *args, **kwargs)
            else:
                return redirect(reverse('about_course', args=[unicode(course.id)]))
        return wrapped
    return decorator


@require_GET
@login_required
@require_enroll()
def choose_advanced_course(request, course):

    _is_f2f_course = course.is_f2f_course and course.is_f2f_course_sell
    _course_types = [c for c in [
        AdvancedCourseTypes.F2F if _is_f2f_course else None,
        'free',  # free must be last
    ] if c is not None]

    context = {
        'course_id': course.id,
        'course_name': course.display_name_with_default,
        'is_f2f_course': _is_f2f_course,
        'course_types': _course_types,
    }

    return render_to_response('ga_advanced_course/choose.html', context)


def _advanced_courses_view(request, course, advanced_course_type):

    if advanced_course_type not in AdvancedCourseTypes.all():
        log.warning("Unknown advanced_course_type {}".format(advanced_course_type))
        raise Http404()

    _advanced_courses = [
        advanced_course
        for advanced_course in AdvancedCourse.get_advanced_courses_by_course_key(course.id)
        if advanced_course.course_type == advanced_course_type
    ]

    if not _advanced_courses:
        log.warning("No advanced course for {course_key}".format(course_key=course.id))
        raise Http404()

    context = {
        'course_name': course.display_name_with_default,
        'course_image': course_image_url(course),
        'advanced_courses_with_status': AdvancedCourseStatus(request, course, _advanced_courses),
        'advanced_course_type': advanced_course_type,
    }

    return render_to_response('ga_advanced_course/courses.html', context)


@require_GET
@login_required
@require_enroll(is_f2f=True)
def advanced_courses_face_to_face(request, course):
    return _advanced_courses_view(request, course, AdvancedCourseTypes.F2F)


@require_GET
@login_required
@require_enroll(is_f2f=True)
def choose_ticket(request, course, advanced_course_id):

    advanced_course = _get_advanced_course(advanced_course_id)

    tickets = AdvancedCourseTicket.find_by_advanced_course(advanced_course)

    if not _check_for_purchase(request, advanced_course, tickets):
        return _redirect_to_advanced_courses(advanced_course.course_id, advanced_course.course_type)

    context = {
        'course_id': unicode(course.id),
        'course_name': course.display_name_with_default,
        'advanced_course': advanced_course,
        'tickets': tickets,
    }
    return render_to_response('ga_advanced_course/choose_ticket.html', context)


def purchase_with_shoppingcart(user, ticket):
    """
    Create an order using shoppingcart.
    """
    cart = Order.get_cart_for_user(user)
    cart.clear()
    AdvancedCourseItem.add_to_order(cart, ticket)

    # Change the order's status so that we don't accidentally modify it later.
    # We need to do this to ensure that the parameters we send to the payment system
    # match what we store in the database.
    # (Ordinarily we would do this client-side when the user submits the form, but since
    # the JavaScript on this page does that immediately, we make the change here instead.
    # This avoids a second AJAX call and some additional complication of the JavaScript.)
    # If a user later re-enters the verification / payment flow, she will create a new order.
    cart.start_purchase()

    return cart


def checkout_with_shoppingcart(request, user, order):
    """
    Trigger checkout using shoppingcart.

    Note: This method same as verify_student.views.py:checkout_with_shoppingcart except model class of OrderItem.
    """

    # OrderItem must be 1
    item = order.orderitem_set.all().select_subclasses()[0]
    advanced_course = item.advanced_course_ticket.advanced_course

    callback_url = request.build_absolute_uri(
        reverse("shoppingcart.views.postpay_callback")
    )
    cancel_callback_url = request.build_absolute_uri(
        reverse("advanced_course:courses_{}".format(AdvancedCourseTypes.F2F), args=[advanced_course.course_id])
    )

    extra_data = [
        item.line_desc,
        str(item.course_id),
        user.id,
    ]

    payment_data = {
        'payment_processor_name': settings.CC_PROCESSOR_NAME,
        'payment_page_url': get_purchase_endpoint(),
        'payment_form_data': get_signed_purchase_params(
            order,
            callback_url=(callback_url, cancel_callback_url),
            extra_data=extra_data
        ),
    }
    return payment_data


@require_GET
@login_required
@require_enroll(is_f2f=True, use_course=False)
def purchase_ticket(request, ticket_id):

    ticket = _get_advanced_course_ticket(ticket_id)
    advanced_course = _get_advanced_course(ticket.advanced_course.id)

    # check status of target ticket
    if ticket.is_end_of_sale():
        log.warning(
            'User ({user_id}) try to choose ticket ({ticket_id}), but end of sale.'.format(
                user_id=request.user.id, ticket_id=ticket.id
            )
        )
        messages.warning(request, _("Sorry, could not buy a ticket because the selected ticket was end of sale."))
        return redirect(reverse(
            'advanced_course:choose_ticket', args=[advanced_course.course_id, advanced_course.id]
        ))

    # check status of target advanced_course
    # sell-by date is already checked. so we don't need to check here.
    if not _check_for_purchase(request, advanced_course, [ticket]):
        return _redirect_to_advanced_courses(advanced_course.course_id, advanced_course.course_type)

    # Now, only use shoppingcart. it may switch ecommerce-service in the future.
    order = purchase_with_shoppingcart(request.user, ticket)

    return redirect(reverse('advanced_course:checkout_ticket', args=[order.id]))


@require_GET
@login_required
def checkout_ticket(request, order_id):
    """
    This page is cushion for authentication. Use re-authentication in the future.
    """
    order = _get_user_paying_cart(request.user, order_id)

    context = {
        'order_id': order.id,
    }

    return render_to_response('ga_advanced_course/checkout_ticket.html', context)


@require_POST
@login_required
def checkout(request):
    """
    The endpoint that add a single product to the user's cart and request immediate checkout.
    """
    order_id = request.POST.get('order_id')

    order = _get_user_paying_cart(request.user, order_id)

    # Now, only use shoppingcart. it may switch ecommerce-service in the future.
    payment_data = checkout_with_shoppingcart(request, request.user, order)

    return JsonResponse(payment_data)


@require_POST
@login_required
def close_upsell(request):
    """
    The endpoint to keep the closed state of upsell message
    """
    course_id = request.POST.get('course_id')
    try:
        course_key = CourseKey.from_string(course_id)
        disable_upsell(request, course_key)
        return JsonResponse()
    except InvalidKeyError:
        log.warning("Invalid course_id({})".format(course_id))
        return JsonResponseBadRequest()

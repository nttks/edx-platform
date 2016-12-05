"""
Views for shoppingcart
"""
import logging

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from edxmako.shortcuts import render_to_response
from formtools.preview import FormPreview

from shoppingcart.models import Order

from ga_shoppingcart.exceptions import InvalidOrder
from ga_shoppingcart.models import PersonalInfo, PersonalInfoSetting
from ga_shoppingcart.notifications import process_notification
from ga_shoppingcart.utils import check_order_can_purchase


NOTIFICATION_RESULT_SUCCESS = '0'

log = logging.getLogger(__name__)


@require_POST
@csrf_exempt
def notify(request):
    try:
        log.info('Begin the process of notification from GMO. params={}'.format(request.POST))
        process_notification(request.POST.copy())
        log.info('Success to process of notification from GMO.')
    except:
        # if Exception occur, record the log for monitoring but no longer need to be notified from GMO.
        # GMO is to retransmit up to a maximum 5 times, every hour if they can not receive a normal status.
        # But we always returns a normal status to them if we received a notification even once.
        # In this case, the notification data is an invalid or a DB and inconsistencies.
        # operation support is required.
        log.exception('Failed to process of notification from GMO.')
    return HttpResponse(NOTIFICATION_RESULT_SUCCESS)


def get_user_paying_cart(user, order_id):
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


def render_checkout(user, order_id, view_name):
    order = get_user_paying_cart(user, order_id)

    context = {
        'order_id': order.id,
        'page_url': reverse(view_name)
    }

    return render_to_response('ga_shoppingcart/checkout.html', context)


class InputPersonalInfoFormPreview(FormPreview):
    preview_template = 'ga_shoppingcart/input_personal_info_preview.html'
    form_template = 'ga_shoppingcart/input_personal_info.html'

    def __init__(self, form):
        super(InputPersonalInfoFormPreview, self).__init__(form)
        self.order_id = None
        self.personal_info_setting = None

    def parse_params(self, *args, **kwargs):
        self.order_id = kwargs.get('order_id')
        self.personal_info_setting = self._get_personal_info_setting()

    def get_initial(self, request):
        self._check_order_status(request)
        return request.POST.dict() or {}

    def _get_personal_info_setting(self):
        try:
            return PersonalInfoSetting.get_item_with_order_id(self.order_id)
        except PersonalInfoSetting.DoesNotExist:
            raise Http404()

    def _check_order_status(self, request):
        if self.personal_info_setting.advanced_course or self.personal_info_setting.course_mode:
            get_user_paying_cart(request.user, self.order_id)
        else:
            log.error(
                'Unexpected Exception: Not have object which advanced_course and course_mode in PersonalInfoSetting'
            )
            raise Http404()

    def _get_form(self, request):
        return self.form(
            request.POST or None,
            initial=self.get_initial(request),
            auto_id=self.get_auto_id(),
            personal_info_setting=self.personal_info_setting
        )

    @method_decorator(login_required)
    def preview_get(self, request):
        context = self.get_context(request, self._get_form(request))
        return render_to_response(self.form_template, context)

    @method_decorator(login_required)
    def preview_post(self, request):
        f = self._get_form(request)
        context = self.get_context(request, f)
        if f.is_valid() and not request.POST.get('cancel'):
            context['hash_field'] = self.unused_name('hash')
            context['hash_value'] = self.security_hash(request, f)
            return render_to_response(self.preview_template, context)
        else:
            return render_to_response(self.form_template, context)

    @method_decorator(login_required)
    def post_post(self, request):
        f = self._get_form(request)
        if f.is_valid():
            if not self._check_security_hash(
                    request.POST.get(self.unused_name('hash'), ''),
                    request, f):
                return self.failed_hash(request)  # Security hash failed.
            return self.done(request, f.cleaned_data)
        else:
            return render_to_response(self.form_template,
                                      self.get_context(request, f))

    @method_decorator(login_required)
    def done(self, request, cleaned_data):
        if cleaned_data.get('gaccatz_check'):
            del cleaned_data['gaccatz_check']
        personal_info_setting = PersonalInfoSetting.get_item_with_order_id(order_id=self.order_id)
        PersonalInfo.objects.update_or_create(
            cleaned_data,
            user=request.user,
            order_id=self.order_id,
            choice=personal_info_setting,
        )
        if personal_info_setting.advanced_course:
            return render_checkout(request.user, self.order_id, 'advanced_course:checkout')
        else:  # Paid course case
            return render_checkout(request.user, self.order_id, 'verify_student_checkout')

    @property
    def __name__(self):
        return self.__class__.__name__

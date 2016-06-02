""" Models for the shopping cart and assorted purchase types """

import json
import pytz

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import ugettext as _
from model_utils.managers import InheritanceManager

from courseware.courses import get_course_by_id
from shoppingcart.models import OrderItem
from xmodule_django.models import CourseKeyField

from openedx.core.lib.ga_datetime_utils import to_timezone
from ga_advanced_course.models import AdvancedCourse, AdvancedCourseTicket
from ga_shoppingcart.utils import get_order_keep_time


class AdvancedCourseItemManager(InheritanceManager):

    def purchased(self):
        return self.filter(
            status='purchased',
            order__status='purchased'
        )


class AdvancedCourseItem(OrderItem):
    """
    This is an inventory item for purchasing advanced course
    """

    objects = AdvancedCourseItemManager()

    # Need for compatibility with shoppingcart
    course_id = CourseKeyField(max_length=128, db_index=True)

    advanced_course_ticket = models.ForeignKey(AdvancedCourseTicket)

    tax = models.DecimalField(default=0.0, decimal_places=2, max_digits=30)

    @property
    def single_item_receipt_template(self):
        """
        The template that should be used when there's only one item in the order
        """
        return 'ga_advanced_course/receipt.html'

    @property
    def single_item_receipt_context(self):
        course = get_course_by_id(self.course_id)
        return {
            'platform_name': settings.PLATFORM_NAME,
            'course_name': course.display_name_with_default,
            'advanced_course': AdvancedCourse.get_advanced_course(self.advanced_course_ticket.advanced_course_id),
            'advanced_course_ticket': self.advanced_course_ticket,
            'order_purchase_datetime': to_timezone(self.order.purchase_time),
        }

    @property
    def item_page(self):
        return reverse(
            'advanced_course:choose_ticket',
            args=[self.course_id, self.advanced_course_ticket.advanced_course.id]
        )

    @classmethod
    @transaction.commit_on_success
    def add_to_order(cls, order, advanced_course_ticket, currency=None):
        """
        Add a AdvancedCourseItem to an order

        Returns the AdvancedCourseItem object after saving

        `order` - an order that this item should be added to, generally the cart order
        `advanced_course_ticket` - an advanced_course_ticket that we would like to purchase as a AdvancedCourseItem
        """
        if currency is None:
            currency = settings.PAYMENT_CURRENCY

        super(AdvancedCourseItem, cls).add_to_order(order, currency=currency)

        item, _created = cls.objects.get_or_create(
            order=order,
            user=order.user,
            course_id=advanced_course_ticket.advanced_course.course_id,
            advanced_course_ticket=advanced_course_ticket,
        )
        item.status = order.status
        item.qty = 1
        item.unit_cost = advanced_course_ticket.price
        item.list_price = advanced_course_ticket.price
        item.tax = advanced_course_ticket.tax
        item.line_desc = u"{advanced_course_name} {advanced_course_ticket_name}".format(
            advanced_course_name=advanced_course_ticket.advanced_course.display_name,
            advanced_course_ticket_name=advanced_course_ticket.display_name,
        )
        item.currency = currency
        order.currency = currency
        order.save()
        item.save()
        return item

    @classmethod
    def find_purchased_by_course_id(cls, course_id):
        return cls.objects.purchased().filter(
            advanced_course_ticket__advanced_course__course_id=course_id,
        ).order_by(
            'advanced_course_ticket__advanced_course__id', 'advanced_course_ticket__id'
        )

    @classmethod
    def find_purchased_by_advanced_course_id(cls, advanced_course_id):
        return cls.objects.purchased().filter(advanced_course_ticket__advanced_course_id=advanced_course_id)

    @classmethod
    def find_purchased_by_user_and_advanced_course(cls, user, advanced_course):
        return cls.objects.purchased().filter(
            user_id=user.id,
            advanced_course_ticket__advanced_course_id=advanced_course.id
        )

    @classmethod
    def find_purchased_with_keep_by_advanced_course(cls, advanced_course):
        return cls.objects.filter(
            Q(advanced_course_ticket__advanced_course_id=advanced_course.id),
            Q(
                status='purchased', order__status='purchased'
            ) | Q(
                status='paying', order__status='paying', modified__gte=get_order_keep_time()
            )
        )

    def purchased_callback(self):
        """AdvancedCourse do not need to be fulfilled, so this method does nothing."""
        pass

    @property
    def payment_method(self):
        """
        Returns payment method
        """
        from shoppingcart.processors.GMO import ResultParams
        _data = self.order.processor_reply_dump if self.order.processor_reply_dump else '{}'
        params = ResultParams(json.loads(_data))
        if params.is_card():
            return _("Credit Card")
        elif params.is_docomo():
            return _("Docomo Mobile Payment")
        else:
            return _("Unknown")

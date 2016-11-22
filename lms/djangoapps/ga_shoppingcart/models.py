""" Models for the shopping cart and assorted purchase types """

import json

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import ugettext as _
from model_utils.managers import InheritanceManager

from course_modes.models import CourseMode
from courseware.courses import get_course_by_id
from shoppingcart.models import CertificateItem, OrderItem, Order
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

    class Meta:
        app_label = 'ga_shoppingcart'

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
    @transaction.atomic
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


class CertificateItemAdditionalInfo(models.Model):

    certificate_item = models.OneToOneField(CertificateItem, related_name='additional_info')
    tax = models.DecimalField(default=0.0, decimal_places=2, max_digits=30)

    class Meta:
        app_label = 'ga_shoppingcart'


class PersonalInfoSetting(models.Model):
    """
    Control personal information input fields.
    Only one of advanced_course and course_mode can be save.
    It is controlled by PersonalInfoModelForm.
    """
    advanced_course = models.OneToOneField(AdvancedCourse, null=True, blank=True, verbose_name=_('Event ID'))
    course_mode = models.OneToOneField(CourseMode, null=True, blank=True, verbose_name=_('Professional Course ID'))
    full_name = models.BooleanField(default=True, verbose_name=_('Full Name'))
    kana = models.BooleanField(default=True, verbose_name=_('Kana'))
    postal_code = models.BooleanField(default=True, verbose_name=_('Postal/Zip Code'))
    address_line_1 = models.BooleanField(default=True, verbose_name=_('Address Line 1'))
    address_line_2 = models.BooleanField(default=True, verbose_name=_('Address Line 2'))
    phone_number = models.BooleanField(default=True, verbose_name=_('Phone Number'))
    gaccatz_check = models.BooleanField(default=True, verbose_name=_('Gaccatz Check'))
    free_entry_field_1_title = models.TextField(blank=True, verbose_name=_('Free Entry Field 1 Title'))
    free_entry_field_2_title = models.TextField(blank=True, verbose_name=_('Free Entry Field 2 Title'))
    free_entry_field_3_title = models.TextField(blank=True, verbose_name=_('Free Entry Field 3 Title'))
    free_entry_field_4_title = models.TextField(blank=True, verbose_name=_('Free Entry Field 4 Title'))
    free_entry_field_5_title = models.TextField(blank=True, verbose_name=_('Free Entry Field 5 Title'))

    class Meta:
        app_label = 'ga_shoppingcart'

    def _is_selected_event_or_course(self):
        if self.advanced_course and self.course_mode:
            return False
        elif self.advanced_course is None and self.course_mode is None:
            return False
        else:
            return True

    def clean(self):
        if not self._is_selected_event_or_course():
            raise ValidationError(_("You must select item 'Event id' or 'Professional course id'."))
        if not self.address_line_1 == self.address_line_2:
            raise ValidationError(_("If you choose an Address Line 1 or 2, you must choose both."))
        if not self.full_name \
                and not self.kana \
                and not self.postal_code \
                and not self.address_line_1 \
                and not self.phone_number \
                and not self.gaccatz_check \
                and not self.free_entry_field_1_title \
                and not self.free_entry_field_2_title \
                and not self.free_entry_field_3_title \
                and not self.free_entry_field_4_title \
                and not self.free_entry_field_5_title:
            raise ValidationError(_(
                "You must select one item except 'Event Id' and 'Professional course ID' and 'Address Line 2'")
            )

    @classmethod
    def has_personal_info_setting(cls, advanced_course=None, course_mode=None):
        if advanced_course:
            return cls.objects.filter(advanced_course=advanced_course).exists()
        else:
            return cls.objects.filter(course_mode=course_mode).exists()

    @classmethod
    def get_item_with_order_id(cls, order_id):
        item = OrderItem.objects.get_subclass(order_id=order_id)
        if isinstance(item, AdvancedCourseItem):
            return cls.objects.get(
                advanced_course_id=item.advanced_course_ticket.advanced_course_id
            )
        elif isinstance(item, CertificateItem):
            return cls.objects.get(
                course_mode=CourseMode.objects.get(
                    course_id=item.course_id,
                    mode_slug=item.mode,
                )
            )
        else:
            raise PersonalInfoSetting.DoesNotExist(
                "'advanced_course' or 'course_mode' is required for PersonalInfoSetting."
            )


class PersonalInfo(models.Model):
    user = models.ForeignKey(User)
    order = models.ForeignKey(Order)
    choice = models.ForeignKey(PersonalInfoSetting)
    full_name = models.CharField(max_length=255, null=True, blank=False, verbose_name=_("Full Name"))
    kana = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Kana"))
    postal_code = models.CharField(max_length=7, null=True, blank=False, verbose_name=_("Postal/Zip Code"))
    address_line_1 = models.CharField(max_length=255, null=True, blank=False, verbose_name=_("Address Line 1"))
    address_line_2 = models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Address Line 2"))
    phone_number = models.CharField(max_length=32, null=True, blank=False, verbose_name=_("Phone Number"))
    gaccatz_check = models.CharField(max_length=1024, null=True, blank=False, verbose_name=_("Please write your personal computer environments.<br> ex.) MacBook Air. 1.6GHz Intel core i5. 8GB RAM. NTT FLET'S HIKARI"))
    free_entry_field_1 = models.CharField(max_length=1024, null=True, blank=False, verbose_name=_("Free Entry Field 1"))
    free_entry_field_2 = models.CharField(max_length=1024, null=True, blank=False, verbose_name=_("Free Entry Field 2"))
    free_entry_field_3 = models.CharField(max_length=1024, null=True, blank=False, verbose_name=_("Free Entry Field 3"))
    free_entry_field_4 = models.CharField(max_length=1024, null=True, blank=False, verbose_name=_("Free Entry Field 4"))
    free_entry_field_5 = models.CharField(max_length=1024, null=True, blank=False, verbose_name=_("Free Entry Field 5"))

    class Meta:
        app_label = 'ga_shoppingcart'
        unique_together = (('user', 'order'),)

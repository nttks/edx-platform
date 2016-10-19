
from django.db.models.signals import post_save
from django.dispatch import receiver

from shoppingcart.models import CertificateItem

from .models import CertificateItemAdditionalInfo
from .utils import get_tax


@receiver(post_save, sender=CertificateItem)
def save_additional_info(sender, instance, **kwargs):
    additional_info, _ = CertificateItemAdditionalInfo.objects.get_or_create(certificate_item=instance)
    additional_info.tax = get_tax(instance.unit_cost)
    additional_info.save()

"""
Models for dAccount
"""
import base64
from django.db import models
from django.contrib.auth.models import User


class DAccountNumber(models.Model):
    """
    Account Number models.
    """
    user = models.ForeignKey(User)
    number = models.TextField()
    updated = models.DateTimeField(auto_now=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'ga_daccount'

    def __unicode__(self):
        return self.user

    @classmethod
    def save_number(cls, user, number):
        enc_number = base64.b64encode(number)
        cls.objects.update_or_create(
            user=user,
            defaults={'number': enc_number},
        )
        return 0

    @classmethod
    def delete_number(cls, user):
        cls.objects.filter(
            user=user
        ).delete()
        return 0

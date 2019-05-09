"""
Models for dAccount
"""
import base64
from django.db import models
from django.contrib.auth.models import User


class AccountNumber(models.Model):
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
        return cls.objects.get_or_create(
            user=user,
            number=enc_number
        )

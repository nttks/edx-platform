"""
Models for dAccount
"""
import base64
from django.db import models


class AccountNumber(models.Model):
    """
    Account Number models.
    """
    uid = models.CharField(max_length=255, db_index=True, unique=True)
    number = models.TextField()
    updated = models.DateTimeField(auto_now=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'ga_daccount'

    def __unicode__(self):
        return self.uid

    @classmethod
    def save_number(cls, uid, number):
        enc_number = base64.b64encode(number)
        return cls.objects.get_or_create(
            uid=uid,
            number=enc_number
        )

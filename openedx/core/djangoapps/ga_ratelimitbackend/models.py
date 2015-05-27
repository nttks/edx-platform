"""
Models for rate limit backends.
"""
from django.db import models


class TrustedClient(models.Model):
    """
    Model for trusted client information.
    """
    ip_address = models.GenericIPAddressField(db_index=True, unique=True)
    name = models.CharField(max_length=100, blank=True)

    def __unicode__(self):
        if self.name:
            return u"{ip_address} {name}".format(ip_address=self.ip_address, name=self.name)
        return self.ip_address

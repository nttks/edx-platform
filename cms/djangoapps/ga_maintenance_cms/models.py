"""
Models for maintenance cms.
"""

from django.db import models


class MaintenanceMessage(models.Model):
    """
    Model for message for users during maintenance.
    """
    message = models.TextField(null=True, blank=True)
    display_order = models.IntegerField(default=1)
    display_flg = models.BooleanField(default=True)

    class Meta:
        ordering = ['-display_order']

    def __unicode__(self):
        return unicode(self.message)

    @classmethod
    def messages_for_all(cls):
        """
        return message data having some conditions.
        """
        messages = MaintenanceMessage.objects.filter(display_flg=True).order_by('-display_order').values('message')

        return messages

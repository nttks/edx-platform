from django.db import models
from django.contrib.auth.models import User

from biz.djangoapps.ga_organization.models import Organization


class ReservationMail(models.Model):
    """
    ReservationMail models.
    """
    user = models.ForeignKey(User)
    org = models.ForeignKey(Organization)
    mail_subject = models.CharField(max_length=128)
    mail_body = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    sent_flag = models.BooleanField(default=False)
    sent_date = models.DateTimeField(null=True)

    class Meta:
        app_label = 'gx_reservation_mail'

    def __unicode__(self):
        return self.user.username

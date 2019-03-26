"""
Django admin page for gx_reservation models
"""
from django.contrib import admin
from biz.djangoapps.gx_reservation_mail.models import ReservationMail


class ReservationMailAdmin(admin.ModelAdmin):
    list_display = ['user', 'org', 'mail_subject', 'mail_body', 'created', 'sent_flag', 'sent_date']
    readonly_fields = ['created', 'sent_date']
    raw_id_fields = ['user']


admin.site.register(ReservationMail, ReservationMailAdmin)

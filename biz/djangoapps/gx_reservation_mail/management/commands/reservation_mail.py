"""
Management command to reservation mail from cron.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import send_mail as django_send_mail
from django.db import transaction
from biz.djangoapps.ga_organization.models import OrganizationOption
from biz.djangoapps.gx_reservation_mail.models import ReservationMail
from pytz import timezone
import datetime

import logging
log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Usage: python manage.py lms --settings=aws auto_member_register [--debug]
    """
    target_id = None

    def add_arguments(self, parser):
        parser.add_argument('-id')

    def handle(self, *args, **options):
        target_id = options['id']

        def _get_send_mail():
            target_mails = ReservationMail.objects.filter(sent_flag=False).exclude(mail_subject="")
            if target_id:
                target_mails = target_mails.filter(id=target_id)

            for i, target_mail in enumerate(target_mails):
                org_opt = OrganizationOption.objects.filter(org=target_mail.org).first()
                created_jst = target_mail.created.astimezone(timezone('Asia/Tokyo'))
                target_mails[i].created = datetime.datetime(created_jst.year,
                                                            created_jst.month,
                                                            created_jst.day,
                                                            created_jst.hour,
                                                            created_jst.minute)
                if org_opt and org_opt.reservation_mail_date:
                    target_mails[i].batch_datetime = datetime.datetime(datetime.datetime.now().year,
                                                                       datetime.datetime.now().month,
                                                                       datetime.datetime.now().day,
                                                                       org_opt.reservation_mail_date.hour,
                                                                       org_opt.reservation_mail_date.minute)
                else:
                    target_mails[i].batch_datetime = datetime.datetime(datetime.datetime.now().year,
                                                                       datetime.datetime.now().month,
                                                                       datetime.datetime.now().day,
                                                                       7,
                                                                       0)
            return target_mails

        def _put_send_mail(send_mails):
            count = 0
            for i, email in enumerate(send_mails):
                if email.batch_datetime <= datetime.datetime.now():
                    if email.created < email.batch_datetime:
                        try:
                            with transaction.atomic():
                                reservation_mail = ReservationMail.objects.get(id=email.id)

                                django_send_mail(
                                    reservation_mail.mail_subject,
                                    reservation_mail.mail_body,
                                    settings.DEFAULT_FROM_EMAIL,
                                    [reservation_mail.user.email]
                                )
                                reservation_mail.sent_flag = True
                                reservation_mail.sent_date = datetime.datetime.now()
                                reservation_mail.mail_body = "(masked)"
                                reservation_mail.save()

                                log.info("email[" + str(email.id) + "] send complete batch_time:" + str(
                                    email.batch_datetime) + " created:" + str(email.created))
                                count += 1
                        except Exception as e:
                            log.info("email[" + str(email.id) + "] send error:" + str(e))
                    else:
                        log.info("email[" + str(email.id) + "] not send (new) batch_time:" + str(
                            email.batch_datetime) + " created:" + str(email.created))
                else:
                    log.info("email[" + str(email.id) + "] not send (before) batch_time:" + str(
                        email.batch_datetime) + " created:" + str(email.created))
            return count

        log.info(u"Command reservation_mail started.")
        reserve_mails = _get_send_mail()
        send_count = _put_send_mail(reserve_mails)

        total = len(reserve_mails)

        log.info(u"Command reservation_mail completed. total:{} send:{}".format(total, send_count))
        return "total:{} send:{}".format(total, send_count)

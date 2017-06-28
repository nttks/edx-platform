import logging
import json
from celery import task

from django.conf import settings
from django.core.mail import send_mail

from .pdf import create_pdf
from .models import DiagnosisInfo, GeneratePDFState
from lms import CELERY_APP

log = logging.getLogger(__name__)


@CELERY_APP.task
def perform_create_pdf(diagnosis_info_id):
    error_message = pdf_state = None
    try:
        diagnosis_info = DiagnosisInfo.objects.prefetch_related('user').get(id=diagnosis_info_id)
        log.info('Start perform_create_pdf task: username={}'.format(diagnosis_info.user.username))
        pdf_state = GeneratePDFState.objects.get(diagnosis_info=diagnosis_info)
        key = GeneratePDFState.make_hashkey(str(diagnosis_info.course_id) + diagnosis_info.user.username)
        response = create_pdf(diagnosis_info=diagnosis_info, key=key)
        download_url = json.loads(response).get('download_url')
        if download_url:
            pdf_state.download_url = download_url
            pdf_state.status = GeneratePDFState.downloadable
            pdf_state.key = key
        else:
            error_message = 'create_pdf was failed.\nDiagnosisInfo.id={}\nError reason: {}'.format(
                diagnosis_info_id,
                '{}'.format(response_dict),
            )
    except Exception as e:
        error_message = u'Caught some exception: {}\nDiagnosisInfo.id={}'.format(e, diagnosis_info_id)
        log.exception(error_message)

    try:
        if error_message:
            # zabbix hook
            log.error('ga_diagnosis: Notify Celery task operation was failed(receiver). DiagnosisInfo.id={}'.format(
                diagnosis_info_id
            ))
            send_mail(
                subject='ga_diagnosis: perform_create_pdf() was failed.',
                message=error_message,
                from_email=settings.GA_DIAGNOSIS_SERVICE_SUPPORT_SENDER,
                recipient_list=settings.GA_DIAGNOSIS_SERVICE_SUPPORT_EMAIL,
            )
        if pdf_state:
            if error_message:
                pdf_state.error_reason = error_message
                pdf_state.status = GeneratePDFState.error
            pdf_state.save()
    except Exception as e:
        log.exception(u'Caught some exception: {}'.format(e))
    log.info('End perform_create_pdf task')

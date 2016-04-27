# -*- coding: utf-8 -*-
import logging

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.core.management import call_command

from opaque_keys.edx.keys import CourseKey
from util.json_request import JsonResponse
from pdfgen.certificate import CertPDFException
from certificates.models import GeneratedCertificate, CertificateStatuses
from ga_operation.forms.move_videos_form import MoveVideosForm
from ga_operation.forms.create_certs_form import CreateCertsForm
from ga_operation.forms.create_certs_meeting_form import CreateCertsMeetingForm
from ga_operation.forms.publish_certs_form import PublishCertsForm
from ga_operation.tasks import CreateCerts, create_certs_task
from ga_operation.utils import handle_uploaded_file_to_s3, get_s3_bucket, get_s3_connection

log = logging.getLogger(__name__)
RESPONSE_FIELD_ID = 'right_content_response'


def staff_only(view_func):
    """Prevent invasion from other roll's user."""
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_staff:
            return JsonResponse({}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
def create_certs(request):
    """Ajax call to create certificates for normal."""
    f = CreateCertsForm(data=request.POST, files=request.FILES)
    if not f.is_valid():
        f.errors[RESPONSE_FIELD_ID] = u'入力したフォームの内容が不正です。'
        log.info(f.errors)
        return JsonResponse(f.errors, status=400)
    email = f.cleaned_data['email']
    course_id = f.cleaned_data['course_id']
    file_name_list = handle_uploaded_file_to_s3(form=f,
                                                file_name_keys=['cert_pdf_tmpl'],
                                                bucket_name=settings.GA_OPERATION_CERTIFICATE_BUCKET_NAME)
    try:
        create_certs_task.delay(course_id=course_id,
                                email=email,
                                file_name_list=file_name_list)
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponse({
            RESPONSE_FIELD_ID: "{}".format(e)
        }, status=400)
    else:
        return JsonResponse({
            RESPONSE_FIELD_ID: u'修了証の作成（対面なし）を開始しました。\n処理が完了したら{}のアドレスに処理の完了通知が来ます。'.format(email)
        })
    finally:
        log.info('path:{}, user.id:{} End.'.format(request.path, request.user.id))


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
def create_certs_meeting(request):
    """Ajax call to create certificates for normal and meeting."""
    f = CreateCertsMeetingForm(data=request.POST, files=request.FILES)
    if not f.is_valid():
        f.errors[RESPONSE_FIELD_ID] = u'入力したフォームの内容が不正です。'
        log.info(f.errors)
        return JsonResponse(f.errors, status=400)
    email = f.cleaned_data['email']
    course_id = f.cleaned_data['course_id']
    file_name_list = handle_uploaded_file_to_s3(form=f,
                                                file_name_keys=['cert_pdf_tmpl', 'cert_pdf_meeting_tmpl', 'cert_lists'],
                                                bucket_name=settings.GA_OPERATION_CERTIFICATE_BUCKET_NAME)
    try:
        create_certs_task.delay(course_id=course_id,
                                email=email,
                                file_name_list=file_name_list,
                                is_meeting=True)
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponse({
            RESPONSE_FIELD_ID: "{}".format(e)
        }, status=400)
    else:
        return JsonResponse({
            RESPONSE_FIELD_ID: u'修了証の作成（対面あり）を開始しました。\n処理が完了したら{}のアドレスに処理の完了通知が来ます。'.format(email)
        })
    finally:
        log.info('path:{}, user.id:{} End.'.format(request.path, request.user.id))


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
def publish_certs(request):
    """Ajax call to publish certificates."""
    f = PublishCertsForm(request.POST)
    if not f.is_valid():
        f.errors[RESPONSE_FIELD_ID] = u'入力したフォームの内容が不正です。'
        log.info(f.errors)
        return JsonResponse(f.errors, status=400)
    course_id = f.cleaned_data['course_id']
    response_msg = "--CertificateStatuses--\n\n"
    try:
        call_command(CreateCerts.get_command_name(),
                     'publish', course_id,
                     username=False, debug=False, noop=False, prefix='', exclude=None)
        course_key = CourseKey.from_string(course_id)
        attr_list = ['deleted', 'deleting', 'downloadable',
                     'error', 'generating', 'notpassing',
                     'regenerating', 'restricted', 'unavailable']
        # Describe message on a web browser to be counting each CertificateStatuses class's attribute.
        for status in attr_list:
            response_msg += "{}: {}\n".format(status, GeneratedCertificate.objects.filter(
                course_id=course_key,
                status=status
            ).count())
    except CertPDFException as e:
        log.exception("Failure to publish certificates from create_certs command")
        return JsonResponse({
            RESPONSE_FIELD_ID: "{}".format(e)
        }, status=400)
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponse({
            RESPONSE_FIELD_ID: "{}".format(e)
        }, status=500)
    else:
        return JsonResponse(
            {RESPONSE_FIELD_ID: u'対象講座ID: {} の修了証公開処理が完了しました。\n\n{}'.format(course_id, response_msg)})
    finally:
        log.info('path:{}, user.id:{} End.'.format(request.path, request.user.id))


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
def move_videos(request):
    """Ajax call to move videos file between AWS S3 buckets."""
    conn = None
    f = MoveVideosForm(request.POST)
    if not f.is_valid():
        f.errors[RESPONSE_FIELD_ID] = u'入力したフォームの内容が不正です。'
        log.info(f.errors)
        return JsonResponse(f.errors, status=400)
    course_key = CourseKey.from_string(f.cleaned_data.get('course_id'))

    try:
        conn = get_s3_connection()
        course = course_key.course
        direction = request.POST['select_bucket']
        if direction == 'org_to_log':
            origin_bucket = get_s3_bucket(conn, settings.GA_OPERATION_VIDEO_BUCKET_NAME_ORG)
            log_bucket = get_s3_bucket(conn, settings.GA_OPERATION_VIDEO_BUCKET_NAME_LOG)
        elif direction == 'log_to_org':
            origin_bucket = get_s3_bucket(conn, settings.GA_OPERATION_VIDEO_BUCKET_NAME_LOG)
            log_bucket = get_s3_bucket(conn, settings.GA_OPERATION_VIDEO_BUCKET_NAME_ORG)
        else:
            raise ValueError
        find_target = False
        for k in origin_bucket.list(prefix=course):
            find_target = True
            log_bucket.copy_key(new_key_name=k.key,
                                src_bucket_name=origin_bucket.name,
                                src_key_name=k.key)
            origin_bucket.delete_key(key_name=k.key)
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponse({
            RESPONSE_FIELD_ID: "{}".format(e)
        }, status=500)
    else:
        return JsonResponse({
            RESPONSE_FIELD_ID: u'移動に成功しました。' if find_target else u'移動させる動画がありませんでした。'
        })
    finally:
        log.info('path:{}, user.id:{} End.'.format(request.path, request.user.id))
        if conn:
            conn.close()

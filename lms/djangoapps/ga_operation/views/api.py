# -*- coding: utf-8 -*-
import logging
import csv

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_GET
from django.core.management import call_command
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden, HttpResponseBadRequest

from opaque_keys.edx.keys import CourseKey
from opaque_keys import InvalidKeyError
from util.json_request import JsonResponse
from pdfgen.certificate import CertPDFException
from certificates.models import GeneratedCertificate
from ga_operation.forms.move_videos_form import MoveVideosForm
from ga_operation.forms.create_certs_form import CreateCertsForm
from ga_operation.forms.create_certs_meeting_form import CreateCertsMeetingForm
from ga_operation.forms.publish_certs_form import PublishCertsForm
from ga_operation.forms.mutual_grading_report import MutualGradingReportForm
from ga_operation.forms.last_login_info_form import LastLoginInfoForm
from ga_operation.forms.discussion_data_form import DiscussionDataForm
from ga_operation.forms.past_graduates_info_form import PastGraduatesInfoForm
from ga_operation.forms.aggregate_g1528_form import AggregateG1528Form
from ga_operation.tasks import (CreateCerts, create_certs_task, dump_oa_scores_task, ga_get_grades_g1528_task)
from ga_operation.utils import (handle_uploaded_received_file_to_s3, get_s3_bucket,
                                get_s3_connection, CSVResponse, JSONFileResponse)
from ga_operation.mongo_utils import CommentStore

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
    try:
        file_name_list = handle_uploaded_received_file_to_s3(form=f,
                                                             file_name_keys=['cert_pdf_tmpl'],
                                                             bucket_name=settings.GA_OPERATION_CERTIFICATE_BUCKET_NAME)
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
    try:
        tmpl_list = ['cert_pdf_tmpl', 'cert_pdf_meeting_tmpl', 'cert_lists']
        file_name_list = handle_uploaded_received_file_to_s3(form=f,
                                                             file_name_keys=tmpl_list,
                                                             bucket_name=settings.GA_OPERATION_CERTIFICATE_BUCKET_NAME)
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


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
def mutual_grading_report(request):
    """Ajax call to mutual grading report."""
    f = MutualGradingReportForm(request.POST)
    if not f.is_valid():
        f.errors[RESPONSE_FIELD_ID] = u'入力したフォームの内容が不正です。'
        log.info(f.errors)
        return JsonResponse(f.errors, status=400)
    course_id = f.cleaned_data['course_id']
    email = f.cleaned_data['email']
    try:
        dump_oa_scores_task.delay(course_id=course_id, email=email)
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponse({
            RESPONSE_FIELD_ID: "{}".format(e)
        }, status=500)
    else:
        return JsonResponse({
            RESPONSE_FIELD_ID: u'相互採点レポートの作成を開始しました。\n処理が完了したら{}のアドレスに処理の完了通知が届きます。'.format(email)
        })
    finally:
        log.info('path:{}, user.id:{} End.'.format(request.path, request.user.id))


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
def discussion_data(request):
    """Ajax call to discussion data."""
    f = DiscussionDataForm(request.POST)
    if not f.is_valid():
        f.errors[RESPONSE_FIELD_ID] = u'入力したフォームの内容が不正です。'
        log.info(f.errors)
        return JsonResponse(f.errors, status=400)
    course_id = f.cleaned_data['course_id']
    try:
        store = CommentStore()
        # Thread count
        thread_count = store.get_count(dict(course_id=course_id, _type="CommentThread"))
        # Comment count
        comment_count = store.get_count(dict(course_id=course_id, _type="Comment"))
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponse({RESPONSE_FIELD_ID: u'{}'.format(e)}, status=500)
    finally:
        log.info('path:{}, user.id:{} End.'.format(request.path, request.user.id))
    res = "スレッド数: {}件\nコメント数: {}件".format(thread_count, comment_count)
    return JsonResponse({RESPONSE_FIELD_ID: res})


@staff_only
@login_required
@require_GET
@ensure_csrf_cookie
def discussion_data_download(request):
    """Ajax call to discussion data."""
    f = DiscussionDataForm(request.GET)
    if not f.is_valid():
        f.errors[RESPONSE_FIELD_ID] = u'入力したフォームの内容が不正です。'
        log.info(f.errors)
        return JsonResponse(f.errors, status=400)
    course_id = f.cleaned_data['course_id']
    try:
        all_documents = CommentStore().get_documents(dict(course_id=course_id))
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return HttpResponseBadRequest(u'{}'.format(e))
    finally:
        log.info('path:{}, user.id:{} End.'.format(request.path, request.user.id))
    return JSONFileResponse(object=all_documents, filename='discussion_data.json')


@staff_only
@login_required
@require_GET
@ensure_csrf_cookie
def past_graduates_info(request):
    """Ajax call to past graduates information."""
    f = PastGraduatesInfoForm(request.GET)
    if not f.is_valid():
        log.info(f.errors)
        return HttpResponseForbidden(u'入力したフォームの内容が不正です。')
    course_id = f.cleaned_data['course_id']
    # Collect the user who certificated and available for send the email.
    sql = '''
        select a.id from (auth_user a inner join student_courseenrollment b on a.id=b.user_id)
            inner join certificates_generatedcertificate c on a.id=c.user_id
        where
             b.course_id like "{}%%"
             and b.is_active=1
             and c.status="downloadable"
             and b.course_id=c.course_id
             and not exists (select * from bulk_email_optout d where a.id=d.user_id and (b.course_id=d.course_id or b.course_id like "{}%%"))
             and not exists (select * from student_userstanding e where a.id=e.user_id and e.account_status="disabled");
    '''.format(course_id, course_id)
    response = CSVResponse(filename='past_graduates_info.csv')
    writer = csv.writer(response)
    try:
        for user in User.objects.raw(sql):
            writer.writerow([user.username, user.email])
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return HttpResponseBadRequest(u'{}'.format(e))
    finally:
        log.info('path:{}, user.id:{} End.'.format(request.path, request.user.id))
    return response


@staff_only
@login_required
@require_GET
@ensure_csrf_cookie
def last_login_info(request):
    """Ajax call to last login information."""
    f = LastLoginInfoForm(request.GET)
    if not f.is_valid():
        log.info(f.errors)
        return HttpResponseForbidden(u'入力したフォームの内容が不正です。')
    course_id = f.cleaned_data['course_id']
    response = CSVResponse(filename='last_login_info.csv')
    writer = csv.writer(response)
    # Collect the user who enrolling the course and account is not disabled.
    sql = '''
        select a.id from auth_user a
            inner join student_courseenrollment b on a.id=b.user_id
        where
            b.course_id="{}"
            and b.is_active=1
            and not exists (select c.user_id from student_userstanding c where a.id=c.user_id and c.account_status="disabled");
    '''.format(course_id)

    try:
        for user in User.objects.raw(sql):
            writer.writerow([user.username, user.email, user.last_login, 1 if user.is_active else 0])
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return HttpResponseBadRequest(u'{}'.format(e))
    finally:
        log.info('path:{}, user.id:{} End.'.format(request.path, request.user.id))
    return response


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
def aggregate_g1528(request):
    """Ajax call to aggregate g1528."""
    f = AggregateG1528Form(request.POST, files=request.FILES)
    if not f.is_valid():
        log.info(f.errors)
        f.errors[RESPONSE_FIELD_ID] = u'入力したフォームの内容が不正です。'
        return JsonResponse(f.errors, status=400)
    email = f.cleaned_data['email']
    course_list = []
    line_count = 0
    try:
        for line in f.cleaned_data['course_lists_file'].readlines():
            course_id = line.strip('\n')
            course_list.append(course_id)
            line_count += 1
            CourseKey.from_string(course_id)
        ga_get_grades_g1528_task.delay(course_list=course_list, email=email)
    except InvalidKeyError as e:
        err_msg = 'Course ID format error. Line:{}, {}'.format(line_count, e)
        log.exception(err_msg)
        return JsonResponse({
            RESPONSE_FIELD_ID: err_msg
        }, status=400)
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponse({
            RESPONSE_FIELD_ID: "{}".format(e)
        }, status=500)
    else:
        return JsonResponse({
            RESPONSE_FIELD_ID: u'処理を開始しました。\n処理が終了次第、{}のアドレスに完了通知が届きます。'.format(email)
        })
    finally:
        log.info('path:{}, user.id:{} End.'.format(request.path, request.user.id))


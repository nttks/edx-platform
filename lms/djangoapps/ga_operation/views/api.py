# -*- coding: utf-8 -*-
import logging

from boto.s3.connection import S3Connection
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from opaque_keys.edx.keys import CourseKey
from util.json_request import JsonResponse
from ..forms.move_videos_form import MoveVideosForm


log = logging.getLogger(__name__)
RESPONSE_FIELD_ID = 'right_content_response'


def staff_only(view_func):
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
    pass


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
def publish_certs(request):
    pass


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
def move_videos(request):
    conn = None
    f = MoveVideosForm(request.POST)
    if not f.is_valid():
        f.errors[RESPONSE_FIELD_ID] = u'入力したフォームの内容が不正です。'
        log.info(f.errors)
        return JsonResponse(f.errors, status=400)
    course_key = CourseKey.from_string(f.cleaned_data.get('course_id'))

    try:
        conn = S3Connection(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
        org_bucket_name = settings.GA_OPERATION_VIDEO_BUCKET_NAME_ORG
        log_bucket_name = settings.GA_OPERATION_VIDEO_BUCKET_NAME_LOG
        course = course_key.course
        direction = request.POST['select_bucket']
        if direction == 'org_to_log':
            origin_bucket = conn.get_bucket(org_bucket_name)
            log_bucket = conn.get_bucket(log_bucket_name)
        elif direction == 'log_to_org':
            origin_bucket = conn.get_bucket(log_bucket_name)
            log_bucket = conn.get_bucket(org_bucket_name)
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
        log.error(e)
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



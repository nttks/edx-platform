# -*- coding: utf-8 -*-
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from xmodule.modulestore.django import modulestore

from biz.djangoapps.ga_contract.models import Contract, ContractDetail
from cms.djangoapps.ga_operation.forms.delete_course_form import DeleteCourseForm
from cms.djangoapps.ga_operation.forms.delete_library_form import DeleteLibraryForm
from cms.djangoapps.ga_operation.tasks import delete_course_task, delete_library_task
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.ga_operation.utils import handle_operation, RESPONSE_FIELD_ID, staff_only
from student.models import CourseEnrollment
from util.json_request import JsonResponse


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
@handle_operation(DeleteCourseForm)
def delete_course(request, form_instance):
    """Ajax call to delete course."""
    course_id = form_instance.cleaned_data['course_id']
    course_key = CourseKey.from_string(course_id)
    email = form_instance.cleaned_data['email']
    err_msg_list = []
    contracts = Contract.objects.filter(
        id__in=[d.contract.id for d in ContractDetail.objects.filter(course_id=course_key)]
    )
    if contracts.exists():
        err_msg_list.append(u"・以下の法人契約がこの講座を登録しているため、削除できません。\n")
        err_msg_list.append(u"\n".join([u"- " + c.contract_name for c in contracts]) + u"\n\n")
    enrollments = CourseEnrollment.objects.prefetch_related("user").filter(course_id=course_key, is_active=True)
    if enrollments.exists():
        err_msg_list.append(u"・以下のユーザーがこの講座を受講登録しているため、削除できません。\n")
        err_msg_list.append(u",".join([e.user.username for e in enrollments]))
    if err_msg_list:
        return JsonResponse({RESPONSE_FIELD_ID: u"".join(err_msg_list)}, status=400)
    else:
        delete_course_task.delay(course_id=course_id, email=email)
        return JsonResponse({
            RESPONSE_FIELD_ID: u"講座削除処理を開始しました。\n処理が終了次第、{}のアドレスに完了通知が届きます。".format(email)
        })


@staff_only
@login_required
@require_POST
@ensure_csrf_cookie
@handle_operation(DeleteLibraryForm)
def delete_library(request, form_instance):
    """Ajax call to delete library."""
    library_id = form_instance.cleaned_data['library_id']
    email = form_instance.cleaned_data['email']
    target_course_key = None
    source_library_ids = []
    courses = modulestore().get_courses()
    for course in courses:
        target_libraries = getattr(course, 'target_library', [])
        if unicode(library_id) in target_libraries:
            target_course_key = course.scope_ids.def_id.course_key
            break

    if target_course_key:
        items = modulestore().get_items(target_course_key)
        for item in items:
            if item.scope_ids.block_type == 'library_content':
                source_library_id = getattr(item, 'source_library_id', '')
                if source_library_id:
                    source_library_ids.append(source_library_id)

    if source_library_ids:
        if library_id in source_library_ids:
            return JsonResponse({RESPONSE_FIELD_ID: u"・以下の講座で利用されているため、削除できません。\n{}".format(target_course_key)}, status=400)

    delete_library_task.delay(library_id=library_id, email=email)
    return JsonResponse({
        RESPONSE_FIELD_ID: u"ライブラリ削除処理を開始しました。\n処理が終了次第、{}のアドレスに完了通知が届きます。".format(email)
    })

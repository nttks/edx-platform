from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.conf import settings
from django.shortcuts import redirect

from courseware.access import has_access, GA_ACCESS_CHECK_TYPE_ANALYZER
from edxmako.shortcuts import render_to_response
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.ga_operation.utils import staff_only, authority_check
from opaque_keys.edx.keys import CourseKey
from student.models import CourseAccessRole


@login_required
@staff_only
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def ga_operation_dashboard(request):
    """ Display the operation dashboard for a staff. """
    is_ga_analyzer = request.user.is_superuser or has_access(request.user, GA_ACCESS_CHECK_TYPE_ANALYZER, 'global')
    if not request.user.is_staff:
        return HttpResponseForbidden()
    context = {
        "company_keys": settings.GA_OPERATION_SPECIFIC_COMPANY_KEYS,
        "callback_email": settings.GA_OPERATION_CALLBACK_EMAIL,
        "is_ga_analyzer": is_ga_analyzer,
    }
    return render_to_response('ga_operation/ga_operation_dashboard.html', context)


@login_required
@authority_check
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def ga_operation_user_dashboard(request):
    """ Display the operation dashboard for a staff. """
    if request.user.is_staff:
        is_ga_analyzer = request.user.is_superuser or has_access(request.user, GA_ACCESS_CHECK_TYPE_ANALYZER, 'global')
        context = {
            "company_keys": settings.GA_OPERATION_SPECIFIC_COMPANY_KEYS,
            "callback_email": settings.GA_OPERATION_CALLBACK_EMAIL,
            "is_ga_analyzer": is_ga_analyzer,
        }
        return redirect('/ga_operation', context)

    else:
        studio_user_list = CourseAccessRole.objects.filter(user=request.user,
                                                           role__in=['instructor', 'staff']).values('course_id')
        if studio_user_list:
            course_list = []
            for studio_user in studio_user_list:
                try:
                    course_overview = CourseOverview.objects.get(
                        id=CourseKey.from_string(studio_user['course_id']))
                except CourseOverview.DoesNotExist:
                    # Error CourseOverview is not value
                    continue

                course_list.append([studio_user['course_id'], course_overview.display_name])
            context = {
                "company_keys": settings.GA_OPERATION_SPECIFIC_COMPANY_KEYS,
                "callback_email": settings.GA_OPERATION_CALLBACK_EMAIL,
                "course_list": course_list,
            }
            return render_to_response('ga_operation/ga_operation_user_dashboard.html', context)
        else:
            return HttpResponseForbidden()

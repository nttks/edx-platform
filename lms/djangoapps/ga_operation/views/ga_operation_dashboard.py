from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.conf import settings

from courseware.access import has_access, GA_ACCESS_CHECK_TYPE_ANALYZER
from edxmako.shortcuts import render_to_response


@login_required
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

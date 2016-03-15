from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from edxmako.shortcuts import render_to_response


@login_required
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def ga_operation_dashboard(request):
    """ Display the operation dashboard for a staff. """
    if not request.user.is_staff:
        return HttpResponseForbidden()
    return render_to_response('ga_operation/ga_operation_dashboard.html')

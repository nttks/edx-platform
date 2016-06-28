"""
Views for course selection
"""
import logging

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.util import cache_utils
from biz.djangoapps.util.decorators import check_course_selection
from edxmako.shortcuts import render_to_string

log = logging.getLogger(__name__)


@require_GET
@login_required
@check_course_selection
def index(request):
    """
    Redirect the user to the specified page according to the user's manager permission

    :param request: HttpRequest
    :return: HttpResponse
    """
    current_manager = request.current_manager
    current_contract = request.current_contract
    current_course = request.current_course

    # Platformer or Aggregator
    if current_manager.is_platformer() or (current_manager.is_aggregator() and current_contract.is_available_for_aggregator()):
        return redirect(reverse('biz:contract:index'))

    # Director
    elif current_manager.is_director() and current_contract.is_available_for_director_or_manager():
        return redirect(reverse('biz:achievement:index')) if current_course else redirect(reverse('biz:contract_operation:students'))

    # Manager
    elif current_manager.is_manager() and current_contract.is_available_for_director_or_manager():
        return redirect(reverse('biz:achievement:index'))

    else:
        return HttpResponseForbidden(render_to_string('static_templates/403.html', {}))


@require_POST
@login_required
def change(request):
    """
    Change cache data of the course selection and redirect to biz:index

    :param request: HttpRequest
    :return: HttpResponse
    """
    user = request.user
    # Convert empty string into None
    org_id = request.POST.get('org_id') or None
    contract_id = request.POST.get('contract_id') or None
    course_id = request.POST.get('course_id') or None

    # Set cache
    cache_utils.set_course_selection(user, org_id, contract_id, course_id)

    return redirect(reverse('biz:index'))

"""
Views for course selection
"""
import logging

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.util import cache_utils
from biz.djangoapps.util.decorators import check_course_selection

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
    if current_manager.is_platformer() or (current_manager.is_aggregator() and current_contract and not current_course):
        return redirect(reverse('biz:contract:index'))

    # Director or Manager
    elif current_manager.is_director() or current_manager.is_manager():
        return redirect(reverse('biz:achievement:index'))


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

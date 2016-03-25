"""
Views for manager feature
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_invitation.models import ContractRegister
from biz.djangoapps.ga_manager.models import (
    Manager, ManagerPermission, PERMISSION_AGGREGATOR, PERMISSION_DIRECTOR, PERMISSION_MANAGER,
)
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.util.decorators import check_course_selection
from edxmako.shortcuts import render_to_response
from instructor.views.tools import get_student_from_identifier
from student.models import UserStanding
from util.json_request import JsonResponse

log = logging.getLogger(__name__)


@require_GET
@login_required
@check_course_selection
def index(request):
    """
    Show manager setting view

    :param request: HttpRequest
    :return: HttpResponse
    """
    manager = request.current_manager
    context = {
        'org_list': _create_org_choice_list(manager),
        'permission_list': _create_permission_choice_list(manager),
    }

    if not context['org_list']:
        messages.error(request, _("You need to create an organization first."))

    return render_to_response('ga_manager/index.html', context)


def _create_org_choice_list(manager):
    """
    Create organization choice list the manager can access

    :param manager: manager object
    :return: organization list
    """
    org_list = []
    current_org = manager.org
    if manager.is_platformer() or manager.is_aggregator():
        org_list = [(org.id, org.org_name) for org in Organization.find_by_creator_org_without_itself(current_org)]
    if manager.is_director():
        org_list.append((current_org.id, current_org.org_name))
    return org_list


def _create_permission_choice_list(manager):
    """
    Create manager permission choice list the manager can access

    :param manager: manager object
    :return: permission list
    """
    permission_list = []
    if manager.is_platformer():
        permission_list.append((PERMISSION_AGGREGATOR[0], force_unicode(PERMISSION_AGGREGATOR[1])))
    permission_list.append((PERMISSION_DIRECTOR[0], force_unicode(PERMISSION_DIRECTOR[1])))
    permission_list.append((PERMISSION_MANAGER[0], force_unicode(PERMISSION_MANAGER[1])))
    return permission_list


@require_POST
@ensure_csrf_cookie
@login_required
@check_course_selection
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def modify_ajax(request):
    """
    Modify manager permission for input user of selected organization

    :param request: HttpRequest
    :return: JsonResponse
    """
    try:
        selected_org = _get_valid_selected_org(request)
        selected_permission = _get_valid_selected_permission(request)
        unique_student_identifier = _get_valid_user(request)
    except ValidationError as e:
        log.error(e.messages[0])
        return HttpResponseBadRequest()

    try:
        user = get_student_from_identifier(unique_student_identifier)
    except User.DoesNotExist:
        return _ajax_fail_response("The user does not exist.")

    # check that user is active
    if not user.is_active:
        return _ajax_fail_response("The user is not active.")

    # check that user is not logged in user
    if request.user == user:
        return _ajax_fail_response("You can not change permissions of yourself.")

    action = request.POST.get('action')
    user_manager = Manager.get_manager(user, selected_org)
    if action == 'allow':
        # check that user is resigned
        user_standing = UserStanding.objects.filter(user=user)
        if user_standing and user_standing[0].account_status == UserStanding.ACCOUNT_DISABLED:
            return _ajax_fail_response("The user is resigned.")

        current_manager = request.current_manager
        if current_manager.is_director() and selected_org == current_manager.org:
            # check course registration status
            contract_register = ContractRegister.get_by_user_contract(user, request.current_contract)
            if not contract_register or not contract_register.is_registered:
                return _ajax_fail_response("The user have not registered course.")

        # add manager permission
        if not user_manager:
            # save new manager
            user_manager = Manager(org=selected_org, user=user)
            user_manager.save()
        elif selected_permission in user_manager.get_manager_permissions():
            return _ajax_fail_response("The user already has the same permission.")
        # save new permission
        user_manager.manager_permissions.add(selected_permission)
        user_manager.save()
    elif action == 'revoke':
        if not user_manager or selected_permission not in user_manager.get_manager_permissions():
            return _ajax_fail_response("The user does not have permission.")
        # remove permission
        if len(user_manager.get_manager_permissions()) > 1:
            user_manager.manager_permissions.remove(selected_permission)
            user_manager.save()
        else:
            user_manager.delete()
    else:
        log.error("You cannot access the page (action={0}) because it does not exist.".format(action))
        return HttpResponseBadRequest()

    response_payload = {
        'name': user.username,
        'email': user.email,
        'success': True,
    }
    return JsonResponse(response_payload)


def _ajax_fail_response(message):
    response_payload = {
        'message': _(message),
        'success': False,
    }
    return JsonResponse(response_payload)


@require_POST
@ensure_csrf_cookie
@login_required
@check_course_selection
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def list_ajax(request):
    """
    Return manager list of selected org and permission

    :param request: HttpRequest
    :return:
        JsonResponse if success
        HttpResponseBadRequest if parameter is invalid
    """
    try:
        selected_org = _get_valid_selected_org(request)
        selected_permission = _get_valid_selected_permission(request)
    except ValidationError as e:
        log.error(e.messages[0])
        return HttpResponseBadRequest()

    managers = Manager.get_manager_with_permission(selected_org, selected_permission)
    show_list = []
    for manager in managers:
        show_list.append({
            'name': manager.user.username,
            'email': manager.user.email,
        })

    response_payload = {
        'show_list': show_list,
        'success': True,
    }
    return JsonResponse(response_payload)


def _get_valid_selected_org(request):
    """
    return valid selected_org_id parameter

    Note: raises ValidationError if the selected_org_id parameter is empty or current manager cannot access
    :param request: HttpRequest
    :return: parameter permission_name
    """
    manager = request.current_manager

    # Check selected_org_id is valid
    selected_org_id = request.POST.get('selected_org_id')
    if not selected_org_id:
        raise ValidationError("You miss required parameter [selected_org_id] for the request.")

    selected_org = get_object_or_404(Organization, pk=selected_org_id)
    if manager.is_platformer() or manager.is_aggregator():
        # Platformer or Aggregator
        if selected_org.creator_org_id != manager.org.id and selected_org.id != manager.org.id:
            raise ValidationError(
                "You cannot change permission of the organization(id={}) which does not belong to your own organization(id={}).".format(
                    selected_org.creator_org_id, manager.org.id)
            )
    elif selected_org.id != manager.org.id:
        # Director or Manager
        raise ValidationError(
            "You cannot change permission of the organization(id={}) which is not your own organization(id={}).".format(
                selected_org.creator_org_id, manager.org.id)
        )
    return selected_org


def _get_valid_selected_permission(request):  # or _get_cleaned_selected_permission
    """
    return valid permission_name parameter

    Note: raises ValidationError if the permission_name parameter is empty or current manager cannot access
    :param request: HttpRequest
    :return: parameter permission_name
    """
    manager = request.current_manager

    # Check permission_name is valid
    permission_name = request.POST.get('permission_name')
    if not permission_name:
        raise ValidationError("You miss required parameter [permission_name] for the request.")
    selected_permission = get_object_or_404(ManagerPermission, permission_name=permission_name)
    if permission_name not in dict(_create_permission_choice_list(manager)):
        raise ValidationError(
            "You cannot change {} permission because your manager(id={}) permission is not allowed to do so.".format(
                permission_name, manager.org.id)
        )
    return selected_permission


def _get_valid_user(request):
    """
    return valid unique_student_identifier parameter

    Note: raises ValidationError if the unique_student_identifier parameter is empty
    :param request: HttpRequest
    :return: parameter unique_student_identifier
    """
    # Check user is valid
    unique_student_identifier = request.POST.get('unique_student_identifier')
    if not unique_student_identifier:
        raise ValidationError("You miss required parameter [unique_student_identifier] for the request.")

    return unique_student_identifier

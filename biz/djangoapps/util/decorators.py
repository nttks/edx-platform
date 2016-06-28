"""
Decorator utilities
"""
from functools import wraps
import logging
import os
import re
import traceback

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.http import HttpResponseForbidden
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract.models import Contract, ContractDetail
from biz.djangoapps.ga_manager.models import Manager
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.util import cache_utils, course_utils, datetime_utils, validators
from edxmako.shortcuts import render_to_response, render_to_string

log = logging.getLogger(__name__)


def check_course_selection(func):
    """
    This checks user's course selection on cache,
    and redirects user to not_specified page if the selected parameters are not sufficient,
    and redirects user to 403 page if user's selected parameter is not accessible.

    :param func: function to be wrapped
    :returns: the wrapped function
    """

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        log.debug("request.path={}".format(request.path))
        user = request.user
        if not Manager.get_managers(user):
            log.warning("User(id={}) has no manager model.".format(user.id))
            return _render_403(request)

        # Collect organization, contract and course selection
        selection_organizations = Organization.find_by_user(user)
        selection_contracts = Contract.find_enabled_by_user(user)
        selection_contract_details = ContractDetail.find_enabled_by_user(user)
        request.selection_organizations = selection_organizations
        request.selection_contracts = selection_contracts
        request.selection_contract_details = _set_course_name_to_contract_details(selection_contract_details)

        request.current_organization = None
        request.current_manager = None
        request.current_contract = None
        request.current_course = None

        # Get from cache
        org_id, contract_id, course_id = cache_utils.get_course_selection(user)

        # Try to get the only-one organization
        if not org_id and len(selection_organizations) == 1:
            org_id = selection_organizations[0].id
        if not org_id:
            log.info("Redirect to org_not_specified page because org_id is not specified.")
            return _render_org_not_specified(request)

        # Validate access permission for organization
        try:
            org = validators.get_valid_organization(org_id)
        except ValidationError as e:
            log.warning(e.messages[0])
            return _render_403(request)
        request.current_organization = org

        # Validate access permission for manager
        try:
            manager = validators.get_valid_manager(user, org_id)
        except ValidationError as e:
            log.warning(e.messages[0])
            return _render_403(request)
        request.current_manager = manager

        # Try to get the only-one contract
        if not contract_id:
            contracts = Contract.find_enabled_by_manager(manager)
            if len(contracts) == 1:
                contract_id = contracts[0].id
        # If you're not Platformer, contract_id must be specified
        if not manager.is_platformer() and not contract_id:
            log.info("Redirect to contract_not_specified page because contract_id is not specified.")
            return _render_contract_not_specified(request)

        # Validate access permission for contract
        if contract_id:
            try:
                contract = validators.get_valid_contract(manager, contract_id)
            except ValidationError as e:
                log.warning(e.messages[0])
                return _render_403(request)
            request.current_contract = contract

            # Try to get the only-one course
            if not course_id:
                contract_details = ContractDetail.find_enabled_by_manager_and_contract(manager, contract)
                if len(contract_details) == 1:
                    course_id = unicode(contract_details[0].course_id)

            # Validate access permission for course
            if course_id:
                try:
                    course = validators.get_valid_course(manager, contract, course_id)
                except ValidationError as e:
                    log.warning(e.messages[0])
                    return _render_403(request)
                request.current_course = course

        # Validate feature permission
        if re.match('^/biz/organization/', request.path):
            if not manager.can_handle_organization():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'organization')
                )
                return _render_403(request)

        elif re.match('^/biz/contract/', request.path):
            if not manager.can_handle_contract():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'contract')
                )
                return _render_403(request)

        elif re.match('^/biz/manager/', request.path):
            if not manager.can_handle_manager():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'manager')
                )
                return _render_403(request)

        elif re.match('^/biz/course_operation/', request.path):
            if not manager.can_handle_course_operation():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'course_operation')
                )
                return _render_403(request)
            elif not course_id:
                log.info("Redirect to course_not_specified page because course_id is not specified.")
                return _render_course_not_specified(request)

        elif re.match('^/biz/achievement/', request.path):
            if not manager.can_handle_achievement():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'achievement')
                )
                return _render_403(request)
            elif not course_id:
                log.info("Redirect to course_not_specified page because course_id is not specified.")
                return _render_course_not_specified(request)

        elif re.match('^/biz/contract_operation/', request.path):
            if not manager.can_handle_contract_operation():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'contract_operation')
                )
                return _render_403(request)
            elif not contract_id:
                # if user has role(platformer and director:can_handle_contract_operation).
                log.info("Redirect to contract_not_specified page because contract_id is not specified.")
                return _render_contract_not_specified(request)


        log.debug("request.current_organization={}".format(getattr(request, 'current_organization', None)))
        log.debug("request.current_manager={}".format(getattr(request, 'current_manager', None)))
        log.debug("request.current_contract={}".format(getattr(request, 'current_contract', None)))
        log.debug("request.current_course={}".format(getattr(request, 'current_course', None)))
        log.debug("request.selection_organizations={}".format(getattr(request, 'selection_organizations', None)))
        log.debug("request.selection_contracts={}".format(getattr(request, 'selection_contracts', None)))
        log.debug("request.selection_contract_details={}".format(getattr(request, 'selection_contract_details', None)))

        # Set cache
        cache_utils.set_course_selection(user, org_id, contract_id, course_id)

        out = func(request, *args, **kwargs)
        return out

    return wrapper


def require_survey(func):
    """View decorator that requires that the user have download survey permissions. """

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        current_manager = getattr(request, 'current_manager', None)
        current_contract = getattr(request, 'current_contract', None)
        current_course = getattr(request, 'current_course', None)

        if (
            current_manager and current_contract and current_course and
            current_manager.can_handle_course_operation() and
            current_contract.is_spoc_available
        ):
            return func(request, *args, **kwargs)
        else:
            return _render_403(request)

    return wrapper


def handle_command_exception(output_file):
    """
    Command Exception Handler

    If the command failed, write 'NG' to output file (for monitoring).
    Otherwise, write 'OK'.

    :param output_file: file path to output command status and errors
    :returns: the wrapped function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            command_name = func.__module__.split('.')[-1]
            log.info(u"Command {} started at {}.".format(command_name, _now()))
            try:
                out = func(*args, **kwargs)
                msg = u"Command {} finished at {}.".format(command_name, _now())
                _output_command_status(output_file, 'OK', msg)
                log.info(msg)
                return out
            except Exception:
                msg = u"Command {} failed at {}.\n{}".format(command_name, _now(), traceback.format_exc())
                _output_command_status(output_file, 'NG', msg)
                log.error(msg)

        return wrapper

    return decorator


def _now():
    """Returns current datetime string with server timezone"""
    return datetime_utils.timezone_now().strftime('%Y-%m-%d %H:%M:%S.%f %Z')


def _output_command_status(output_file, status, msg=''):
    """
    Writes status and message to output file.

    Note: raises CommandError if anything goes wrong (so, only use for handle_command_exception)
    """

    if not output_file:
        raise CommandError("Output filename is not specified. output_file={}".format(output_file))
    dirname = os.path.dirname(output_file)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    try:
        with open(output_file, 'w') as f:
            f.write(u"{}\n{}".format(status, msg))
    except Exception:
        raise CommandError("Error occurred while writing output file. output_file={}".format(output_file))


def _set_course_name_to_contract_details(contract_details):
    """
    Exclude a ContractDetail object if the related course does not exist in modulestore,
    or set course name to the object

    :param contract_details: list of ContractDetail object
    :return: list of ContractDetail object
    """
    selection_contract_details = []
    for contract_detail in contract_details:
        course = course_utils.get_course(contract_detail.course_id)
        # Exclude non-existent course
        if course is not None:
            contract_detail.course_name = course.course_canonical_name or course.display_name
            selection_contract_details.append(contract_detail)

    return selection_contract_details


def _render_403(request):
    """Renders 403 page"""
    cache_utils.delete_course_selection(request.user)
    return HttpResponseForbidden(render_to_string('static_templates/403.html', {}))


def _render_org_not_specified(request):
    """Renders org_not_specified page"""
    messages.error(request, _("Organization is not specified."))
    return render_to_response('ga_course_selection/org_not_specified.html')


def _render_contract_not_specified(request):
    """Renders contract_not_specified page"""
    messages.error(request, _("Contract is not specified."))
    return render_to_response('ga_course_selection/contract_not_specified.html')


def _render_course_not_specified(request):
    """Renders course_not_specified page"""
    messages.error(request, _("Course is not specified."))
    return render_to_response('ga_course_selection/course_not_specified.html')

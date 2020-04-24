"""
Decorator utilities
"""
from functools import wraps
import logging
import os
import re
import traceback

from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.core.urlresolvers import reverse
from django.http import HttpResponseForbidden
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract.models import Contract, ContractDetail,\
    CONTRACT_TYPE_PF, CONTRACT_TYPE_GACCO_SERVICE,\
    CONTRACT_TYPE_OWNER_SERVICE, CONTRACT_TYPE_OWNERS
from biz.djangoapps.ga_manager.models import Manager
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_org_group.models import Group, Right, Child
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_sso_config.models import SsoConfig
from biz.djangoapps.util import cache_utils, course_utils, datetime_utils, validators
from edxmako.shortcuts import render_to_response, render_to_string

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from opaque_keys.edx.locator import CourseLocator


log = logging.getLogger(__name__)


def check_course_selection3(func):
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
            if not manager.can_handle_achievement():
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

        elif re.match('^/biz/contract_operation/reminder', request.path):
            if not manager.can_handle_contract_operation():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'contract_operation/reminder_mail')
                )
                return _render_403(request)

            elif not contract_id:
                # if user has role(platformer and director:can_handle_contract_operation).
                log.info("Redirect to contract_not_specified page because contract_id is not specified.")
                return _render_contract_not_specified(request)

        elif re.match('^/biz/contract_operation/students', request.path):
            if not manager.can_handle_contract_operation():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'contract_operation/students')
                )
                return _render_403(request)
            elif not contract_id:
                # if user has role(platformer and director:can_handle_contract_operation).
                log.info("Redirect to contract_not_specified page because contract_id is not specified.")
                return _render_contract_not_specified(request)

        elif re.match('^/biz/contract_operation/', request.path):
            if not manager.can_handle_contract_operation() or not manager.is_director():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'contract_operation')
                )
                return _render_403(request)
            elif not contract_id:
                # if user has role(platformer and director:can_handle_contract_operation).
                log.info("Redirect to contract_not_specified page because contract_id is not specified.")
                return _render_contract_not_specified(request)

        elif re.match('^/biz/member/', request.path):
            if not manager.can_handle_course_operation():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'member')
                )
                return _render_403(request)

        elif re.match('^/biz/group/', request.path):
            if not manager.can_handle_course_operation():
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'group')
                )
                return _render_403(request)

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
        # managers = Manager.get_managers(user)
        managers = list(Manager.objects.filter(user_id=user).values('id',
                                                               'org_id',
                                                               'manager_permissions__permission_name',
                                                               'manager_permissions__can_handle_organization',
                                                               'manager_permissions__can_handle_manager',
                                                               'manager_permissions__can_handle_contract',
                                                               'manager_permissions__can_handle_achievement',
                                                               'manager_permissions__permission_name',
                                                               'manager_permissions__can_handle_contract_operation',
                                                               'manager_permissions__can_handle_course_operation',
                                                               ))
        # if not Manager.get_managers(user):
        if not managers:
            log.warning("User(id={}) has no manager model.".format(user.id))
            return _render_403(request)
        # Collect organization, contract and course selection
        selection_organizations = Organization.find_by_user(user)
        # selection_contracts = Contract.find_enabled_by_user(user)
        managers_contract_types = get_contract_types_by_managers_custom(managers)
        selection_contracts = Contract.objects.enabled().filter(
            contractor_organization__in=selection_organizations,
            contractor_organization__managers__user=user,
            contract_type__in=managers_contract_types).order_by('-created')
        # selection_contract_details = ContractDetail.find_enabled_by_user(user)
        selection_contract_details = ContractDetail.objects.enabled().filter(
            contract__contractor_organization__managers__user=user,
            contract__contract_type__in=managers_contract_types).order_by('id')

        request.selection_organizations = selection_organizations
        request.selection_contracts = selection_contracts
        request.selection_contract_details = _set_course_name_to_contract_details(selection_contract_details)

        request.current_organization = None
        request.current_manager = None
        request.current_manager_values = None
        request.current_contract = None
        request.current_course = None

        # Get from cache
        org_id, contract_id, course_id = cache_utils.get_course_selection(user)
        # org_id, contract_id, course_id = (None, None, None)

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
            manager_value = {k.replace('manager_permissions__', ''): v for k, v in [i for i in managers if manager.id == i['id']][0].items()}
        except ValidationError as e:
            log.warning(e.messages[0])
            return _render_403(request)
        request.current_manager = manager
        request.current_manager_values = manager_value
        current_manager_contract_type = get_contract_types_custom(manager_value)
        request.current_manager_contract_type = current_manager_contract_type

        # Try to get the only-one contract
        if not contract_id:
            # contracts = Contract.find_enabled_by_manager(manager)
            contracts = Contract.objects.enabled().filter(
                contractor_organization=manager_value['org_id'],
                contractor_organization__managers__user=user,
                contract_type__in=current_manager_contract_type)
            if len(contracts) == 1:
                contract_id = contracts[0].id
        # If you're not Platformer, contract_id must be specified
        # if not manager.is_platformer() and not contract_id:
        if manager_value['permission_name'] != 'platformer' and not contract_id:
            log.info("Redirect to contract_not_specified page because contract_id is not specified.")
            return _render_contract_not_specified(request)

        # Validate access permission for contract
        if contract_id:
            try:
                # contract = validators.get_valid_contract(manager, contract_id)
                contract = Contract.objects.enabled().select_related('contractauth').get(
                    pk=contract_id,
                    contractor_organization__id=manager_value['org_id'],
                    contract_type__in=current_manager_contract_type
                )
            except ValidationError as e:
                log.warning(e.messages[0])
                return _render_403(request)
            request.current_contract = contract

            # Try to get the only-one course
            if not course_id:
                # contract_details = ContractDetail.find_enabled_by_manager_and_contract(manager, contract)
                contract_details = ContractDetail.objects.enabled().filter(
                    contract=contract,
                    contract__contract_type__in=current_manager_contract_type,
                    contract__contractor_organization__id=manager_value['org_id']
                )
                if len(contract_details) == 1:
                    course_id = unicode(contract_details[0].course_id)

            # Validate access permission for course
            if course_id:
                try:
                    # course = validators.get_valid_course(manager, contract, course_id)
                    course = get_valid_course_custom(manager, contract, course_id, selection_contract_details)
                except ValidationError as e:
                    log.warning(e.messages[0])
                    return _render_403(request)
                request.current_course = course
                try:
                    request.current_course.display_name = [i.course_name for i in request.selection_contract_details if i.course_id ==request.current_course.id][0]
                except:
                    pass
        # Validate feature permission
        if re.match('^/biz/organization/', request.path):
            # if not manager.can_handle_organization():
            if not manager_value['can_handle_organization']:
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'organization')
                )
                return _render_403(request)

        elif re.match('^/biz/contract/', request.path):
            # if not manager.can_handle_contract():
            if not manager_value['can_handle_contract']:
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'contract')
                )
                return _render_403(request)

        elif re.match('^/biz/manager/', request.path):
            # if not manager.can_handle_manager():
            if not manager_value['can_handle_manager']:
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'manager')
                )
                return _render_403(request)

        elif re.match('^/biz/course_operation/', request.path):
            # if not manager.can_handle_achievement():
            if not manager_value['can_handle_achievement']:
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'course_operation')
                )
                return _render_403(request)
            elif not course_id:
                log.info("Redirect to course_not_specified page because course_id is not specified.")
                return _render_course_not_specified(request)

        elif re.match('^/biz/achievement/', request.path):
            # if not manager.can_handle_achievement():
            if not manager_value['can_handle_achievement']:
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'achievement')
                )
                return _render_403(request)
            elif not course_id:
                log.info("Redirect to course_not_specified page because course_id is not specified.")
                return _render_course_not_specified(request)

        elif re.match('^/biz/contract_operation/reminder', request.path):
            # if not manager.can_handle_contract_operation():
            if not manager_value['can_handle_contract_operation']:
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'contract_operation/reminder_mail')
                )
                return _render_403(request)

            elif not contract_id:
                # if user has role(platformer and director:can_handle_contract_operation).
                log.info("Redirect to contract_not_specified page because contract_id is not specified.")
                return _render_contract_not_specified(request)

        elif re.match('^/biz/contract_operation/students', request.path):
            # if not manager.can_handle_contract_operation():
            if not manager_value['can_handle_contract_operation']:
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'contract_operation/students')
                )
                return _render_403(request)
            elif not contract_id:
                # if user has role(platformer and director:can_handle_contract_operation).
                log.info("Redirect to contract_not_specified page because contract_id is not specified.")
                return _render_contract_not_specified(request)

        elif re.match('^/biz/contract_operation/', request.path):
            # if not manager.can_handle_contract_operation() or not manager.is_director():
            if not manager_value['can_handle_contract_operation'] or manager_value['permission_name'] != 'director':
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'contract_operation')
                )
                return _render_403(request)
            elif not contract_id:
                # if user has role(platformer and director:can_handle_contract_operation).
                log.info("Redirect to contract_not_specified page because contract_id is not specified.")
                return _render_contract_not_specified(request)

        elif re.match('^/biz/member/', request.path):
            # if not manager.can_handle_course_operation():
            if not manager_value['can_handle_course_operation']:
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'member')
                )
                return _render_403(request)

        elif re.match('^/biz/group/', request.path):
            # if not manager.can_handle_course_operation():
            if not manager_value['can_handle_course_operation']:
                log.warning(
                    "Manager(id={}) has no permission to handle '{}' feature.".format(
                        manager.id, 'group')
                )
                return _render_403(request)

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
            current_manager.can_handle_achievement() and
            current_contract.is_spoc_available
        ):
            return func(request, *args, **kwargs)
        else:
            return _render_403(request)

    return wrapper


class ExitWithWarning(Exception):
    pass


def handle_command_exception(output_file, output_return_value=False):
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
                if output_return_value:
                    msg = '{}\n{}'.format(out, msg)
                _output_command_status(output_file, 'OK', msg)
                log.info(msg)
                return out
            except ExitWithWarning as e:
                msg = e.message
                _output_command_status(output_file, 'WARNING', msg)
                log.warning(msg, exc_info=True)
            except Exception:
                msg = u"Command {} failed at {}.\n{}".format(command_name, _now(), traceback.format_exc())
                _output_command_status(output_file, 'NG', msg)
                log.error(msg)

        wrapper._original = func
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


def _set_course_name_to_contract_details3(contract_details):
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


def _set_course_name_to_contract_details(contract_details):
    """
    Exclude a ContractDetail object if the related course does not exist in modulestore,
    or set course name to the object

    :param contract_details: list of ContractDetail object
    :return: list of ContractDetail object
    """
    courses = list(CourseOverview.objects.filter(id__in=[i.course_id for i in contract_details]).values_list('id', 'display_name'))
    selection_contract_details = []
    for contract_detail in contract_details:
        # course = course_utils.get_course(contract_detail.course_id)
        course = [i for i in courses if i[0] == str(contract_detail.course_id)]
        # Exclude non-existent course
        # if course is not None:
        if course:
            contract_detail.course_name = course[0][1]
            selection_contract_details.append(contract_detail)

    return selection_contract_details


def _render_403(request):
    """Renders 403 page"""
    cache_utils.delete_course_selection(request.user)
    cache_utils.delete_organization_group(request.user)
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


def check_organization_group3(func):
    """
    This checks user's organization group on cache,
    and redirects user to 403 page if user's organization group is not found.

    :param func: function to be wrapped
    :returns: the wrapped function
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        log.debug("request.path={}".format(request.path))
        user = request.user
        org = request.current_organization

        manager = Manager.get_manager(user=user, org=org)
        if not manager:
            log.warning("User(id={}) has no manager model.".format(user.id))
            return _render_403(request)

        if org and manager and manager.is_manager() and not manager.is_director():
            group, visible_group_ids = cache_utils.get_organization_group(user)

            if not group or org is not group.org:
                rights = Right.objects.filter(user=user, org=org).select_related('group')
                if rights.exists():
                    group = rights.first().group
                    visible_group_ids = []
                    for right in rights:
                        if right.group.child.exists():
                            child_group_ids = [right.group.id]
                            for child in right.group.child.all():
                                if child.list.strip():
                                    child_group_ids.extend(int(id) for id in child.list.split(','))
                            visible_group_ids.extend(child_group_ids)
                else:
                    group = None
                    visible_group_ids = []

        else:
            # If not selected organization, empty set.
            group = None
            visible_group_ids = []

        # Set request
        request.current_organization_group = group
        log.info('set request.current_organization_group:' + str(group.id if group else ''))
        request.current_organization_visible_group_ids = visible_group_ids
        log.info('set request.current_organization_visible_group_ids:' + ','.join(map(str, visible_group_ids)))
        # Set cache
        cache_utils.set_organization_group(user, group, visible_group_ids)

        out = func(request, *args, **kwargs)
        return out

    return wrapper


def check_organization_group(func):
    """
    This checks user's organization group on cache,
    and redirects user to 403 page if user's organization group is not found.

    :param func: function to be wrapped
    :returns: the wrapped function
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        log.debug("request.path={}".format(request.path))
        user = request.user
        org = request.current_organization
        manager = request.current_manager
        manager_value = request.current_manager_values

        # manager = Manager.get_manager(user=user, org=org)
        if not manager:
            log.warning("User(id={}) has no manager model.".format(user.id))
            return _render_403(request)

        # if org and manager and manager.is_manager() and not manager.is_director():
        if org and manager and manager_value['permission_name'] == 'manager':
            group, visible_group_ids = cache_utils.get_organization_group(user)

            if not group or org is not group.org:
                rights = Right.objects.filter(user=user, org=org).select_related('group')
                if rights.exists():
                    group = rights.first().group
                    visible_group_ids = []
                    for right in rights:
                        if right.group.child.exists():
                            child_group_ids = [right.group.id]
                            for child in right.group.child.all():
                                if child.list.strip():
                                    child_group_ids.extend(int(id) for id in child.list.split(','))
                            visible_group_ids.extend(child_group_ids)
                else:
                    group = None
                    visible_group_ids = []

        else:
            # If not selected organization, empty set.
            group = None
            visible_group_ids = []

        # Set request
        request.current_organization_group = group
        log.info('set request.current_organization_group:' + str(group.id if group else ''))
        request.current_organization_visible_group_ids = visible_group_ids
        log.info('set request.current_organization_visible_group_ids:' + ','.join(map(str, visible_group_ids)))
        # Set cache
        cache_utils.set_organization_group(user, group, visible_group_ids)

        out = func(request, *args, **kwargs)
        return out

    return wrapper


def control_specific_organization(func):
    """
    account setting not display control reverse dashboard
    :returns: the wrapped function
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not SsoConfig.user_control_process(request.user.id):
            return redirect(reverse('dashboard'))
        out = func(request, *args, **kwargs)
        return out
    return wrapper


def get_contract_types_by_managers_custom(managers):
    """
    Get contract types related to managers' permissions

    :param managers: list of Manager
    :return: list of contract types
    """
    contract_types = []
    if any([True for manager in managers if manager['manager_permissions__permission_name'] == 'aggregator']):
        contract_types.append(CONTRACT_TYPE_OWNERS[0])
    if any([True for manager in managers if manager['manager_permissions__permission_name'] in ['director', 'manager']]):
        contract_types.append(CONTRACT_TYPE_PF[0])
        contract_types.append(CONTRACT_TYPE_GACCO_SERVICE[0])
        contract_types.append(CONTRACT_TYPE_OWNER_SERVICE[0])
    return contract_types

def get_contract_types_custom(manager):
    """
    Get contract types related to manager's permissions

    :param manager: Manager object
    :return: list of contract types
    """
    contract_types = []
    if manager['permission_name'] == 'aggregator':
        contract_types.append(CONTRACT_TYPE_OWNERS[0])
    if manager['permission_name'] in ['director', 'manager']:
        contract_types.append(CONTRACT_TYPE_PF[0])
        contract_types.append(CONTRACT_TYPE_GACCO_SERVICE[0])
        contract_types.append(CONTRACT_TYPE_OWNER_SERVICE[0])
    return contract_types


def get_valid_course_custom(manager, contract, course_id, details):
    """
    Check access permission for Course and return the valid object

    :param manager: Manager object which the logged-in user works as
    :param contract: Contract object
    :param course_id: str id of the course, not a CourseKey
    :return: the valid modulestore's course object, or raises ValidationError if invalid
    """
    # Check if the course exists in modulestore
    course = course_utils.get_course(course_id)
    if course is None:
        raise ValidationError("No such course was found in modulestore. course_id={}".format(course_id))

    # Check if the course exists in biz database
    contract_details = [i for i in details if str(i.course_id) == course_id]
    if len(contract_details) == 0:
        raise ValidationError(
            "Manager(id={}) has no permission to access to the specified course. contract_id={}, course_id={}".format(
                manager.id, contract.id, course_id)
        )
    elif len(contract_details) > 1:
        log.warning(
            "Manager(id={}) has duplicated course details with the same course_id. contract_id={}, course_id={}".format(
                manager.id, contract.id, course_id)
        )
    return course
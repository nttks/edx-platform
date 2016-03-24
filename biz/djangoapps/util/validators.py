"""
Validators for biz
"""
import logging

from django.core.exceptions import ValidationError

from biz.djangoapps.ga_contract.models import (
    Contract, ContractDetail,
    CONTRACT_TYPE_PF, CONTRACT_TYPE_OWNERS, CONTRACT_TYPE_GACCO_SERVICE, CONTRACT_TYPE_OWNER_SERVICE,
)
from biz.djangoapps.ga_manager.models import Manager
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.util import course_utils

log = logging.getLogger(__name__)


def get_valid_organization(org_id):
    """
    Check access permission for Organization and return the valid object

    :param org_id: Organization id
    :return: the valid Organization object, or raises ValidationError if invalid
    """
    try:
        org = Organization.objects.get(pk=org_id)
    except Organization.DoesNotExist:
        raise ValidationError("No such organization(id={}) was found.".format(org_id))
    return org


def get_valid_manager(user, org_id):
    """
    Check access permission for Manager and return the valid object

    :param user: logged-in user object
    :param org_id: Organization id
    :return: the valid Manager object, or raises ValidationError if invalid
    """
    manager = Manager.get_manager(user, org_id)
    if manager is None:
        raise ValidationError(
            "User(id={}) has no permission to access to the specified organization(id={}).".format(
                user.id, org_id)
        )
    return manager


def get_valid_contract(manager, contract_id):
    """
    Check access permission for Contract and return the valid object

    :param manager: Manager object which the logged-in user works as
    :param contract_id: Contract id
    :return: the valid Contract object, or raises ValidationError if invalid
    """
    contract_types = []
    if manager.is_aggregator():
        contract_types.append(CONTRACT_TYPE_OWNERS[0])
    if manager.is_director() or manager.is_manager():
        contract_types.append(CONTRACT_TYPE_PF[0])
        contract_types.append(CONTRACT_TYPE_GACCO_SERVICE[0])
        contract_types.append(CONTRACT_TYPE_OWNER_SERVICE[0])

    try:
        contract = Contract.get_enabled_by_contractor_and_contract_id_and_contract_types(
            manager.org.id, contract_id, contract_types
        )
    except Contract.DoesNotExist:
        raise ValidationError(
            "Manager(id={}) has no permission to access to the specified contract(id={}).".format(
                manager.id, contract_id)
        )
    return contract


def get_valid_course(manager, contract, course_id):
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
    contract_types = []
    if manager.is_director() or manager.is_manager():
        contract_types.append(CONTRACT_TYPE_PF[0])
        contract_types.append(CONTRACT_TYPE_GACCO_SERVICE[0])
        contract_types.append(CONTRACT_TYPE_OWNER_SERVICE[0])

    contract_details = ContractDetail.find_enabled_by_contractor_and_contract_id_and_contract_types_and_course_id(
        manager.org.id, contract.id, contract_types, course.id
    )
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

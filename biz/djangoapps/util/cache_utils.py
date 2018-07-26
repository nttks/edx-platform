"""
Cache utilities
"""
import logging

from django.core.cache import cache

COURSE_SELECTION_CACHE_KEY = 'biz.course_selection:{}'
COURSE_SELECTION_CACHE_TIMEOUT = 60 * 60 * 24 * 30  # 30 days

ORGANIZATION_GROUP_CACHE_KEY = 'biz.organization_group:{}'
ORGANIZATION_GROUP_CACHE_TIMEOUT = COURSE_SELECTION_CACHE_TIMEOUT

log = logging.getLogger(__name__)


def get_course_selection(user):
    """
    Get course selection object (tuple of org_id, contract_id, course_id) from cache

    :param user: logged-in user object
    :return: tuple of org_id, contract_id, course_id, or (None, None, None) if key doesn't exist in cache
    """
    key = _course_selection_key(user)
    org_id, contract_id, course_id = cache.get(key, (None, None, None))
    log.debug("Get course selection from cache. key={}, org_id={}, contract_id={}, course_id={}".format(
        key, org_id, contract_id, course_id
    ))
    return org_id, contract_id, course_id


def set_course_selection(user, org_id, contract_id, course_id):
    """
    Set course selection object (tuple of org_id, contract_id, course_id) into cache

    :param user: logged-in user object
    :param org_id: Organization id
    :param contract_id: Contract id
    :param course_id: str id of the course, not a CourseKey
    """
    key = _course_selection_key(user)
    log.debug("Set course selection to cache. key={}, org_id={}, contract_id={}, course_id={}".format(
        key, org_id, contract_id, course_id
    ))
    cache.set(key, (org_id, contract_id, course_id), COURSE_SELECTION_CACHE_TIMEOUT)


def delete_course_selection(user):
    """
    Delete course selection object from cache

    :param user: logged-in user object
    """
    key = _course_selection_key(user)
    log.debug("Delete course selection cache. key={}".format(key))
    cache.delete(key)


def _course_selection_key(user):
    """
    Returns the cache key for the user

    :param user: logged-in user object
    :return: the cache key for the user
    """
    return COURSE_SELECTION_CACHE_KEY.format(user.id)


def get_organization_group(user):
    """
    Get organization group object (tuple of org_group, visible_org_id_list) from cache

    :param user: logged-in user object
    :return: tuple of org_group, visible_group_ids, or (None, None) if key doesn't exist in cache
    """
    key = _organization_group_key(user)
    org_group, visible_group_ids = cache.get(key, (None, None))
    log.debug("Get organization group and list of visible group id from cache. key={}, org_group={}, visible_group_ids={}".format(
        key, org_group, visible_group_ids
    ))
    return org_group, visible_group_ids


def set_organization_group(user, org_group, visible_group_ids):
    """
    Set course selection object (tuple of org_id, visible_group_ids) into cache

    :param user: logged-in user object
    :param org_group: Group model
    :param visible_group_ids: Group model id list
    """
    key = _organization_group_key(user)
    log.debug("Set organization group to cache. key={}, org_group={}, visible_group_ids={}".format(
        key, org_group, visible_group_ids
    ))
    cache.set(key, (org_group, visible_group_ids), ORGANIZATION_GROUP_CACHE_TIMEOUT)


def delete_organization_group(user):
    """
    Delete organization group object from cache

    :param user: logged-in user object
    """
    key = _organization_group_key(user)
    log.debug("Delete organization group cache. key={}".format(key))
    cache.delete(key)


def _organization_group_key(user):
    """
    Returns the cache key for the user

    :param user: logged-in user object
    :return: the cache key for the user
    """
    return ORGANIZATION_GROUP_CACHE_KEY.format(user.id)

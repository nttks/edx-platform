"""
This file contains celery tasks for contentstore views
"""
import json
import logging
import re

from celery.task import task
from celery.utils.log import get_task_logger
from datetime import datetime
from pytz import UTC

from django.contrib.auth.models import User

from contentstore.courseware_index import CoursewareSearchIndexer, LibrarySearchIndexer, SearchIndexingError
from contentstore.utils import initialize_permissions
from course_action_state.models import CourseRerunState
from opaque_keys.edx.keys import CourseKey
from xmodule.course_module import CourseFields
from xmodule.modulestore import EdxJSONEncoder
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import DuplicateCourseError, ItemNotFoundError

LOGGER = get_task_logger(__name__)
FULL_COURSE_REINDEX_THRESHOLD = 1


def _make_library_key_suffix(store, base_library_key):
    """
    Make library_key for rerun library.
    It increases sequentially from '___0001'.
    """
    LIB_KEY_SUFFIX_REGEX = r'^(?P<base_text>.*)(?P<suffix>___[0-9]{4}$)'
    lib_key_suffix_pattern = re.compile(LIB_KEY_SUFFIX_REGEX)
    matches = lib_key_suffix_pattern.match(base_library_key)
    num = 0
    base_text = base_library_key
    if matches:
        num = int(matches.group('suffix')[3:])
        base_text = matches.group('base_text')

    for offset in range(1, 10000):
        check_key = '{0}___{1:04d}'.format(base_text, (num + offset) % 10000)
        source_library_key = CourseKey.from_string(check_key)
        if store.get_library(source_library_key) is None:
            return check_key

    LOGGER.warning('Failed to rerun. There is no library key that can be duplicated.')
    raise DuplicateCourseError(base_library_key, base_library_key)


def _update_source_library_id(store, destination_course_key, user_id, src_libray_keys, dest_library_keys):
    """
    update source_library_id for library_content of vertical
    """
    items = store.get_items(destination_course_key)
    for item in items:
        if item.scope_ids.block_type == 'library_content':
            source_library_id = getattr(item, 'source_library_id', '')
            if source_library_id and source_library_id in src_libray_keys:
                new_source_library_id = dest_library_keys[src_libray_keys.index(source_library_id)]
                setattr(item, 'source_library_id', new_source_library_id)
                store.update_item(item, user_id)


@task()
def rerun_course(source_course_key_string, destination_course_key_string, user_id, fields=None, target_libraries=None):
    """
    Reruns a course in a new celery task.
    """
    # import here, at top level this import prevents the celery workers from starting up correctly
    from edxval.api import copy_course_videos

    try:
        store = modulestore()
        if target_libraries is not None:
            target_libraries_dest = [_make_library_key_suffix(store, library) for library in target_libraries]
            fields_load = json.loads(fields)
            fields_load['target_library'] = target_libraries_dest
            fields = json.dumps(fields_load, cls=EdxJSONEncoder)

        # deserialize the payload
        source_course_key = CourseKey.from_string(source_course_key_string)
        destination_course_key = CourseKey.from_string(destination_course_key_string)
        fields = deserialize_fields(fields) if fields else None

        # use the split modulestore as the store for the rerun course,
        # as the Mongo modulestore doesn't support multiple runs of the same course.
        with store.default_store('split'):
            # clone library
            if target_libraries is not None:
                for (target_library, target_library_dest) in zip(target_libraries, target_libraries_dest):
                    target_library_src_key = CourseKey.from_string(target_library)
                    target_library_dest_key = CourseKey.from_string(target_library_dest)
                    store.clone_course(target_library_src_key, target_library_dest_key, user_id, ga_rerun_library=True)
            store.clone_course(source_course_key, destination_course_key, user_id, fields=fields)

            # update source_library_id for library_content of vertical
            if target_libraries is not None:
                _update_source_library_id(store, destination_course_key, user_id, target_libraries, target_libraries_dest)

        # set initial permissions for the user to access the course.
        initialize_permissions(destination_course_key, User.objects.get(id=user_id))

        # update state: Succeeded
        CourseRerunState.objects.succeeded(course_key=destination_course_key)

        # call edxval to attach videos to the rerun
        copy_course_videos(source_course_key, destination_course_key)

        return "succeeded"

    except DuplicateCourseError as exc:
        # do NOT delete the original course, only update the status
        CourseRerunState.objects.failed(course_key=destination_course_key)
        logging.exception(u'Course Rerun Error')
        return "duplicate course"

    # catch all exceptions so we can update the state and properly cleanup the course.
    except Exception as exc:  # pylint: disable=broad-except
        # update state: Failed
        CourseRerunState.objects.failed(course_key=destination_course_key)
        logging.exception(u'Course Rerun Error')

        try:
            # cleanup any remnants of the course
            modulestore().delete_course(destination_course_key, user_id)
        except ItemNotFoundError:
            # it's possible there was an error even before the course module was created
            pass

        return "exception: " + unicode(exc)


def deserialize_fields(json_fields):
    fields = json.loads(json_fields)
    for field_name, value in fields.iteritems():
        fields[field_name] = getattr(CourseFields, field_name).from_json(value)
    return fields


def _parse_time(time_isoformat):
    """ Parses time from iso format """
    return datetime.strptime(
        # remove the +00:00 from the end of the formats generated within the system
        time_isoformat.split('+')[0],
        "%Y-%m-%dT%H:%M:%S.%f"
    ).replace(tzinfo=UTC)


@task()
def update_search_index(course_id, triggered_time_isoformat):
    """ Updates course search index. """
    try:
        course_key = CourseKey.from_string(course_id)
        CoursewareSearchIndexer.index(modulestore(), course_key, triggered_at=(_parse_time(triggered_time_isoformat)))

    except SearchIndexingError as exc:
        LOGGER.error('Search indexing error for complete course %s - %s', course_id, unicode(exc))
    else:
        LOGGER.debug('Search indexing successful for complete course %s', course_id)


@task()
def update_library_index(library_id, triggered_time_isoformat):
    """ Updates course search index. """
    try:
        library_key = CourseKey.from_string(library_id)
        LibrarySearchIndexer.index(modulestore(), library_key, triggered_at=(_parse_time(triggered_time_isoformat)))

    except SearchIndexingError as exc:
        LOGGER.error('Search indexing error for library %s - %s', library_id, unicode(exc))
    else:
        LOGGER.debug('Search indexing successful for library %s', library_id)


@task()
def push_course_update_task(course_key_string, course_subscription_id, course_display_name):
    """
    Sends a push notification for a course update.
    """
    # TODO Use edx-notifications library instead (MA-638).
    from .push_notification import send_push_course_update
    send_push_course_update(course_key_string, course_subscription_id, course_display_name)

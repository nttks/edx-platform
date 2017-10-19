"""
Views related to content libraries.
A content library is a structure containing XBlocks which can be re-used in the
multiple courses.
"""
from __future__ import absolute_import

import json
import logging

from contentstore.views.item import create_xblock_info
from contentstore.utils import reverse_course_url, reverse_library_url, add_instructor
from django.http import HttpResponseNotAllowed, Http404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from edxmako.shortcuts import render_to_response
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import LibraryLocator, LibraryUsageLocator
from openedx.core.djangoapps.ga_optional.api import is_available
from openedx.core.djangoapps.ga_optional.models import LIBRARY_OPTION_KEY
from xmodule.modulestore.exceptions import DuplicateCourseError
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore
from .user import user_with_role

from .component import get_component_templates, CONTAINER_TEMPLATES
from student.auth import (
    STUDIO_VIEW_USERS, STUDIO_EDIT_ROLES, get_user_permissions, has_studio_read_access, has_studio_write_access
)
from student.roles import CourseInstructorRole, CourseStaffRole, LibraryUserRole, GlobalStaff, UserBasedRole
from util.json_request import expect_json, JsonResponse, JsonResponseBadRequest

__all__ = ['library_handler', 'course_library_handler', 'manage_library_users']

log = logging.getLogger(__name__)

LIBRARIES_ENABLED = settings.FEATURES.get('ENABLE_CONTENT_LIBRARIES', False)


def _get_course_and_check_access(course_key, user, depth=0):
    """
    Internal method used to calculate and return the locator and
    course module for the view functions in this file.
    """
    if not has_studio_write_access(user, course_key):
        raise PermissionDenied()
    course_module = modulestore().get_course(course_key, depth=depth)
    return course_module


@login_required
@ensure_csrf_cookie
@require_http_methods(('GET', 'POST'))
def library_handler(request, library_key_string=None):
    """
    library_handler is not used in gacco.
    Please use course_library_handler.
    """
    if not LIBRARIES_ENABLED:
        log.exception("Attempted to use the content library API when the libraries feature is disabled.")
        raise Http404  # Should never happen because we test the feature in urls.py also

    if library_key_string is not None and request.method == 'POST':
        return HttpResponseNotAllowed(("POST",))

    if request.method == 'POST':
        return _create_library(request)

    # request method is get, since only GET and POST are allowed by @require_http_methods(('GET', 'POST'))
    if library_key_string:
        return _display_library(library_key_string, request)

    return _list_libraries(request)


@login_required
@ensure_csrf_cookie
@require_http_methods(('GET', 'POST'))
def course_library_handler(request, course_key_string=None, library_key_string=None):
    """
    RESTful interface to most content library related functionality.
    """
    if not LIBRARIES_ENABLED:
        log.exception("Attempted to use the content library API when the libraries feature is disabled.")
        raise Http404  # Should never happen because we test the feature in urls.py also

    instructor_courses = UserBasedRole(request.user, CourseInstructorRole.ROLE).courses_with_role()
    global_staff = GlobalStaff().has_user(request.user)
    course_key = CourseKey.from_string(course_key_string)
    if not is_available(LIBRARY_OPTION_KEY, course_key):
        raise Http404
    if not instructor_courses and not global_staff:
        raise Http404

    if request.method == 'POST':
        if library_key_string:
            return HttpResponseNotAllowed(("POST",))
        else:
            response = _create_library(request, course_key_string)
            return response
    # request method is get, since only GET and POST are allowed by @require_http_methods(('GET', 'POST'))
    if not course_key_string:
        raise Http404
    if library_key_string:
        with modulestore().bulk_operations(course_key):
            course_module = _get_course_and_check_access(course_key, request.user, depth=None)
            if not course_module:
                raise Http404

            target_libraries = course_module.target_library
            if library_key_string in target_libraries:
                return _display_library(library_key_string, request, course_key_string)
            else:
                raise Http404
    return redirect(reverse_course_url('library_listing', unicode(course_key_string)))


def _display_library(library_key_string, request, course_key_string):
    """
    Displays single library
    """
    library_key = CourseKey.from_string(library_key_string)
    if not isinstance(library_key, LibraryLocator):
        log.exception("Non-library key passed to content libraries API.")  # Should never happen due to url regex
        raise Http404  # This is not a library
    course_key = CourseKey.from_string(course_key_string)
    if not has_studio_read_access(request.user, course_key):
        log.exception(
            u"User %s tried to access course %s without permission",
            request.user.username, unicode(course_key)
        )
        raise PermissionDenied()

    library = modulestore().get_library(library_key)
    if library is None:
        log.exception(u"Library %s not found", unicode(library_key))
        raise Http404

    response_format = 'html'
    if (
            request.REQUEST.get('format', 'html') == 'json' or
            'application/json' in request.META.get('HTTP_ACCEPT', 'text/html')
    ):
        response_format = 'json'

    return library_blocks_view(library, request.user, response_format, course_key_string)


def _list_libraries(request, course_key_string):
    """
    List all accessible libraries
    """
    course_key = CourseKey.from_string(course_key_string)

    libraries = modulestore().get_libraries()
    with modulestore().bulk_operations(course_key):
        course_module = _get_course_and_check_access(course_key, request.user, depth=None)
        if not course_module:
            raise Http404

        target_libraries = course_module.target_library
        for library in libraries[:]:
            if unicode(library.location.library_key) not in target_libraries:
                libraries.remove(library)

    lib_info = [
        {
            "display_name": lib.display_name,
            "library_key": unicode(lib.location.library_key),
        }
        for lib in libraries
    ]
    return JsonResponse(lib_info)


@expect_json
def _create_library(request, course_key_string=None):
    """
    Helper method for creating a new library.
    """
    if not course_key_string:
        raise Http404

    course_key = CourseKey.from_string(course_key_string)
    course_module = _get_course_and_check_access(course_key, request.user)
    if not course_module:
        raise Http404

    display_name = None
    try:
        display_name = request.json['display_name']
        library = request.json.get('number', None)
        if library is None:
            library = request.json['library']
        store = modulestore()
        with store.default_store(ModuleStoreEnum.Type.split):
            new_lib = store.create_library(
                org=course_module.org,
                library=library,
                user_id=request.user.id,
                fields={"display_name": display_name},
            )
        # Give the user admin ("Instructor") role for this library:
        add_instructor(new_lib.location.library_key, request.user, request.user)
    except KeyError as error:
        log.exception("Unable to create library - missing required JSON key.")
        return JsonResponseBadRequest({
            "ErrMsg": _("Unable to create library - missing required field '{field}'").format(field=error.message)
        })
    except InvalidKeyError as error:
        log.exception("Unable to create library - invalid key.")
        return JsonResponseBadRequest({
            "ErrMsg": _("Unable to create library '{name}'.\n\n{err}").format(name=display_name, err=error.message)
        })
    except DuplicateCourseError:
        log.exception("Unable to create library - one already exists with the same key.")
        return JsonResponseBadRequest({
            'ErrMsg': _(
                'There is already a library defined with the same '
                'organization and library code. Please '
                'change your library code so that it is unique within your organization.'
            )
        })

    lib_key_str = unicode(new_lib.location.library_key)
    libraries = course_module.target_library
    libraries.append(lib_key_str)
    setattr(course_module, 'target_library', libraries)
    modulestore().update_item(course_module, request.user.id)

    return JsonResponse({
        'url': reverse_course_url('course_library_handler', course_key_string, kwargs={'library_key_string': lib_key_str}),
        'library_key': lib_key_str,
    })


def library_blocks_view(library, user, response_format, course_key_string=None):
    """
    The main view of a course's content library.
    Shows all the XBlocks in the library, and allows adding/editing/deleting
    them.
    Can be called with response_format="json" to get a JSON-formatted list of
    the XBlocks in the library along with library metadata.

    Assumes that read permissions have been checked before calling this.
    """
    assert isinstance(library.location.library_key, LibraryLocator)
    assert isinstance(library.location, LibraryUsageLocator)

    children = library.children
    if response_format == "json":
        # The JSON response for this request is short and sweet:
        prev_version = library.runtime.course_entry.structure['previous_version']
        return JsonResponse({
            "display_name": library.display_name,
            "library_id": unicode(library.location.library_key),
            "version": unicode(library.runtime.course_entry.course_key.version),
            "previous_version": unicode(prev_version) if prev_version else None,
            "blocks": [unicode(x) for x in children],
        })

    can_edit = has_studio_write_access(user, library.location.library_key)

    xblock_info = create_xblock_info(library, include_ancestor_info=False, graders=[])
    component_templates = get_component_templates(library, library=True) if can_edit else []

    course_key = CourseKey.from_string(course_key_string)

    with modulestore().bulk_operations(course_key):
        course_module = _get_course_and_check_access(course_key, user, depth=None)
        if not course_module:
            raise Http404

    return render_to_response('library.html', {
        'can_edit': can_edit,
        'context_library': library,
        'component_templates': component_templates,
        'xblock_info': xblock_info,
        'templates': CONTAINER_TEMPLATES,
        'context_course': course_module,
        'library_option': is_available(LIBRARY_OPTION_KEY, course_key),
    })


def manage_library_users(request, library_key_string):
    """
    Studio UI for editing the users within a library.

    Uses the /course_team/:library_key/:user_email/ REST API to make changes.
    """
    library_key = CourseKey.from_string(library_key_string)
    if not isinstance(library_key, LibraryLocator):
        raise Http404  # This is not a library
    user_perms = get_user_permissions(request.user, library_key)
    if not user_perms & STUDIO_VIEW_USERS:
        raise PermissionDenied()
    library = modulestore().get_library(library_key)
    if library is None:
        raise Http404

    # Segment all the users explicitly associated with this library, ensuring each user only has one role listed:
    instructors = set(CourseInstructorRole(library_key).users_with_role())
    staff = set(CourseStaffRole(library_key).users_with_role()) - instructors
    users = set(LibraryUserRole(library_key).users_with_role()) - instructors - staff

    formatted_users = []
    for user in instructors:
        formatted_users.append(user_with_role(user, 'instructor'))
    for user in staff:
        formatted_users.append(user_with_role(user, 'staff'))
    for user in users:
        formatted_users.append(user_with_role(user, 'library_user'))

    return render_to_response('manage_users_lib.html', {
        'context_library': library,
        'users': formatted_users,
        'allow_actions': bool(user_perms & STUDIO_EDIT_ROLES),
        'library_key': unicode(library_key),
        'lib_users_url': reverse_library_url('manage_library_users', library_key_string),
        'show_children_previews': library.show_children_previews
    })


import logging
import re

from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import redirect

from courseware.access import has_access
from courseware.courses import get_course_overview_with_access
from courseware.ga_access import is_terminated
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from courseware.courses import get_course_with_access, get_permission_for_course_about
from openedx.core.djangoapps.ga_optional.api import is_available
from openedx.core.djangoapps.ga_optional.models import CUSTOM_LOGO_OPTION_KEY
from openedx.core.lib.courses import custom_logo_url

log = logging.getLogger(__name__)


COURSEWARE_URL = r'^/courses/{}/(?P<suffix>.*$)'.format(settings.COURSE_ID_PATTERN)
COURSEWARE_URL_PATTERN = re.compile(COURSEWARE_URL)


class CourseTerminatedCheckMiddleware(object):
    """
    Middleware to check whether course has been terminated.
    """

    def process_request(self, request):
        course_key = None

        is_target, course_id = self._check_target_path(request)
        if is_target and course_id:
            try:
                course_key = CourseKey.from_string(course_id)
            except InvalidKeyError:
                # do NOT raise HTTP404 here. should raise at each view if need be.
                pass

        # If could not get course_key, nothing to do.
        if not course_key:
            return

        try:
            course = get_course_overview_with_access(request.user, 'load', course_key)
        except Http404:
            # If course does not exist, nothing to do.
            return

        is_staff = has_access(request.user, 'staff', course)
        if is_terminated(course, request.user, is_staff):
            log.warning(
                'Cannot access to the terminated course. User({user_id}), Path({path})'.format(
                    user_id=request.user.id, path=request.path
                )
            )
            return redirect(reverse('dashboard'))

    def _check_target_path(self, request):
        matches = COURSEWARE_URL_PATTERN.match(request.path)
        if matches:
            for config in getattr(settings, 'COURSE_TERMINATED_CHECK_EXCLUDE_PATH', []):
                path = config.get('path', '')
                # We need to remove the leading slash since it is included in COURSEWARE_URL.
                path = path[1:] if path.startswith('/') else path
                if matches.group('suffix') == path:
                    return False, None
            return True, matches.group('course_id')
        return False, None


class CustomLogoMiddleware(object):
    """
    When it is the URL of the course series, obtain the setting
    of the custom logo from the course ID
    """

    COURSE_URL_PATTERN = re.compile(r'^/courses/{}/'.format(settings.COURSE_ID_PATTERN))
    COURSE_ABOUT_URL_PATTERN = re.compile(r'^/courses/{}/about'.format(settings.COURSE_ID_PATTERN))

    def process_request(self, request):

        course_key = None
        matches = self.COURSE_URL_PATTERN.match(request.path)
        about_matches = self.COURSE_ABOUT_URL_PATTERN.match(request.path)
        if matches:
            course_id = matches.group('course_id')
            if course_id:
                try:
                    course_key = CourseKey.from_string(course_id)
                except InvalidKeyError:
                    # do NOT raise HTTP404 here. should raise at each view if need be.
                    pass

            # If could not get course_key, nothing to do.
            if not course_key:
                return
            try:
                if about_matches:
                    permission = get_permission_for_course_about()
                    course = get_course_with_access(request.user, permission, course_key)
                else:
                    course = get_course_with_access(request.user, "load", course_key)
            except Http404:
                return
            if course.custom_logo:
                custom_logo_enabled = is_available(CUSTOM_LOGO_OPTION_KEY, course_key)
                request.custom_logo_enabled = custom_logo_enabled
                request.custom_logo_for_url = custom_logo_url(course)

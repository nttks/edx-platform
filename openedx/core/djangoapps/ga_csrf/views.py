"""
Views for ga_csrf
"""
from django.http import HttpResponseForbidden

from edxmako.shortcuts import render_to_response


def csrf_failure(request, reason=''):  # pylint: disable=unused-argument
    return HttpResponseForbidden(render_to_response('ga_csrf_failure.html'))

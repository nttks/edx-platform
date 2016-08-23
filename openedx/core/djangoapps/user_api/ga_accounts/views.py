"""
NOTE: this API is WIP and has not yet been approved. Do not use this API
without talking to Hiro.
"""
import re

from django.db import transaction

from rest_framework import permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response

from openedx.core.lib.api.authentication import SessionAuthenticationAllowInactiveUser

from ..errors import ReceiveEmailRequestError
from .api import (
    can_receive_email_global_course, optout_global_course, optin_global_course
)


class IsMatchedUsername(permissions.BasePermission):

    def has_permission(self, request, view):
        user = getattr(request._request, 'user', None)
        return user and re.search(r'/{}$'.format(user.username), request._request.path)


class ReceiveEmailView(APIView):
    """
        **Use Cases**

            Get or update the user's status to receive email.

        **Example Requests**

            GET /api/user/v1/receive_email/{username}

            PUT /api/user/v1/receive_email/{username}

            DELETE /api/user/v1/receive_email/{username}

        **Response Values for GET**

            If the user makes the request for her own account, an HTTP 200
            "OK" response is returned. The response contains a JSON dictionary
            with a key/value pair (of type String).

            * is_receive_email: The user's setting to receive email.
            * has_global_courses: The global course setting as enabled.

        **Response Values for PUT**

            If the update is successful, an HTTP 204 "No Content" response is
            returned with no additional content.

            The user's setting to optin email.

        **Response Values for DELETE**

            If the update is successful, an HTTP 204 "No Content" response is
            returned with no additional content.

            The user's setting to optout email.
    """
    authentication_classes = (SessionAuthenticationAllowInactiveUser,)
    permission_classes = (permissions.IsAuthenticated, IsMatchedUsername)

    def get(self, request, username):
        """
        GET /api/user/v1/receive_email/{username}
        """
        try:
            is_receive_email = can_receive_email_global_course(request.user)
            results = {
                'is_receive_email': is_receive_email,
                'has_global_courses': True,
            }
        except ReceiveEmailRequestError:
            results = {
                'is_receive_email': False,
                'has_global_courses': False,
            }

        return Response(results)

    def put(self, request, username):
        """
        PUT /api/user/v1/receive_email/{username}
        """
        if request.user.is_anonymous():
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        if request.user.username != username:
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            with transaction.atomic():
                optin_global_course(request.user)
        except ReceiveEmailRequestError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, username):
        """
        DELETE /api/user/v1/receive_email/{username}
        """
        if request.user.is_anonymous():
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        if request.user.username != username:
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            with transaction.atomic():
                optout_global_course(request.user)
        except ReceiveEmailRequestError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

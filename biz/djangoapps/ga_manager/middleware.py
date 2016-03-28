
from django.utils.functional import SimpleLazyObject

from biz.djangoapps.ga_manager.models import Manager


class BizAccessCheckMiddleware(object):
    """
    Middleware to check whether login user has the permissions to Biz.

    This middleware must be excecuted after the AuthenticationMiddleware
    """

    def process_request(self, request):
        user = getattr(request, 'user', None)

        # Anonymous user's id is None
        request.biz_accessible = SimpleLazyObject(
            lambda: bool(user and user.id and Manager.get_managers(user).exists())
        )

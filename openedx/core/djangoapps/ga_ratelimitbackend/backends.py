"""
A Custom classes for django-ratelimit-backend.
"""
import logging

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from ratelimitbackend.backends import RateLimitMixin as DjangoRateLimitMixin

from openedx.core.djangoapps.ga_ratelimitbackend.models import TrustedClient

log = logging.getLogger('ga_ratelimitbackend')


class RateLimitMixin(DjangoRateLimitMixin):
    """
    A mixin that is customized django-ratelimit-backend.
    """
    def __init__(self):
        self.minutes = getattr(settings, 'RATE_LIMIT_MINUTES', 5)
        self.requests = getattr(settings, 'RATE_LIMIT_REQUESTS', 30)

    def get_counters(self, request):
        """
        If IP is in the spoc client list, then always return 0.
        Otherwise call original `get_counters` method.
        """
        ip_address = request.META.get('REMOTE_ADDR', '<none>')
        if ip_address in TrustedClient.get_ip_address_list():
            log.debug("IP {} is in the SPOC client list.".format(ip_address))
            return {'': 0}
        else:
            return super(RateLimitMixin, self).get_counters(request)


class RateLimitModelBackend(RateLimitMixin, ModelBackend):
    pass

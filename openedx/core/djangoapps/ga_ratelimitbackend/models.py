"""
Models for rate limit backends.
"""
import logging

from cache_toolbox.app_settings import CACHE_TOOLBOX_DEFAULT_TIMEOUT
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_save, post_delete

log = logging.getLogger('ga_ratelimitbackend')

KEY_TRUSTED_CLIENT_LIST = 'ga_ratelimitbackend.trusted_client_list'


class TrustedClient(models.Model):
    """
    Model for trusted client information.
    """
    ip_address = models.GenericIPAddressField(db_index=True, unique=True)
    name = models.CharField(max_length=100, blank=True)

    def __unicode__(self):
        if self.name:
            return u"{ip_address} {name}".format(ip_address=self.ip_address, name=self.name)
        return self.ip_address

    @classmethod
    def _clear_cache(cls, sender, **kwargs):
        cache.delete(KEY_TRUSTED_CLIENT_LIST)

    @classmethod
    def get_ip_address_list(cls):
        """
        Returns the list of IP of trusted client.
        """
        client_list = cache.get(KEY_TRUSTED_CLIENT_LIST)

        if client_list is not None:
            return client_list

        log.info('Get the list of ip of trusted client from database because of cache expired or data updated.')
        client_list = [client.ip_address for client in TrustedClient.objects.all()]

        cache.set(KEY_TRUSTED_CLIENT_LIST, client_list, CACHE_TOOLBOX_DEFAULT_TIMEOUT)

        return client_list


post_save.connect(TrustedClient._clear_cache, sender=TrustedClient)
post_delete.connect(TrustedClient._clear_cache, sender=TrustedClient)

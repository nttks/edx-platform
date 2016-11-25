"""
API of ga_optional for XBlock.
"""
import logging

from opaque_keys.edx.keys import UsageKey
from xblock.reference.plugins import Service

from openedx.core.djangoapps.ga_optional import api

log = logging.getLogger(__name__)


class OptionalService(Service):

    def is_available(self, xblock, key):
        # XBlock should have location and it has been guaranteed to be instance of UsageKey
        # by mix-in the xmodule.x_module.XModuleMixin
        if hasattr(xblock, 'location') and isinstance(xblock.location, UsageKey):
            return api.is_available(key, course_key=xblock.location.course_key)
        else:
            log.warning("XBlock does not have valid location. {}".format(xblock))
            return False

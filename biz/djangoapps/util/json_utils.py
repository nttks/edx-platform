"""
JSON utilities
"""
import json

from django.utils.encoding import force_unicode
from django.utils.functional import Promise


class LazyEncoder(json.JSONEncoder):
    """Convert lazy translation to string"""

    def default(self, obj):
        if isinstance(obj, Promise):
            return force_unicode(obj)
        return super(LazyEncoder, self).default(obj)

"""
JSON utilities
"""
import json
import simplejson

from django.utils.encoding import force_unicode
from django.utils.functional import Promise

from xmodule.modulestore import EdxJSONEncoder


class EscapedEdxJSONEncoder(EdxJSONEncoder):
    """
    Class for encoding edx JSON which will be printed inline into HTML
    templates.
    """
    def encode(self, obj):
        """
        Encodes JSON that is safe to be embedded in HTML.
        """
        return simplejson.dumps(
            simplejson.loads(super(EscapedEdxJSONEncoder, self).encode(obj)),
            cls=simplejson.JSONEncoderForHTML
        )


class LazyEncoder(json.JSONEncoder):
    """Convert lazy translation to string"""

    def default(self, obj):
        if isinstance(obj, Promise):
            return force_unicode(obj)
        return super(LazyEncoder, self).default(obj)

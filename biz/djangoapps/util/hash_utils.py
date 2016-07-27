"""
Hash utilities
"""
from hashlib import sha256
import hmac

from django.conf import settings


def to_target_id(user_id):
    """
    Returns hashed value from user id.
    :param user_id: user id
    :return: hashed value
    """
    return hmac.new(settings.BIZ_SECRET_KEY.encode('utf-8'), str(user_id), sha256).hexdigest()

"""
Settings for Biz
"""
from lms.envs.common import MIDDLEWARE_CLASSES

"""
MongoDB
"""
BIZ_MONGO = {
    'score': {
        'host': 'localhost',
        'db': 'biz',
        'collection': 'score',
    }
}

"""
Middleware Classes
"""
MIDDLEWARE_CLASSES += (
    'biz.djangoapps.ga_manager.middleware.BizAccessCheckMiddleware',
    'biz.djangoapps.ga_invitation.middleware.SpocStatusMiddleware',
)

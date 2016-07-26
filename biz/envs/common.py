"""
Settings for Biz
"""
from lms.envs.common import MIDDLEWARE_CLASSES, CELERY_DEFAULT_QUEUE

"""
MongoDB
"""
BIZ_MONGO = {
    'score': {
        'host': ['localhost'],
        'db': 'biz',
        'collection': 'score',
    },
    'playback': {
        'host': ['localhost'],
        'db': 'biz',
        'collection': 'playback',
    }
}

"""
Middleware Classes
"""
MIDDLEWARE_CLASSES += (
    'biz.djangoapps.ga_manager.middleware.BizAccessCheckMiddleware',
    'biz.djangoapps.ga_invitation.middleware.SpocStatusMiddleware',
)

"""
Celery
"""
BIZ_CELERY_DEFAULT_QUEUE = CELERY_DEFAULT_QUEUE

"""
Monthly report info
"""
BIZ_FROM_EMAIL = 'support@nttks.jp'
BIZ_RECIPIENT_LIST = []

"""
Register student
"""
BIZ_MAX_REGISTER_NUMBER = 1000
BIZ_MAX_CHAR_LENGTH_REGISTER_LINE = 300

"""
Settings for Biz
"""
from lms.envs.common import MIDDLEWARE_CLASSES, CELERY_DEFAULT_QUEUE, INSTALLED_APPS

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
    },
    'playback_log': {
        'host': ['localhost'],
        'db': 'biz',
        'collection': 'playback_log',
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
Install Apps
"""
INSTALLED_APPS += (
    'biz.djangoapps.ga_achievement',
    'biz.djangoapps.ga_contract',
    'biz.djangoapps.ga_course_operation',
    'biz.djangoapps.ga_course_selection',
    'biz.djangoapps.ga_manager',
    'biz.djangoapps.ga_organization',
    'biz.djangoapps.ga_invitation',
    'biz.djangoapps.ga_contract_operation',
    'biz.djangoapps.ga_login',
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

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
    'biz.djangoapps.ga_contract_operation',
    'biz.djangoapps.ga_course_anslist',
    'biz.djangoapps.ga_course_operation',
    'biz.djangoapps.ga_course_selection',
    'biz.djangoapps.ga_invitation',
    'biz.djangoapps.ga_login',
    'biz.djangoapps.ga_manager',
    'biz.djangoapps.ga_organization',
    'biz.djangoapps.ga_student',
    'biz.djangoapps.gx_member',
    'biz.djangoapps.gx_org_group',
    'biz.djangoapps.gx_username_rule',
    'biz.djangoapps.gx_sso_config',
    'biz.djangoapps.gx_login',
    'biz.djangoapps.gx_register_api',
    'biz.djangoapps.gx_reservation_mail',
    'biz.djangoapps.gx_save_register_condition',
    'biz.djangoapps.gx_students_register_batch',
)

"""
Batch Settings
"""
MAX_RETRY_REMOVE_DOCUMENTS = 5
SLEEP_RETRY_REMOVE_DOCUMENTS = 1
MAX_RETRY_SET_DOCUMENTS = 10
SLEEP_RETRY_SET_DOCUMENTS = 3
AGGREGATE_FETCH_LIMIT = 50000

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
BIZ_MAX_REGISTER_NUMBER = 10000
BIZ_MAX_CHAR_LENGTH_REGISTER_LINE = 300

"""
Bulk student Management
"""
BIZ_MAX_BULK_STUDENTS_NUMBER = 10000
BIZ_MAX_CHAR_LENGTH_BULK_STUDENTS_LINE = 30

"""
Additional info
"""
BIZ_MAX_REGISTER_ADDITIONAL_INFO = 10
BIZ_MAX_CHAR_LENGTH_REGISTER_ADD_INFO_LINE = 3000

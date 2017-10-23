"""
Settings for Biz
"""
import tempfile


"""
Basic settings
"""
# Dummy biz secret key for dev/test
BIZ_SECRET_KEY = 'test'
BIZ_MONGO_LIMIT_RECORDS = 0

"""
Batch Settings
"""
BIZ_SET_SCORE_COMMAND_OUTPUT = tempfile.NamedTemporaryFile().name
BIZ_SET_SHOW_ENABLED_CONTRACT_COMMAND_OUTPUT = tempfile.NamedTemporaryFile().name
BIZ_SET_PLAYBACK_COMMAND_OUTPUT = tempfile.NamedTemporaryFile().name
BIZ_SEND_SUBMISSION_REMINDER_COMMAND_OUTPUT = tempfile.NamedTemporaryFile().name

"""
Monthly report info
"""
BIZ_MONTHLY_REPORT_COMMAND_OUTPUT = tempfile.NamedTemporaryFile().name
BIZ_FROM_EMAIL = 'from@test.com'
BIZ_RECIPIENT_LIST = ['recipient@test.com']

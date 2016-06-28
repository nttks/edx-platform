"""
Settings for Biz
"""
import tempfile


"""
Set score Batch Settings
"""
BIZ_SET_SCORE_COMMAND_OUTPUT = tempfile.NamedTemporaryFile().name

"""
Monthly report info
"""
BIZ_MONTHLY_REPORT_COMMAND_OUTPUT = tempfile.NamedTemporaryFile().name
BIZ_FROM_EMAIL = 'from@test.com'
BIZ_RECIPIENT_LIST = ['recipient@test.com']

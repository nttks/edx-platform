"""
Settings for Biz
"""
from lms.envs.aws import AUTH_TOKENS, ENV_TOKENS
from lms.envs.common import BIZ_MONGO


"""
MongoDB
"""
BIZ_MONGO = AUTH_TOKENS.get('BIZ_MONGO', BIZ_MONGO)

"""
Set score Batch Settings
"""
BIZ_SET_SCORE_COMMAND_OUTPUT = ENV_TOKENS.get('BIZ_SET_SCORE_COMMAND_OUTPUT')

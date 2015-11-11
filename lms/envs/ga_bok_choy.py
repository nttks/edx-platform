"""
Settings for Bok Choy tests that are used by gacco.
"""
import json
import os
from path import Path as path

_DIR_ROOT = PROJECT_ROOT = path(__file__).abspath().dirname()

# commo.py
OAUTH_OIDC_ISSUER = 'https:/example.com/oauth2'
EDXMKTG_LOGGED_IN_COOKIE_NAME = 'edxloggedin'
PLATFORM_NAME = "Your Platform Name Here"
PASSWORD_COMPLEXITY = {"UPPER": 1, "LOWER": 1, "DIGITS": 1}
PASSWORD_DICTIONARY = []
PASSWORD_MIN_LENGTH = 8

FEATURES = {
    'ENABLE_OAUTH2_PROVIDER': False,
}

# aws.py
with open(_DIR_ROOT / "bok_choy.env.json") as env_file:
    ENV_TOKENS = json.load(env_file)

ENV_FEATURES = ENV_TOKENS.get('FEATURES', {})
for feature, value in ENV_FEATURES.items():
    FEATURES[feature] = value

EMAIL_FILE_PATH = ENV_TOKENS.get('EMAIL_FILE_PATH', None)

if FEATURES.get('ENABLE_OAUTH2_PROVIDER'):
    OAUTH_OIDC_ISSUER = ENV_TOKENS['OAUTH_OIDC_ISSUER']

EDXMKTG_LOGGED_IN_COOKIE_NAME = ENV_TOKENS.get('EDXMKTG_LOGGED_IN_COOKIE_NAME', EDXMKTG_LOGGED_IN_COOKIE_NAME)
PLATFORM_NAME = ENV_TOKENS.get('PLATFORM_NAME', PLATFORM_NAME)
PASSWORD_COMPLEXITY = ENV_TOKENS.get("PASSWORD_COMPLEXITY", {})
PASSWORD_DICTIONARY = ENV_TOKENS.get("PASSWORD_DICTIONARY", [])
PASSWORD_MIN_LENGTH = ENV_TOKENS.get("PASSWORD_MIN_LENGTH")

# bok_choy.py
if os.environ.get('ENABLE_BOKCHOY_GA'):

    EMAIL_FILE_PATH = 'test_root/bokchoy_email'

    # Password policy
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_COMPLEXITY = {"UPPER": 1, "LOWER": 1, "DIGITS": 1}
    PASSWORD_DICTIONARY = ["Password1"]

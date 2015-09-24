"""Unit tests for third_party_auth/pipeline.py."""

import random
import string

from third_party_auth import pipeline, provider
from third_party_auth.tests import testutil
import unittest


# Allow tests access to protected methods (or module-protected methods) under
# test. pylint: disable-msg=protected-access


class MakeRandomPasswordTest(testutil.TestCase):
    """Tests formation of random placeholder passwords."""

    def setUp(self):
        super(MakeRandomPasswordTest, self).setUp()
        self.seed = 1

    def test_default_args(self):
        self.assertEqual(pipeline._DEFAULT_RANDOM_PASSWORD_LENGTH, len(pipeline.make_random_password()))

    def test_password_length(self):
        # divisible by 3
        self.assertEqual(9, len(pipeline.make_random_password(length=9)))
        # not divisible by 3
        self.assertEqual(10, len(pipeline.make_random_password(length=10)))
        self.assertEqual(11, len(pipeline.make_random_password(length=11)))

    def test_probably_only_uses_charset(self):
        # This is ultimately probablistic since we could randomly select a good character 100000 consecutive times.
        _PASSWORD_CHARSET = string.ascii_lowercase + string.ascii_uppercase + string.digits
        for char in pipeline.make_random_password(length=100000):
            self.assertIn(char, _PASSWORD_CHARSET)

    def test_pseudorandomly_picks_chars_from_charset(self):
        random_instance = random.Random(self.seed)
        expected = ''.join(
            random_instance.choice(string.ascii_lowercase)
            for _ in xrange(pipeline._DEFAULT_RANDOM_PASSWORD_LENGTH / 3))
        expected += ''.join(
            random_instance.choice(string.ascii_uppercase)
            for _ in xrange(pipeline._DEFAULT_RANDOM_PASSWORD_LENGTH / 3))
        expected += ''.join(
            random_instance.choice(string.digits)
            for _ in xrange(pipeline._DEFAULT_RANDOM_PASSWORD_LENGTH / 3 + pipeline._DEFAULT_RANDOM_PASSWORD_LENGTH % 3))
        random_instance.seed(self.seed)
        self.assertEqual(sorted(expected), sorted(pipeline.make_random_password(choice_fn=random_instance.choice)))

    def test_include_valid_character_type(self):
        # Try a sufficiently large number of times.
        for i in range(10000):
            password = pipeline.make_random_password()
            self.assertRegexpMatches(password, r'[a-z]')
            self.assertRegexpMatches(password, r'[A-Z]')
            self.assertRegexpMatches(password, r'[0-9]')


@unittest.skipUnless(testutil.AUTH_FEATURE_ENABLED, 'third_party_auth not enabled')
class ProviderUserStateTestCase(testutil.TestCase):
    """Tests ProviderUserState behavior."""

    def test_get_unlink_form_name(self):
        google_provider = self.configure_google_provider(enabled=True)
        state = pipeline.ProviderUserState(google_provider, object(), 1000)
        self.assertEqual(google_provider.provider_id + '_unlink_form', state.get_unlink_form_name())

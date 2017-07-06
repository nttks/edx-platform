from django.test import TestCase

from ..models import UserOptionalConfiguration, USERPOFILE_OPTION_KEY

from student.tests.factories import UserFactory


class UserOptionalConfigurationModelsTest(TestCase):

    def setUp(self):
        super(UserOptionalConfigurationModelsTest, self).setUp()

        self.user = UserFactory()

    def _save_configuration(self, user, enabled=True):
        UserOptionalConfiguration(key=USERPOFILE_OPTION_KEY, user=user, enabled=enabled).save()

    def test_is_available(self):
        # record is None
        self.assertFalse(UserOptionalConfiguration.is_available(USERPOFILE_OPTION_KEY, self.user))
        # user is none
        self.assertFalse(UserOptionalConfiguration.is_available(USERPOFILE_OPTION_KEY))

        self._save_configuration(self.user, enabled=False)

        # record is not None and return False
        self.assertFalse(UserOptionalConfiguration.is_available(USERPOFILE_OPTION_KEY, self.user))

        # record is not None and return True
        self._save_configuration(self.user)
        self.assertTrue(UserOptionalConfiguration.is_available(USERPOFILE_OPTION_KEY, self.user))

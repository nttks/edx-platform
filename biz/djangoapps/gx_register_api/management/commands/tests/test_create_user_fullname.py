"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth.models import User


class TestArgParsing(TestCase):
    def setUp(self):
        super(TestCase, self).setUp()

    def test_command_non_arguments(self):
        with self.assertRaises(CommandError) as ce:
            call_command('create_user_fullname')
        raise_except = ce.exception
        self.assertEqual(raise_except.args[0], "Error: argument -u is required")

    def test_command_success(self):
        self.assertEqual(User.objects.count(), 0)
        call_command('create_user_fullname', '-u "guest_user"', '-p "pass"', '-e "guest@example.com"',
                     '-f "first"', '-l "last"')
        self.assertEqual(User.objects.count(), 1)

    def test_command_duplication_error(self):
        call_command('create_user_fullname', '-u "guest_user"', '-p "Password1234"', '-e "guest@example.com"',
                     '-f "first"', '-l "last"')
        with self.assertRaises(ValueError) as ce:
            call_command('create_user_fullname', '-u "guest_user"', '-p "Password1234"', '-e "guest2@example.com"',
                         '-f "first2"', '-l "last2"')
        raise_except = ce.exception
        self.assertEqual(raise_except.args[0], "User already exists")

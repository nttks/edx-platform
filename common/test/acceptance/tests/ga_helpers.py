# -*- coding: utf-8 -*-
"""
Test helper functions and base classes.
"""
import os
import os.path
import re
import subprocess
import time
import unittest
from contextlib import contextmanager
from itertools import chain

from email import message_from_string
from email.header import decode_header

from ..pages.common.logout import LogoutPage
from ..pages.lms.auto_auth import AutoAuthPage
from ..pages.lms.ga_django_admin import DjangoAdminPage


SUPER_USER_INFO = {
    'username': 'superuser',
    'password': 'SuperUser3',
    'email': 'superuser@example.com',
}


@unittest.skipUnless(os.environ.get('ENABLE_BOKCHOY_GA'), "Test only valid in gacco")
class GaccoTestMixin(object):
    """
    Mixin for gacco tests
    """

    WINDOW_WIDTH_PC = 1280
    WINDOW_HEIGHT_PC = 800

    RESIGN_CONFIRM_MAIL_SUBJECT = 'How to resign from edX website'
    RESIGN_CONFIRM_MAIL_URL_PATTERN = r'/resign_confirm/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/'

    def setup_email_client(self, email_file_path):
        """
        Set up an email client
        """
        self.email_client = FilebasedEmailClient(email_file_path)
        self.email_client.clear_messages()
        self.addCleanup(self.email_client.clear_messages)

    def setup_window_size_for_pc(self):
        """
        Set up window size for PC
        """
        self.browser.set_window_size(self.WINDOW_WIDTH_PC, self.WINDOW_HEIGHT_PC)

    def assert_email_resign(self):
        """
        Assert email of resign.
        - return uidb36 and token in email body.
        """
        email_message = self.email_client.get_latest_message()
        self.assertEqual(email_message['subject'], self.RESIGN_CONFIRM_MAIL_SUBJECT)
        matches = re.search(self.RESIGN_CONFIRM_MAIL_URL_PATTERN, email_message['body'], re.MULTILINE)
        self.assertIsNotNone(matches)
        return (matches.groupdict()['uidb36'], matches.groupdict()['token'])

    def restart_memcached(self):
        """
        Restart memcached for clear of selected-info on biz.
        """
        self.assertEqual(0, subprocess.call(['sudo', 'service', 'memcached', 'restart']))

    def switch_to_user(self, user_info, course_id=None):
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=user_info['username'],
            password=user_info['password'],
            email=user_info['email'],
            course_id=course_id
        ).visit()
        return user_info

    @contextmanager
    def setup_global_course(self, course_id):

        global_course_enabled_name = "Course '{}': Global Enabled".format(course_id)

        # Create course global setting.
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_list_page = DjangoAdminPage(self.browser).visit().click_add('course_global', 'courseglobalsetting').input({
            'course_id': course_id,
        }).save()

        grid_row = django_admin_list_page.get_row({
            'Course global setting': global_course_enabled_name
        })
        self.assertIsNotNone(grid_row)

        # Logout
        LogoutPage(self.browser).visit()

        yield

        # Remove course global setting.
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_list_page = DjangoAdminPage(self.browser).visit().click_list('course_global', 'courseglobalsetting')
        django_admin_list_page = django_admin_list_page.click_grid_anchor(grid_row).click_delete().click_yes()

        grid_row = django_admin_list_page.get_row({
            'Course global setting': global_course_enabled_name
        })
        self.assertIsNone(grid_row)

        # Logout
        LogoutPage(self.browser).visit()


class FilebasedEmailClient(object):

    WAIT_TIMEOUT = 10
    WAIT_INTERVAL = 2

    def __init__(self, email_file_path):
        self.email_file_path = email_file_path

    def _get_files(self):
        if os.path.exists(self.email_file_path):
            files = [os.path.join(self.email_file_path, file_name) for file_name in os.listdir(self.email_file_path)]
            return files
        else:
            return []

    def _count_messages(self):
        files = self._get_files()
        return len(files)

    def _wait_for_messages(self):
        timeout = time.time() + self.WAIT_TIMEOUT
        while True:
            if self._count_messages() > 0:
                return True
            elif time.time() > timeout:
                raise Exception("Timeout. No email file was found at %s." % self.email_file_path)
            time.sleep(self.WAIT_TIMEOUT)

    def _get_messages_from_file(self, file):
        with open(file, 'r') as f:
            return [message.strip() for message in f.read().split('-' * 79) if message.strip() != '']

    def _parse_message(self, message):
        """
        Parse content of the file
        """
        msg = message_from_string(message)
        encoding = decode_header(msg.get('Subject'))[0][1] or 'utf-8'
        subject = decode_header(msg.get('Subject'))[0][0].decode(encoding)
        body = msg.get_payload()
        return {
            'from_address': msg.get('From'),
            'to_addresses': msg.get('To'),
            'date': msg.get('Date'),
            'subject': subject,
            'body': body
        }

    def get_messages(self):
        """
        Get all messages
        """
        # Wait until email file appears
        self._wait_for_messages()
        files = self._get_files()
        messages = list(chain.from_iterable([self._get_messages_from_file(file) for file in files]))
        return [self._parse_message(message) for message in messages]

    def get_latest_message(self):
        """
        Get the latest email message
        """
        # Wait until email file appears
        self._wait_for_messages()
        files = self._get_files()
        # Sort in the chronological order, most recent first
        files.sort(key=os.path.getmtime, reverse=True)
        # Get latest message in the file
        messages = self._get_messages_from_file(files[0])
        message = messages[-1]
        return self._parse_message(message)

    def clear_messages(self):
        """
        Remove all email files under `email_file_path`
        """
        files = self._get_files()
        for file in files:
            os.remove(file)

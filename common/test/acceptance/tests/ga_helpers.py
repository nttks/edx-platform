"""
Test helper functions and base classes.
"""
import os
import os.path
import time

from email import message_from_string
from email.header import decode_header


class EmailTestMixin(object):
    """
    Mixin for tests using emails
    """
    def setup_email_client(self, email_file_path):
        """
        Set up an email client
        """
        self.email_client = FilebasedEmailClient(email_file_path)
        self.email_client.clear_messages()
        self.addCleanup(self.email_client.clear_messages)


class FilebasedEmailClient(object):

    WAIT_TIMEOUT = 10
    WAIT_INTERVAL = 2

    def __init__(self, email_file_path):
        self.email_file_path = email_file_path

    def _get_files(self):
        files = [os.path.join(self.email_file_path, file_name) for file_name in os.listdir(self.email_file_path)]
        return files

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

    def get_latest_message(self):
        """
        Get the latest email message
        """
        # Wait until email file appears
        self._wait_for_messages()
        files = self._get_files()
        # Sort in the chronological order, most recent first
        files.sort(key=os.path.getmtime, reverse=True)
        file = files[0]
        # Parse content of the file
        with open(file, 'r') as f:
            msg = message_from_string(f.read())
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

    def clear_messages(self):
        """
        Remove all email files under `email_file_path`
        """
        files = self._get_files()
        for file in files:
          os.remove(file)

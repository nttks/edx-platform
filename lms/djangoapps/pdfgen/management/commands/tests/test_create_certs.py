from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from mock import patch, MagicMock
from StringIO import StringIO
from pdfgen.management.commands import create_certs as cc


def call_management_command(name, *args, **kwargs):
    """Call management command and return output"""
    out = StringIO()  # To Capture the output of the command
    call_command(name, *args, stdout=out, **kwargs)
    out.seek(0)
    return out.read()


class GenerateCertCommandTestCase(TestCase):

    def setUp(self):
        self.args = ["org/num/run"]
        self.create_kwargs = {"noop": False, "username": "testuser",
            "debug": True, "method": "create"}
        self.delete_kwargs = {"noop": False, "username": "testuser",
            "debug": True, "method": "delete"}
        self.report_kwargs = {"noop": False, "username": "testuser",
            "debug": True, "method": "report"}
        self.invalid_kwargs = {"noop": False, "username": "testuser",
            "debug": True, "method": "unknown"}

        self.username = "testuser"
        self.mail = "testuser@example.com"
        self.seed = "seed"

        patcher0 = patch(
            'pdfgen.management.commands.create_certs.CertificatePDF')
        self.certmock = patcher0.start()
        self.addCleanup(patcher0.stop)

    def tearDown(self):
        pass

    def test_handle_create(self):
        cc.Command().handle(*self.args, **self.create_kwargs)
        self.certmock.assert_called_once_with(
            'testuser', 'org/num/run', True, False)

    def test_handle_delete(self):
        cc.Command().handle(*self.args, **self.delete_kwargs)
        self.certmock.assert_called_once_with(
            'testuser', 'org/num/run', True, False)

    def test_handle_report(self):
        cc.Command().handle(*self.args, **self.report_kwargs)
        self.certmock.assert_called_once_with(
            'testuser', 'org/num/run', True, False)

    def test_handle_invalid_method(self):
        with self.assertRaises(CommandError):
            cc.Command().handle(*self.args, **self.invalid_kwargs)

    def test_handle_not_course_id(self):
        with self.assertRaises(CommandError):
            cc.Command().handle(*[], **self.invalid_kwargs)

    def test_handle_invalid_kwargs(self):
        with self.assertRaises(KeyError):
            cc.Command().handle(*self.args, **{"unknown": "unknown"})

# -*- coding: utf-8 -*-

"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".
"""
import logging
import tempfile
from StringIO import StringIO
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.crypto import get_random_string
from mock import patch

from biz.djangoapps.ga_achievement.management.commands import show_enabled_contract
from biz.djangoapps.ga_contract.tests.factories import ContractFactory
from biz.djangoapps.util.datetime_utils import timezone_today
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from student.tests.factories import UserFactory

command_output_file = tempfile.NamedTemporaryFile()


class TestArgParsing(TestCase):
    """
    Tests for parsing arguments of the `show_enabled_contract` command
    """
    def setUp(self):
        super(TestArgParsing, self).setUp()
        self.command = show_enabled_contract.Command()

    def test_args_debug(self):
        self.command.execute(debug=True)
        self.assertEquals(show_enabled_contract.log.level, logging.DEBUG)

    def test_excludes_as_empty_string(self):
        with patch('django.db.models.query.QuerySet.exclude', return_value='[]') as mock_exclude:
            self.command.execute(excludes='')
            mock_exclude.assert_called_once_with(id__in=[])

    def test_excludes_as_integer(self):
        with patch('django.db.models.query.QuerySet.exclude', return_value='[]') as mock_exclude:
            self.command.execute(excludes='1')
            mock_exclude.assert_called_once_with(id__in=[1])

    def test_excludes_as_comma_delimited_integers(self):
        with patch('django.db.models.query.QuerySet.exclude', return_value='[]') as mock_exclude:
            self.command.execute(excludes='1,2')
            mock_exclude.assert_called_once_with(id__in=[1, 2])

    def test_invalid_excludes(self):
        errstring = "excludes should be specified as comma-delimited integers \(like 1 or 1,2\)."
        with self.assertRaisesRegexp(CommandError, errstring):
            self.command.handle._original(self.command, excludes='a')


@override_settings(BIZ_SET_SHOW_ENABLED_CONTRACT_COMMAND_OUTPUT=command_output_file.name)
class ShowEnabledContractTest(BizStoreTestBase):

    def setUp(self):
        super(ShowEnabledContractTest, self).setUp()
        self.command = show_enabled_contract.Command()

        self.twodaysago = timezone_today() - timedelta(days=2)
        self.yesterday = timezone_today() - timedelta(days=1)
        self.today = timezone_today()
        self.tomorrow = timezone_today() + timedelta(days=1)

    def test_contract(self):
        for _ in range(4):
            self._create_contract()

        out = StringIO()
        call_command('show_enabled_contract', stdout=out)
        self.assertEquals("ContractID 1,2,3,4", out.getvalue().rstrip())

    def test_contract_with_excludes(self):
        for _ in range(4):
            self._create_contract()

        out = StringIO()
        call_command('show_enabled_contract', excludes='2', stdout=out)
        self.assertEquals("ContractID 1,3,4", out.getvalue().rstrip())

    def test_contract_with_multiple_excludes(self):
        for _ in range(4):
            self._create_contract()

        out = StringIO()
        call_command('show_enabled_contract', excludes='2,3', stdout=out)
        self.assertEquals("ContractID 1,4", out.getvalue().rstrip())

    def test_contract_from_two_days_ago_to_yesterday(self):
        self._create_contract_with_dates(self.twodaysago, self.yesterday)  # contract 1

        out = StringIO()
        call_command('show_enabled_contract', stdout=out)
        self.assertEquals("ContractID 1", out.getvalue().rstrip())

    def test_contract_from_yesterday_to_today(self):
        self._create_contract_with_dates(self.yesterday, self.today)  # contract 1

        out = StringIO()
        call_command('show_enabled_contract', stdout=out)
        self.assertEquals("ContractID 1", out.getvalue().rstrip())

    def test_contract_from_today_to_tomorrow(self):
        self._create_contract_with_dates(self.today, self.tomorrow)  # contract 1

        out = StringIO()
        call_command('show_enabled_contract', stdout=out)
        self.assertEquals("ContractID", out.getvalue().rstrip())

    def test_three_contracts_from_two_days_ago_to_tomorrow(self):
        self._create_contract_with_dates(self.twodaysago, self.yesterday)  # contract 1
        self._create_contract_with_dates(self.yesterday, self.today)  # contract 2
        self._create_contract_with_dates(self.today, self.tomorrow)  # contract 3

        out = StringIO()
        call_command('show_enabled_contract', stdout=out)
        self.assertEquals("ContractID 1,2", out.getvalue().rstrip())

    def _create_contract_with_dates(self, start_date, end_date):
        contract = ContractFactory.create(
            contract_name=get_random_string(8),
            contract_type='PF',
            register_type='ERS',
            contractor_organization=self._create_organization(),
            owner_organization=self.gacco_organization,
            created_by=UserFactory.create(),
            start_date=start_date,
            end_date=end_date,
        )
        return contract

# -*- coding: utf-8 -*-
"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import ddt
from django.db import connection
from mock import patch
from pytz import utc

from django.core.management import call_command
from django.test.utils import override_settings
from django.utils import timezone

from biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user import (
    _create_report_data,
    _render_message,
    _target_date,
)
from biz.djangoapps.ga_invitation.models import ContractRegister, ContractRegisterHistory
from biz.djangoapps.util.datetime_utils import timezone_today, timezone_now
from biz.djangoapps.util.tests.testcase import BizTestBase
from lms.djangoapps.courseware.tests.helpers import LoginEnrollmentTestCase
from student.models import UserStanding
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


@ddt.ddt
class MonthlyReportBizRegisterUser(BizTestBase, ModuleStoreTestCase, LoginEnrollmentTestCase):

    def setUp(self):
        super(MonthlyReportBizRegisterUser, self).setUp()
        self.today = timezone_today()
        self.last_day_of_last_month_utc = datetime(self.today.year, self.today.month, 1, tzinfo=utc) - timedelta(days=1)
        self.first_day_of_this_month_jst_00 = datetime(self.today.year, self.today.month, 1, 0, 0, 0, tzinfo=timezone.get_default_timezone()).astimezone(utc)
        self.last_day_of_last_month_jst_59 = self.first_day_of_this_month_jst_00 - timedelta(seconds=1)

    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user._create_report_data', return_value=([], []))
    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user._render_message', return_value=('', ''))
    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user.send_mail')
    @patch('biz.djangoapps.util.decorators.log.info')
    @patch('biz.djangoapps.util.decorators.log.error')
    def test_call_command_without_args(self, fn_log_error, fn_log_info, fn_senf_mail, fn_render_message, fn_create_report_data):
        call_command('monthly_report_biz_register_user')

        fn_render_message.assert_called_once_with(self.today.year, self.today.month, [], [])
        fn_senf_mail.assert_called_once_with('', '', 'from@test.com', ['recipient@test.com'])
        self.assertEquals(fn_log_info.call_count, 2)
        self.assertEquals(fn_log_error.call_count, 0)

    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user._create_report_data', return_value=([], []))
    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user._render_message', return_value=('', ''))
    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user.send_mail')
    @patch('biz.djangoapps.util.decorators.log.info')
    @patch('biz.djangoapps.util.decorators.log.error')
    def test_call_command_with_args(self, fn_log_error, fn_log_info, fn_senf_mail, fn_render_message, fn_create_report_data):
        call_command('monthly_report_biz_register_user', '2016', '07')

        fn_render_message.assert_called_once_with(2016, 7, [], [])
        fn_senf_mail.assert_called_once_with('', '', 'from@test.com', ['recipient@test.com'])
        self.assertEquals(fn_log_info.call_count, 2)
        self.assertEquals(fn_log_error.call_count, 0)

    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user._create_report_data', return_value=([], []))
    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user._render_message', return_value=('', ''))
    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user.send_mail')
    @patch('biz.djangoapps.util.decorators.log.info')
    @patch('biz.djangoapps.util.decorators.log.error')
    @ddt.data(
        ('2016',),
        ('2016', '13'),
        ('A', '13'),
        ('2016', 'B'),
        ('2016', '07', '17'),
    )
    def test_call_command_with_illegal_args(self, cmd_args, fn_log_error, fn_log_info, fn_senf_mail, fn_render_message, fn_create_report_data):
        call_command('monthly_report_biz_register_user', *cmd_args)

        self.assertEquals(fn_create_report_data.call_count, 0)
        self.assertEquals(fn_render_message.call_count, 0)
        self.assertEquals(fn_senf_mail.call_count, 0)
        self.assertEquals(fn_log_info.call_count, 1)
        self.assertEquals(fn_log_error.call_count, 1)

    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user._create_report_data', return_value=([], []))
    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user._render_message', return_value=('', ''))
    @patch('biz.djangoapps.ga_contract_operation.management.commands.monthly_report_biz_register_user.send_mail')
    @patch('biz.djangoapps.util.decorators.log.info')
    @patch('biz.djangoapps.util.decorators.log.error')
    @ddt.unpack
    @ddt.data(
        (None, ['recipient@test.com']),
        ('', ['recipient@test.com']),
        ('from@test.com', None),
        ('from@test.com', []),
    )
    def test_call_command_illegal_settings(self, from_email, recipient_list, fn_log_error, fn_log_info, fn_senf_mail, fn_render_message, fn_create_report_data):
        with override_settings(
            BIZ_FROM_EMAIL=from_email,
            BIZ_RECIPIENT_LIST=recipient_list,
        ):
            call_command('monthly_report_biz_register_user')

        self.assertEquals(fn_create_report_data.call_count, 0)
        self.assertEquals(fn_render_message.call_count, 0)
        self.assertEquals(fn_senf_mail.call_count, 0)
        self.assertEquals(fn_log_info.call_count, 1)
        self.assertEquals(fn_log_error.call_count, 1)

    def assert_create_report_data(self, pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        self.assertEqual(len(pfgs_contract_list), assert_len_pfgs)
        self.assertEqual(len(os_contract_list), assert_len_os)

        if assert_len_register_pfgs is not None:
            self.assertEqual(len(pfgs_contract_list[0].contract_register_list), assert_len_register_pfgs)
        if assert_len_register_os is not None:
            self.assertEqual(len(os_contract_list[0].contract_register_list), assert_len_register_os)

    def _mod_register_history_modified(self, contract, user, modified):
        history = ContractRegisterHistory.objects.get(contract=contract, user=user)
        history.modified = modified
        history.save()

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 0, None),
        ('GS', 1, 0, 0, None),
        ('OS', 0, 1, None, 0),
        ('O', 0, 0, None, None),
    )
    def _test_create_report_data_unregister(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._unregister_contract(contract, self.user)
        self._mod_register_history_modified(contract, self.user, self.first_day_of_this_month_jst_00)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 1, None),
        ('GS', 1, 0, 1, None),
        ('OS', 0, 1, None, 1),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_input(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._input_contract(contract, self.user)
        self._mod_register_history_modified(contract, self.user, self.first_day_of_this_month_jst_00)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 1, None),
        ('GS', 1, 0, 1, None),
        ('OS', 0, 1, None, 1),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_register(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._register_contract(contract, self.user)
        self._mod_register_history_modified(contract, self.user, self.first_day_of_this_month_jst_00)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 1, None),
        ('GS', 1, 0, 1, None),
        ('OS', 0, 1, None, 1),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_unregister(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._unregister_contract(contract, self.user)
        self._mod_register_history_modified(contract, self.user, self.first_day_of_this_month_jst_00)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 1, None),
        ('GS', 1, 0, 1, None),
        ('OS', 0, 1, None, 1),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_input_last_month(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._input_contract(contract, self.user)
        self._mod_register_history_modified(contract, self.user, self.last_day_of_last_month_jst_59)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 1, None),
        ('GS', 1, 0, 1, None),
        ('OS', 0, 1, None, 1),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_register_last_month(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._register_contract(contract, self.user)
        self._mod_register_history_modified(contract, self.user, self.last_day_of_last_month_jst_59)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 0, None),
        ('GS', 1, 0, 0, None),
        ('OS', 0, 1, None, 0),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_unregister_last_month(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._unregister_contract(contract, self.user)
        self._mod_register_history_modified(contract, self.user, self.last_day_of_last_month_jst_59)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 0, 0, None, None),
        ('GS', 0, 0, None, None),
        ('OS', 0, 0, None, None),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_input_contract_ended(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type, end_date=self.last_day_of_last_month_utc)
        self._input_contract(contract, self.user)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 0, 0, None, None),
        ('GS', 0, 0, None, None),
        ('OS', 0, 0, None, None),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_register_contract_ended(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type, end_date=self.last_day_of_last_month_utc)
        self._register_contract(contract, self.user)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 0, 0, None, None),
        ('GS', 0, 0, None, None),
        ('OS', 0, 0, None, None),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_unregister_contract_ended(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type, end_date=self.last_day_of_last_month_utc)
        self._unregister_contract(contract, self.user)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    def _mod_userstanding_last_changed_at(self, user, modified):
        connection.cursor().execute('''
            UPDATE student_userstanding SET standing_last_changed_at = %s WHERE user_id = %s
        ''', [modified.strftime('%Y-%m-%d %H:%M:%S'), str(user.id)])

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 1, None),
        ('GS', 1, 0, 1, None),
        ('OS', 0, 1, None, 1),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_input_userstanding(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._input_contract(contract, self.user)
        self._account_disable(self.user)
        self._mod_userstanding_last_changed_at(self.user, self.first_day_of_this_month_jst_00)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 1, None),
        ('GS', 1, 0, 1, None),
        ('OS', 0, 1, None, 1),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_register_userstanding(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._register_contract(contract, self.user)
        self._account_disable(self.user)
        self._mod_userstanding_last_changed_at(self.user, self.first_day_of_this_month_jst_00)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 1, None),
        ('GS', 1, 0, 1, None),
        ('OS', 0, 1, None, 1),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_unregister_userstanding(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._unregister_contract(contract, self.user)
        self._account_disable(self.user)
        self._mod_userstanding_last_changed_at(self.user, self.first_day_of_this_month_jst_00)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 0, None),
        ('GS', 1, 0, 0, None),
        ('OS', 0, 1, None, 0),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_input_userstanding_last_month(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._input_contract(contract, self.user)
        self._account_disable(self.user)
        self._mod_userstanding_last_changed_at(self.user, self.last_day_of_last_month_jst_59)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    def ddd(self, contract, user, target_date, last_target_date, last_day_of_last_month):
        rrr = ContractRegisterHistory.objects.get(contract=contract, user=user)
        sss = UserStanding.objects.get(user=user)
        print('{}'.format(target_date))
        print('{}'.format(last_target_date))
        print('{}'.format(last_day_of_last_month))
        print('{}'.format(rrr.modified))
        print('{}'.format(sss.standing_last_changed_at))

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 0, None),
        ('GS', 1, 0, 0, None),
        ('OS', 0, 1, None, 0),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_register_userstanding_last_month(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._register_contract(contract, self.user)
        self._account_disable(self.user)
        self._mod_userstanding_last_changed_at(self.user, self.last_day_of_last_month_jst_59)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    @ddt.unpack
    @ddt.data(
        ('PF', 1, 0, 0, None),
        ('GS', 1, 0, 0, None),
        ('OS', 0, 1, None, 0),
        ('O', 0, 0, None, None),
    )
    def test_create_report_data_unregister_userstanding_last_month(self, contract_type, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os):
        contract = self._create_contract(contract_type=contract_type)
        self._unregister_contract(contract, self.user)
        self._account_disable(self.user)
        self._mod_userstanding_last_changed_at(self.user, self.last_day_of_last_month_jst_59)

        _, _, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)

        self.assert_create_report_data(pfgs_contract_list, os_contract_list, assert_len_pfgs, assert_len_os, assert_len_register_pfgs, assert_len_register_os)

    def test_render_message(self):
        self._create_contract(contract_type='PF')
        self._create_contract(contract_type='GS')
        self._create_contract(contract_type='OS')

        year, month, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)
        subject, message = _render_message(year, month, pfgs_contract_list, os_contract_list)

        self.assertIn(str(self.today.year), subject)
        self.assertIn(str(self.today.month), subject)

        self.assertNotIn(u'有効なプラットフォーム契約（gaccoサービス契約）が存在しません。', message)
        self.assertNotIn(u'有効なオーナーサービス契約が存在しません。', message)

    def test_render_message_no_contract(self):
        year, month, target_date, last_target_date = _target_date(self.today.year, self.today.month)
        pfgs_contract_list, os_contract_list = _create_report_data(target_date, last_target_date)
        subject, message = _render_message(year, month, pfgs_contract_list, os_contract_list)

        self.assertIn(str(self.today.year), subject)
        self.assertIn(str(self.today.month), subject)

        self.assertIn(u'有効なプラットフォーム契約（gaccoサービス契約）が存在しません。', message)
        self.assertIn(u'有効なオーナーサービス契約が存在しません。', message)

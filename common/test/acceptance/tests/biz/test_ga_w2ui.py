"""
End-to-end tests for w2ui of biz feature
"""

from datetime import datetime
import pytz

from bok_choy.web_app_test import WebAppTest
from nose.plugins.attrib import attr

from common.test.acceptance.pages.biz.ga_contract import BizContractDetailPage, BizContractPage
from . import AGGREGATOR_USER_INFO, GaccoBizTestMixin
from ...pages.biz.ga_dashboard import DashboardPage


@attr('shard_ga_biz_2')
class BizW2uiTest(WebAppTest, GaccoBizTestMixin):

    def _create_organization(self, biz_organization_page):
        org_code = 'test_org_' + self.unique_id[0:8]
        org_name = 'org name ' + org_code
        biz_organization_page.click_add().input(org_name, org_code).click_register()
        organization_grid_row = biz_organization_page.get_row({'Organization Name': org_name})
        self.assert_grid_row(
            organization_grid_row,
            {
                'Organization Name': org_name,
                'Organization Code': org_code,
            }
        )
        return organization_grid_row

    def assert_grid_icon_columns_checked(self, grid_page, grid_columns, grid_icon_columns):
        for c in grid_icon_columns:
            if c in grid_columns:
                self.assertTrue(grid_page.is_checked_grid_icon_columns(c))
            else:
                self.assertFalse(grid_page.is_checked_grid_icon_columns(c))

    def test_organization_grid_icon_columns(self):
        """
        Test organization grid columns
        """
        self.switch_to_user(AGGREGATOR_USER_INFO)

        # view organization grid
        biz_organization_page = DashboardPage(self.browser).visit().click_biz().click_organization()
        biz_organization_page.click_grid_icon_columns()

        # all columns of grid
        grid_icon_columns = biz_organization_page.grid_icon_columns

        # visivility columns of grid
        grid_columns = biz_organization_page.grid_columns
        self.assertIn(u'Organization Name', grid_columns)
        self.assertNotIn(u'Created By Name', grid_columns)

        self.assert_grid_icon_columns_checked(biz_organization_page, grid_columns, grid_icon_columns)

        # click grid-icon-columns checkbox.
        biz_organization_page.click_grid_icon_columns_checkbox(u'Created By Name')
        grid_columns = biz_organization_page.grid_columns
        self.assertIn(u'Organization Name', grid_columns)
        self.assertIn(u'Created By Name', grid_columns)

        # click grid-icon-columns label.
        biz_organization_page.click_grid_icon_columns_label(u'Organization Name')
        grid_columns = biz_organization_page.grid_columns
        self.assertNotIn(u'Organization Name', grid_columns)
        self.assertIn(u'Created By Name', grid_columns)

    def test_organization_grid_search(self):
        """
        Test organization grid search
        """
        self.switch_to_user(AGGREGATOR_USER_INFO)

        # view organization grid
        biz_organization_page = DashboardPage(self.browser).visit().click_biz().click_organization()
        self.assertEqual(u'Organization Name', biz_organization_page.search_placeholder)

        # create test data
        org1 = self._create_organization(biz_organization_page)
        org2 = self._create_organization(biz_organization_page)
        org3 = self._create_organization(biz_organization_page)
        org4 = self._create_organization(biz_organization_page)

        # columns of grid for search
        biz_organization_page.click_grid_icon_search()
        grid_icon_search = biz_organization_page.grid_icon_search
        self.assertEqual([u'Organization Name', u'Organization Code', u'Created By Name', u'Created Date'], grid_icon_search)
        self.assertTrue(biz_organization_page.is_checked_grid_icon_search(u'Organization Name'))

        # search text
        biz_organization_page.click_grid_icon_search_label(u'Organization Code')
        self.assertEqual(u'Organization Code', biz_organization_page.search_placeholder)

        # 0 result
        biz_organization_page.search('hoge')
        self.assert_grid_row_not_in(org1, biz_organization_page.grid_rows)
        self.assert_grid_row_not_in(org2, biz_organization_page.grid_rows)
        self.assert_grid_row_not_in(org3, biz_organization_page.grid_rows)
        self.assert_grid_row_not_in(org4, biz_organization_page.grid_rows)

        # 1 result
        biz_organization_page.search(org1['Organization Code'])
        self.assert_grid_row_in(org1, biz_organization_page.grid_rows)
        self.assert_grid_row_not_in(org2, biz_organization_page.grid_rows)
        self.assert_grid_row_not_in(org3, biz_organization_page.grid_rows)
        self.assert_grid_row_not_in(org4, biz_organization_page.grid_rows)

        # clear search
        biz_organization_page.clear_search()
        self.assertLess(4, len(biz_organization_page.grid_rows))

        # columns of grid for search
        biz_organization_page.click_grid_icon_search()
        grid_icon_search = biz_organization_page.grid_icon_search
        self.assertEqual([u'Organization Name', u'Organization Code', u'Created By Name', u'Created Date'], grid_icon_search)
        self.assertTrue(biz_organization_page.is_checked_grid_icon_search(u'Organization Code'))

        # search date
        now_ymd = datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y/%m/%d')
        biz_organization_page.click_grid_icon_search_label(u'Created Date').wait_for_calendar_visibility()
        self.assertEqual(u'Created Date', biz_organization_page.search_placeholder)
        self.assertIn(now_ymd, biz_organization_page.calendar_date)

        # previous month calendar
        biz_organization_page.click_calendar_prev()
        self.assertNotIn(now_ymd, biz_organization_page.calendar_date)

        # next month calendar
        biz_organization_page.click_calendar_next()
        self.assertIn(now_ymd, biz_organization_page.calendar_date)

        # choice calendar ymd
        biz_organization_page.click_calendar(now_ymd)
        self.assert_grid_row_in(org1, biz_organization_page.grid_rows)
        self.assert_grid_row_in(org2, biz_organization_page.grid_rows)
        self.assert_grid_row_in(org3, biz_organization_page.grid_rows)
        self.assert_grid_row_in(org4, biz_organization_page.grid_rows)

        # clear search
        biz_organization_page.clear_search()
        self.assertLess(4, len(biz_organization_page.grid_rows))

        # choice calendar y & m & ymd
        biz_organization_page.click_search().wait_for_calendar_visibility()
        biz_organization_page.click_calendar_title().click_calendar_jump(2000, 2).wait_for_calendar_visibility()
        self.assertIn('2000/02/29', biz_organization_page.calendar_date)

        biz_organization_page.click_calendar('2000/02/29')
        self.assert_grid_row_not_in(org1, biz_organization_page.grid_rows)
        self.assert_grid_row_not_in(org2, biz_organization_page.grid_rows)
        self.assert_grid_row_not_in(org3, biz_organization_page.grid_rows)
        self.assert_grid_row_not_in(org4, biz_organization_page.grid_rows)

    def test_organization_grid_sort(self):
        """
        Test organization grid sort
        """
        self.switch_to_user(AGGREGATOR_USER_INFO)

        # view organization grid
        biz_organization_page = DashboardPage(self.browser).visit().click_biz().click_organization()

        # create test data
        for _ in range(10):
            self._create_organization(biz_organization_page)

        # initial grid-rows
        grid_rows = biz_organization_page.grid_rows

        # sort by code
        biz_organization_page.click_sort(u'Organization Code')
        grid_rows.sort(key=lambda x: x[u'Organization Code'])
        self.assert_grid_row_equal(grid_rows, biz_organization_page.grid_rows)

        # sort by name
        biz_organization_page.click_sort(u'Organization Name')
        grid_rows.sort(key=lambda x: x[u'Organization Name'])
        self.assert_grid_row_equal(grid_rows, biz_organization_page.grid_rows)

        # sort by name reverse
        biz_organization_page.click_sort(u'Organization Name')
        grid_rows.sort(key=lambda x: x[u'Organization Name'], reverse=True)
        self.assert_grid_row_equal(grid_rows, biz_organization_page.grid_rows)

    def test_contract_grid_sort(self):
        """
        Test organization grid sort
        """
        self.switch_to_user(AGGREGATOR_USER_INFO)

        biz_contract_page = DashboardPage(self.browser).visit().click_biz().click_contract()

        # create test data
        for _ in range(10):
            self.create_contract(biz_contract_page,
                                      'OS', '2016/01/{0:02d}'.format(_ + 1), '2116/01/{0:02d}'.format(_ + 1))

        # initial grid-rows
        grid_rows = biz_contract_page.grid_rows

        # sort by name
        biz_contract_page.click_sort(u'Contract Name')
        grid_rows.sort(key=lambda x: x[u'Contract Name'])
        self.assert_grid_row_equal(grid_rows, biz_contract_page.grid_rows)

        # sort by name reverse
        biz_contract_page.click_sort(u'Contract Name')
        grid_rows.sort(key=lambda x: x[u'Contract Name'], reverse=True)
        self.assert_grid_row_equal(grid_rows, biz_contract_page.grid_rows)

    def test_contract_grid_icon_columns(self):
        """
        Test contract grid columns
        """
        self.switch_to_user(AGGREGATOR_USER_INFO)

        # view contract grid
        biz_contract_page = DashboardPage(self.browser).visit().click_biz().click_contract()
        self.create_contract(biz_contract_page, 'OS', '2016/01/01', '2116/01/01')

        # all columns of grid
        biz_contract_page.click_grid_icon_columns()
        grid_icon_columns = biz_contract_page.grid_icon_columns

        # visibility columns of grid
        grid_columns = biz_contract_page.grid_columns

        self.assertIn(u'Contract Name', grid_columns)
        self.assertNotIn(u'Created By Name', grid_columns)

        self.assert_grid_icon_columns_checked(biz_contract_page, grid_columns, grid_icon_columns)

        # click grid-icon-columns checkbox.
        biz_contract_page.click_grid_icon_columns_checkbox(u'Created By Name')
        grid_columns = biz_contract_page.grid_columns
        self.assertIn(u'Contract Name', grid_columns)
        self.assertIn(u'Created By Name', grid_columns)

        # click grid-icon-columns label.
        biz_contract_page.click_grid_icon_columns_label(u'Contract Name')
        grid_columns = biz_contract_page.grid_columns
        self.assertNotIn(u'Contract Name', grid_columns)
        self.assertIn(u'Created By Name', grid_columns)

    def test_contract_grid_search(self):
        """
        Test organization grid search
        """
        self.switch_to_user(AGGREGATOR_USER_INFO)

        searchable_fields = [u'Contract Name', u'Contract Type', u'Invitation Code', u'Contractor Organization Name',
                             u'Contract Start Date', u'Contract End Date', u'Created By Name', u'Created Date']

        # view contract grid
        biz_contract_page = DashboardPage(self.browser).visit().click_biz().click_contract()
        # create test data
        contract1 = self.create_contract(biz_contract_page, 'OS', '2016/01/01', '2116/01/01')
        contract2 = self.create_contract(biz_contract_page, 'OS', '2016/01/01', '2116/01/01')
        contract3 = self.create_contract(biz_contract_page, 'OS', '2016/01/01', '2116/01/01')
        contract4 = self.create_contract(biz_contract_page, 'OS', '2016/01/01', '2116/01/01')

        self.assertEqual(u'Contract Name', biz_contract_page.search_placeholder)

        # columns of grid for search
        biz_contract_page.click_grid_icon_search()
        grid_icon_search = biz_contract_page.grid_icon_search
        self.assertEqual(searchable_fields, grid_icon_search)
        self.assertTrue(biz_contract_page.is_checked_grid_icon_search(u'Contract Name'))

        # search text
        biz_contract_page.click_grid_icon_search_label(u'Invitation Code')
        self.assertEqual(u'Invitation Code', biz_contract_page.search_placeholder)

        # 0 result
        biz_contract_page.search('hoge')
        self.assert_grid_row_not_in(contract1, biz_contract_page.grid_rows)
        self.assert_grid_row_not_in(contract2, biz_contract_page.grid_rows)
        self.assert_grid_row_not_in(contract3, biz_contract_page.grid_rows)
        self.assert_grid_row_not_in(contract4, biz_contract_page.grid_rows)

        # 1 result
        biz_contract_page.search(contract1['Invitation Code'])
        self.assert_grid_row_in(contract1, biz_contract_page.grid_rows)
        self.assert_grid_row_not_in(contract2, biz_contract_page.grid_rows)
        self.assert_grid_row_not_in(contract3, biz_contract_page.grid_rows)
        self.assert_grid_row_not_in(contract4, biz_contract_page.grid_rows)

        # clear search
        biz_contract_page.clear_search()
        self.assertLess(4, len(biz_contract_page.grid_rows))

        # columns of grid for search
        biz_contract_page.click_grid_icon_search()
        grid_icon_search = biz_contract_page.grid_icon_search
        self.assertEqual(searchable_fields, grid_icon_search)
        self.assertTrue(biz_contract_page.is_checked_grid_icon_search(u'Invitation Code'))

        # search date
        now_ymd = datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y/%m/%d')
        biz_contract_page.click_grid_icon_search_label(u'Created Date').wait_for_calendar_visibility()
        self.assertEqual(u'Created Date', biz_contract_page.search_placeholder)
        self.assertIn(now_ymd, biz_contract_page.calendar_date)

        # previous month calendar
        biz_contract_page.click_calendar_prev()
        self.assertNotIn(now_ymd, biz_contract_page.calendar_date)

        # next month calendar
        biz_contract_page.click_calendar_next()
        self.assertIn(now_ymd, biz_contract_page.calendar_date)

        # choice calendar ymd
        biz_contract_page.click_calendar(now_ymd)
        self.assert_grid_row_in(contract1, biz_contract_page.grid_rows)
        self.assert_grid_row_in(contract2, biz_contract_page.grid_rows)
        self.assert_grid_row_in(contract3, biz_contract_page.grid_rows)
        self.assert_grid_row_in(contract4, biz_contract_page.grid_rows)

        # clear search
        biz_contract_page.clear_search()
        self.assertLess(4, len(biz_contract_page.grid_rows))

        # choice calendar y & m & ymd
        biz_contract_page.click_search().wait_for_calendar_visibility()
        biz_contract_page.click_calendar_title().click_calendar_jump(2000, 2).wait_for_calendar_visibility()
        self.assertIn('2000/02/29', biz_contract_page.calendar_date)

        biz_contract_page.click_calendar('2000/02/29')
        self.assert_grid_row_not_in(contract1, biz_contract_page.grid_rows)
        self.assert_grid_row_not_in(contract2, biz_contract_page.grid_rows)
        self.assert_grid_row_not_in(contract3, biz_contract_page.grid_rows)
        self.assert_grid_row_not_in(contract4, biz_contract_page.grid_rows)

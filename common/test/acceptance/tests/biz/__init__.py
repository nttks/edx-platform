from common.test.acceptance.pages.biz.ga_contract import BizContractDetailPage, BizContractPage
from ..ga_helpers import GaccoTestMixin

from ...pages.biz.ga_w2ui import remove_grid_row_index
from ...pages.common.logout import LogoutPage
from ...pages.lms.auto_auth import AutoAuthPage


SUPER_USER_INFO = {
    'username': 'superuser',
    'password': 'SuperUser3',
    'email': 'superuser@example.com',
}
PLATFORMER_USER_INFO = {
    'username': 'plat_platformer',
    'password': 'platPlatformer3',
    'email': 'plat_platformer@example.com',
}
AGGREGATOR_USER_INFO = {
    'username': 'owner_aggregator',
    'password': 'ownerAggregator3',
    'email': 'owner_aggregator@example.com',
}
A_DIRECTOR_USER_INFO = {
    'username': 'acom_director',
    'password': 'acomDirector3',
    'email': 'acom_director@example.com',
}
A_MANAGER_USER_INFO = {
    'username': 'acom_manager',
    'password': 'acomManager3',
    'email': 'acom_manager@example.com',
}
B_DIRECTOR_USER_INFO = {
    'username': 'bcom_director',
    'password': 'bcomDirector3',
    'email': 'bcom_director@example.com',
}
B_MANAGER_USER_INFO = {
    'username': 'bcom_manager',
    'password': 'bcomManager3',
    'email': 'bcom_manager@example.com',
}
C_DIRECTOR_USER_INFO = {
    'username': 'ccom_director',
    'password': 'ccomDirector3',
    'email': 'ccom_director@example.com',
}
C_MANAGER_USER_INFO = {
    'username': 'ccom_manager',
    'password': 'ccomManager3',
    'email': 'ccom_manager@example.com',
}

PLAT_COMPANY = 1
OWNER_COMPANY = 2
A_COMPANY = 3
B_COMPANY = 4
C_COMPANY = 5


class GaccoBizTestMixin(GaccoTestMixin):
    """
    Mixin for gacco biz tests
    """

    def switch_to_user(self, user_info):
        LogoutPage(self.browser).visit()
        AutoAuthPage(self.browser, username=user_info['username'], password=user_info['password'], email=user_info['email']).visit()
        return user_info

    def assert_grid_row(self, grid_row, assert_dict):
        for assert_key, assert_value in assert_dict.items():
            self.assertIn(assert_key, grid_row)
            self.assertEqual(assert_value, grid_row[assert_key])

    def assert_grid_row_in(self, grid_row, grid_rows):
        self.assertIn(
            remove_grid_row_index(grid_row),
            [remove_grid_row_index(r) for r in grid_rows]
        )

    def assert_grid_row_not_in(self, grid_row, grid_rows):
        self.assertNotIn(
            remove_grid_row_index(grid_row),
            [remove_grid_row_index(r) for r in grid_rows]
        )

    def assert_grid_row_equal(self, grid_rows_a, grid_rows_b):
        self.assertEqual(
            [remove_grid_row_index(r) for r in grid_rows_a],
            [remove_grid_row_index(r) for r in grid_rows_b]
        )

    def create_contract(self, biz_contract_page, contract_type, start_date, end_date, contractor_organization='',
                        detail_info=None,
                        additional_info=None):
        """
        Register a contract.
        """
        biz_contract_page.click_register_button()
        biz_contract_detail_page = BizContractDetailPage(self.browser).wait_for_page()
        contract_name = 'test_contract_' + self.unique_id[0:8]
        invitation_code = self.unique_id[0:8]
        biz_contract_detail_page.input(contract_name=contract_name, contract_type=contract_type,
                                       invitation_code=invitation_code, start_date=start_date,
                                       end_date=end_date, contractor_organization=contractor_organization)

        if detail_info:
            for i, course_id in enumerate(detail_info):
                biz_contract_detail_page.add_detail_info(course_id, i + 1)

        if additional_info:
            for i, additional_name in enumerate(additional_info):
                biz_contract_detail_page.add_additional_info(additional_name, i + 1)

        biz_contract_detail_page.click_register_button()
        BizContractPage(self.browser).wait_for_page()

        self.assertIn("The new contract has been added.", biz_contract_page.messages)
        self.assert_grid_row(
                biz_contract_page.get_row({'Contract Name': contract_name}),
                {
                    'Contract Name': contract_name,
                    'Invitation Code': invitation_code,
                    'Contract Start Date': start_date,
                    'Contract End Date': end_date
                }
        )
        return biz_contract_page.get_row({'Contract Name': contract_name})

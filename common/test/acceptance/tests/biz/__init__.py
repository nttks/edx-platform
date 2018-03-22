from contextlib import contextmanager

from django.utils.crypto import get_random_string

from ..ga_helpers import GaccoTestMixin, SUPER_USER_INFO
from ...pages.biz.ga_contract import BizContractDetailPage, BizContractPage
from ...pages.biz.ga_dashboard import DashboardPage
from ...pages.biz.ga_invitation import BizInvitationPage, BizInvitationConfirmPage
from ...pages.biz.ga_w2ui import remove_grid_row_index
from ...pages.lms.ga_dashboard import DashboardPage as GaDashboardPage


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
PLAT_COMPANY_NAME = 'plat org'
PLAT_COMPANY_CODE = 'plat'

OWNER_COMPANY = 2
OWNER_COMPANY_NAME = 'owner company'
OWNER_COMPANY_CODE = 'owner'

A_COMPANY = 3
A_COMPANY_NAME = 'A company'
A_COMPANY_CODE = 'acom'

B_COMPANY = 4
B_COMPANY_NAME = 'B company'
B_COMPANY_CODE = 'bcom'

C_COMPANY = 5
C_COMPANY_NAME = 'C company'
C_COMPANY_CODE = 'ccom'


@contextmanager
def visit_page_on_new_window(page_object):
    current_handle = page_object.browser.current_window_handle
    page_object.browser.execute_script('''
                           window.open("{}", "_blank");
                           '''.format(page_object.url))
    page_object.browser.switch_to_window(page_object.browser.window_handles[-1])
    yield page_object.wait_for_page()
    page_object.browser.close()
    page_object.browser.switch_to_window(current_handle)


class GaccoBizTestMixin(GaccoTestMixin):
    """
    Mixin for gacco biz tests
    """

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

    def create_contract(self, biz_contract_page, contract_type, start_date, end_date, contractor_organization='', contractor_organization_name=None,
                        detail_info=None, register_type='ERS'):
        """
        Register a contract.
        """
        biz_contract_page.click_register_button()
        biz_contract_detail_page = BizContractDetailPage(self.browser).wait_for_page()
        contract_name = 'test_contract_' + self.unique_id[0:8]
        invitation_code = self.unique_id[0:8]
        biz_contract_detail_page.input(contract_name=contract_name, contract_type=contract_type, register_type=register_type,
                                       invitation_code=invitation_code, start_date=start_date,
                                       end_date=end_date, contractor_organization=contractor_organization)
        if contractor_organization_name:
            biz_contract_detail_page.select_contractor_organization(contractor_organization_name)

        if detail_info:
            for i, course_id in enumerate(detail_info):
                biz_contract_detail_page.add_detail_info(course_id, i + 1)

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

    def create_aggregator(self, with_contract_count=1):
        new_aggregator = self.register_user()
        new_org_info = self.register_organization(PLATFORMER_USER_INFO)
        new_contracts = []
        for i in range(with_contract_count):
            new_contracts.append(self.register_contract(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'O'))
        self.grant(PLATFORMER_USER_INFO, new_org_info['Organization Name'], 'aggregator', new_aggregator)
        return new_aggregator, new_org_info, new_contracts

    @property
    def new_password(self):
        return 'Aa0' + get_random_string(12)

    @property
    def new_user_info(self):
        username = 'test_' + get_random_string(12)
        return {
            'username': username,
            'password': self.new_password,
            'email': username + '@example.com',
        }

    def grant(self, operator, organization_name, permission, grant_to_user_info):
        self.switch_to_user(operator)

        biz_manager_page = DashboardPage(self.browser).visit().click_biz().click_manager().select(organization_name, permission)
        self.assertNotIn(grant_to_user_info['username'], biz_manager_page.names)
        self.assertNotIn(grant_to_user_info['email'], biz_manager_page.emails)

        biz_manager_page.input_user(grant_to_user_info['username']).click_grant()
        self.assertIn(grant_to_user_info['username'], biz_manager_page.names)
        self.assertIn(grant_to_user_info['email'], biz_manager_page.emails)

        biz_manager_page.refresh_page().select(organization_name, permission)
        self.assertIn(grant_to_user_info['username'], biz_manager_page.names)
        self.assertIn(grant_to_user_info['email'], biz_manager_page.emails)

    def register_contract(self, operator, contractor_organization_name, contract_type='PF', register_type='ERS',
                          start_date='2000/01/01', end_date='2100/12/31', detail_info=None):
        self.switch_to_user(operator)
        return self.create_contract(
            DashboardPage(self.browser).visit().click_biz().click_contract(),
            contract_type,
            start_date,
            end_date,
            contractor_organization_name=contractor_organization_name,
            detail_info=detail_info,
            register_type=register_type,
        )

    def register_organization(self, operator):
        self.switch_to_user(operator)
        biz_organization_page = DashboardPage(self.browser).visit().click_biz().click_organization()

        org_code = 'test_' + self.unique_id[0:8]
        org_name = 'org name ' + org_code
        biz_organization_page.click_add().input(org_name, org_code).click_register()
        self.assertIn('The new organization has been added.', biz_organization_page.messages)

        new_organization = biz_organization_page.get_row({
            'Organization Name': org_name,
            'Organization Code': org_code,
        })
        self.assertIsNotNone(new_organization)

        return new_organization

    def register_invitation(self, invitation_code, additional_info):
        """
        Register invitation code
        """
        BizInvitationPage(self.browser).visit().input_invitation_code(invitation_code).click_register_button()
        invitation_confirm_page = BizInvitationConfirmPage(self.browser, invitation_code).wait_for_page()
        if additional_info:
            for i, additional_name in enumerate(additional_info):
                invitation_confirm_page.input_additional_info(additional_name, i)
        invitation_confirm_page.click_register_button()
        return GaDashboardPage(self.browser).wait_for_page()

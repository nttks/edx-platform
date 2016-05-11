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

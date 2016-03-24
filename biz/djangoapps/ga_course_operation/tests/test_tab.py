from biz.djangoapps.ga_course_operation.tab import ManagerTab
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.ga_manager.tests.factories import ManagerFactory


class ManagerTabTest(BizContractTestBase):

    def test_is_enabled_no_user(self):
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc1, None))

    def test_is_enabled_no_course(self):
        self.setup_user()
        self.assertFalse(ManagerTab.is_enabled(None, self.user))

    def test_is_enabled_contract_platformer(self):
        self.setup_user()
        ManagerFactory.create(org=self.contract_org, user=self.user, permissions=[self.platformer_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc1, self.user))

    def test_is_enabled_contract_aggregator(self):
        self.setup_user()
        ManagerFactory.create(org=self.contract_org, user=self.user, permissions=[self.aggregator_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc1, self.user))

    def test_is_enabled_contract_director(self):
        self.setup_user()
        ManagerFactory.create(org=self.contract_org, user=self.user, permissions=[self.director_permission])
        self.assertTrue(ManagerTab.is_enabled(self.course_spoc1, self.user))

    def test_is_enabled_contract_manager(self):
        self.setup_user()
        ManagerFactory.create(org=self.contract_org, user=self.user, permissions=[self.manager_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc1, self.user))

    def test_is_enabled_no_contract_platformer(self):
        self.setup_user()
        ManagerFactory.create(org=self.no_contract_org, user=self.user, permissions=[self.platformer_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc1, self.user))

    def test_is_enabled_no_contract_aggregator(self):
        self.setup_user()
        ManagerFactory.create(org=self.no_contract_org, user=self.user, permissions=[self.aggregator_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc1, self.user))

    def test_is_enabled_no_contract_director(self):
        self.setup_user()
        ManagerFactory.create(org=self.no_contract_org, user=self.user, permissions=[self.director_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc1, self.user))

    def test_is_enabled_no_contract_manager(self):
        self.setup_user()
        ManagerFactory.create(org=self.no_contract_org, user=self.user, permissions=[self.manager_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc1, self.user))

    def test_is_enabled_other_course_platformer(self):
        self.setup_user()
        ManagerFactory.create(org=self.contract_org, user=self.user, permissions=[self.platformer_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc3, self.user))

    def test_is_enabled_other_course_aggregator(self):
        self.setup_user()
        ManagerFactory.create(org=self.contract_org, user=self.user, permissions=[self.aggregator_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc3, self.user))

    def test_is_enabled_other_course_director(self):
        self.setup_user()
        ManagerFactory.create(org=self.contract_org, user=self.user, permissions=[self.director_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc3, self.user))

    def test_is_enabled_other_course_manager(self):
        self.setup_user()
        ManagerFactory.create(org=self.contract_org, user=self.user, permissions=[self.manager_permission])
        self.assertFalse(ManagerTab.is_enabled(self.course_spoc3, self.user))

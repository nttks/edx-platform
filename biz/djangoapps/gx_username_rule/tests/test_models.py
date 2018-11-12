from student.tests.factories import UserFactory
from biz.djangoapps.gx_username_rule.tests.factories import OrgUsernameRuleFactory
from biz.djangoapps.util.tests.testcase import BizTestBase



class OrgUsernameRuleTest(BizTestBase):

    def test_exists_org_prefix_true(self):
        user = UserFactory.create()
        username_rule = OrgUsernameRuleFactory.create(
            prefix='abc__',
            org=self.gacco_organization
        )
        self.assertTrue(username_rule.exists_org_prefix)

    def test_exists_other_org_prefix_true(self):
        another_org = self._create_organization(org_name='another_org_name', org_code='another_org_code')
        self.gacco_organization.save()
        user = UserFactory.create()
        username_rule = OrgUsernameRuleFactory.create(
            prefix='abc__',
            org=self.gacco_organization
        )

        username_rule1 = OrgUsernameRuleFactory.create(
            prefix='cde__',
            org=another_org
        )
        self.assertTrue(username_rule1.exists_org_prefix)



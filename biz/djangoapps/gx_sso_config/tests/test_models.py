from biz.djangoapps.util.tests.testcase import BizTestBase
from biz.djangoapps.gx_sso_config.tests.factories import SsoConfigFactory
from biz.djangoapps.gx_sso_config.models import SsoConfig
from student.tests.factories import UserFactory
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_member.tests.factories import MemberFactory

class SsoCofigTest(BizTestBase):

    def setUp(self):
        self.user = UserFactory.create()
        self.gacco_organization = Organization(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,  # It means the first of Organization
            created_by=UserFactory.create(),
        )
        self.gacco_organization.save()

    def test_user_control_process(self):
        user = UserFactory.create()
        MemberFactory.create(
            org=self.gacco_organization,
            group=None,
            user=user,
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            is_active=True,
            is_delete=False,
        )
        SsoConfigFactory.create(
            idp_slug='abc',
            org=self.gacco_organization
        )
        self.assertEqual(True, SsoConfig.user_control_process(user_id=self.user.id))
        self.assertEqual(False, SsoConfig.user_control_process(user_id=user.id))

    def test_is_hide_icon(self):
        SsoConfigFactory.create(
            idp_slug='abc',
            org=self.gacco_organization
        )
        self.assertEqual(True, SsoConfig.is_hide_icon(provider_id='saml-abc'))
        self.assertEqual(True, SsoConfig.is_hide_icon(provider_id='SAML-abc'))
        self.assertEqual(False, SsoConfig.is_hide_icon(provider_id='saml-cde'))
        self.assertEqual(False, SsoConfig.is_hide_icon(provider_id='oauth-abc'))
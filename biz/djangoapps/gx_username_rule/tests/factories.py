from factory.django import DjangoModelFactory
from biz.djangoapps.gx_username_rule.models import OrgUsernameRule

class OrgUsernameRuleFactory(DjangoModelFactory):
    class Meta(object):
        model = OrgUsernameRule
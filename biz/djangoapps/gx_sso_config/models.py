from django.db import models
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_member.models import Member
# Create your models here.

class SsoConfig(models.Model):
    idp_slug = models.SlugField(max_length=30, db_index=True)
    org = models.ForeignKey(Organization)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, null=True, db_index=True, blank=True)

    class Meta:
        app_label = 'gx_sso_config'

    @classmethod
    def user_control_process(cls, user_id):
        if Member.objects.filter(user_id=user_id, is_active=True).exists():
            if cls.objects.filter(org=Member.objects.filter(user_id=user_id,
                                                                  is_active=True).first().org_id).exists():
                return False
        return True

    @classmethod
    def is_hide_icon(cls, provider_id=''):
        if cls.objects.filter(idp_slug=provider_id.replace('SAML-', '').replace('saml-','')).exists():
                return True
        return False

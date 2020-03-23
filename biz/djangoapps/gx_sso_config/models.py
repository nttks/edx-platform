from django.db import models
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_member.models import Member
from social.apps.django_app.default.models import UserSocialAuth
import logging

log = logging.getLogger(__name__)


class SsoConfig(models.Model):
    """
    This is a table for restricting execution to users logged in with the SAML provider.
    """
    idp_slug = models.SlugField(max_length=30, db_index=True)
    org = models.ForeignKey(Organization)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True, null=True, db_index=True, blank=True)
    logout_show = models.BooleanField(default=0)

    class Meta:
        app_label = 'gx_sso_config'

    def __unicode__(self):
        return self.idp_slug

    @classmethod
    def user_control_process(cls, user_id):
        """
        Restrict items that can be executed by users of the organization registered in SsoConfig.
        :param user_id:
        :return:
        TRUE :
        FALSE :
        """
        if user_id is not None:
            for member in Member.objects.filter(user_id=long(user_id), is_active=True):
                if member:
                    if cls.objects.filter(org=member.org_id).exists():
                        return False
        return True

    @classmethod
    def is_hide_icon(cls, provider_id=''):
        """
        Restrict display of pages and icon to users of organizations registered in SsoConfig.
        :param provider_id:
        :return:
        """
        if cls.objects.filter(idp_slug=str(provider_id).replace('SAML-', '').replace('saml-','')).exists():
                return True
        return False

    @classmethod
    def user_control_process2(cls, user_id):
        """
        Restrict items that can be executed by users of the organization registered in SsoConfig.
        :param user_id:
        :return:
        TRUE :
        FALSE :
        """
        if user_id is not None:
            for member in Member.objects.filter(user_id=long(user_id), is_active=True):
                if member:
                    if cls.objects.filter(org=member.org_id, logout_show=0).exists():
                        return False
        return True

    @classmethod
    def user_control_process_sso(cls, user_id):
        """
        Restrict items that can be executed by users of the organization registered in SsoConfig.
        :param user_id:
        :return:
        TRUE :
        FALSE :
        """
        if user_id is not None:
            for member in Member.objects.filter(user_id=long(user_id), is_active=True):
                if member:
                    if cls.objects.filter(org=member.org_id).exists():
                        if UserSocialAuth.objects.filter(user_id=long(user_id), provider="tpa-saml").exists():
                            return False
        return True

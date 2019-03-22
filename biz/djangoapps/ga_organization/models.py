"""
Models for organization feature
"""
from django.contrib.auth.models import User
from django.db import models


class Organization(models.Model):
    """
    Organization model.
    """
    org_name = models.CharField(max_length=255)
    org_code = models.CharField(max_length=64)
    creator_org = models.ForeignKey('self', related_name='creator_orgs')
    created_by = models.ForeignKey(User)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'ga_organization'

    def __unicode__(self):
        return self.org_name

    @property
    def can_auto_mask(self):
        return hasattr(self, 'organizationoption') and self.organizationoption.auto_mask_flg

    @property
    def get_reservation_mail_date(self):
        if hasattr(self, 'organizationoption'):
            return self.organizationoption.reservation_mail_date
        else:
            return None

    @classmethod
    def find_by_creator_org(cls, org):
        """
        Find organizations by creator organization

        :param org: organization object
        :return: filtered query
        """
        return cls.objects.filter(creator_org=org).order_by('-created')

    @classmethod
    def find_by_creator_org_without_itself(cls, org):
        """
        Find organizations by creator organization and exclude creator self

        :param org: organization object
        :return: filtered query
        """
        return cls.objects.filter(creator_org=org).exclude(id=org.id).order_by('-created')

    @classmethod
    def find_by_user(cls, user):
        """
        Find organizations by user via managers__user

        :param user: logged-in user object
        :return: filtered query
        """
        return cls.objects.filter(managers__user=user).order_by('-created')


class OrganizationOption(models.Model):
    """
    This table contains organization option info.
    """
    org = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    # For gx_reservation_mail
    reservation_mail_date = models.TimeField(null=True, blank=True)
    # For gx_save_register_condition
    auto_mask_flg = models.BooleanField(default=False)
    modified_by = models.ForeignKey(User)
    modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.org.org_name

    class Meta:
        app_label = 'ga_organization'
        ordering = ['org']

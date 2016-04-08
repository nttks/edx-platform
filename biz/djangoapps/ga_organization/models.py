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

    def __unicode__(self):
        return self.org_name

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

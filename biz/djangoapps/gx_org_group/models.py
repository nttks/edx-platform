from django.contrib.auth.models import User
from django.db import models
from biz.djangoapps.ga_organization.models import Organization


class Group(models.Model):
    """
    Group model describes relations of org and groupCode
    """
    parent_id = models.IntegerField()
    level_no = models.IntegerField()
    group_code = models.CharField(max_length=20)
    group_name = models.CharField(max_length=255)
    notes = models.CharField(max_length=255, null=True, blank=True)
    org = models.ForeignKey(Organization)
    created_by = models.ForeignKey(User, related_name='creator_groups')
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_by = models.ForeignKey(User, null=True, related_name='modifier_groups', default=None)
    modified = models.DateTimeField(auto_now=True, null=True, db_index=True, blank=True)

    class Meta:
        app_label = 'gx_org_group'

    def __unicode__(self):
        return self.group_name


class Right(models.Model):
    """
    Right model.
    """
    org = models.ForeignKey(Organization, related_name='rights')
    group = models.ForeignKey(Group)
    user = models.ForeignKey(User, related_name='right')
    created_by = models.ForeignKey(User, related_name='creator_rights')
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    creator_org = models.ForeignKey(Organization, related_name='creator_org_rights')

    class Meta:
        app_label = 'gx_org_group'

    def __unicode__(self):
        return self.user.email


class Parent(models.Model):
    """
    Parent path of group
    """
    org = models.ForeignKey(Organization, related_name='parents')
    group = models.ForeignKey(Group, related_name='parent')
    path = models.CharField(max_length=65535, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'gx_org_group'

    def __unicode__(self):
        return self.group.group_name


class Child(models.Model):
    """
    Child of group
    """
    org = models.ForeignKey(Organization, related_name='children')
    group = models.ForeignKey(Group, related_name='child')
    list = models.CharField(max_length=65535, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    def __unicode__(self):
        return self.group.group_name

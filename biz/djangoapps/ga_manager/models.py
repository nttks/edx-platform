"""
Models for manager feature
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _

from biz.djangoapps.ga_organization.models import Organization

PERMISSION_PLATFORMER = ('platformer', _('platformer'))
PERMISSION_AGGREGATOR = ('aggregator', _('aggregator'))
PERMISSION_DIRECTOR = ('director', _('director'))
PERMISSION_MANAGER = ('manager', _('manager'))
PERMISSION_NAME = (PERMISSION_PLATFORMER, PERMISSION_AGGREGATOR, PERMISSION_DIRECTOR, PERMISSION_MANAGER)


class ManagerPermission(models.Model):
    """
    Permission for manager
    """
    permission_name = models.CharField(max_length=255, choices=PERMISSION_NAME)

    can_handle_organization = models.BooleanField()
    can_handle_contract = models.BooleanField()
    can_handle_manager = models.BooleanField()
    can_handle_course_operation = models.BooleanField()
    can_handle_achievement = models.BooleanField()
    can_handle_contract_operation = models.BooleanField()

    class Meta:
        app_label = 'ga_manager'

    def __unicode__(self):
        return self.permission_name


class Manager(models.Model):
    """
    Manager
    """
    org = models.ForeignKey(Organization, related_name='managers')
    user = models.ForeignKey(User)
    manager_permissions = models.ManyToManyField(ManagerPermission, related_name='managers')
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'ga_manager'

    def is_platformer(self):
        """
        Return if this manager is Platformer

        :return: True if this manager is Platformer
        """
        return 'platformer' in [p.permission_name for p in self.manager_permissions.all()]

    def is_aggregator(self):
        """
        Return if this manager is Aggregator

        :return: True if this manager is Aggregator
        """
        return 'aggregator' in [p.permission_name for p in self.manager_permissions.all()]

    def is_director(self):
        """
        Return if this manager is Director

        :return: True if this manager is Director
        """
        return 'director' in [p.permission_name for p in self.manager_permissions.all()]

    def is_manager(self):
        """
        Return if this manager is Manager

        :return: True if this manager is Manager
        """
        return 'manager' in [p.permission_name for p in self.manager_permissions.all()]

    def can_handle_organization(self):
        """
        Return whether this manager can handle organization feature

        :return: True if this manager can handle achievement
        """
        return any([p.can_handle_organization for p in self.manager_permissions.all()])

    def can_handle_contract(self):
        """
        Return whether this manager can handle contract feature

        :return: True if this manager can handle achievement
        """
        return any([p.can_handle_contract for p in self.manager_permissions.all()])

    def get_manager_permissions(self):
        """
        Return whether this manager can handle manager feature

        :return: True if this manager can handle achievement
        """
        return self.manager_permissions.all()

    def can_handle_manager(self):
        """
        Return whether this manager can handle manager feature

        :return: True if this manager can handle achievement
        """
        return any([p.can_handle_manager for p in self.manager_permissions.all()])

    def can_handle_course_operation(self):
        """
        Return whether this manager can handle course operation feature

        :return: True if this manager can handle achievement
        """
        return any([p.can_handle_course_operation for p in self.manager_permissions.all()])

    def can_handle_achievement(self):
        """
        Return whether this manager can handle achievement feature

        :return: True if this manager can handle achievement
        """
        return any([p.can_handle_achievement for p in self.manager_permissions.all()])

    def can_handle_contract_operation(self):
        """
        Return whether this manager can handle contract_operation feature

        :return: True if this manager can handle contract_operation
        """
        return any([p.can_handle_contract_operation for p in self.manager_permissions.all()])

    @classmethod
    def get_manager(cls, user, org):
        """
        Get manager by user and organization

        :param user: logged-in user object
        :param org: Organization object
        :return: Manager object, or None if not exist
        """
        managers = cls.objects.filter(org=org, user=user)
        return managers[0] if managers else None

    @classmethod
    def get_manager_with_permission(cls, org, permissions):
        """
        Filter managers by organization and manager permissions

        :param org: Organization object
        :param permissions: ManagerPermission objects
        :return: Manager objects
        """
        return cls.objects.filter(org=org, manager_permissions=permissions)

    @classmethod
    def get_managers(cls, user):
        """
        Filter managers by user

        :param user: logged-in user object
        :return: Manager objects
        """
        return cls.objects.filter(user=user.id).select_related('org')

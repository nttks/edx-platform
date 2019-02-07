from datetime import datetime
from django.contrib.auth.models import User
from django.db import models
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_org_group.models import Group


class Member(models.Model):
    """
    Member model.
    """
    org = models.ForeignKey(Organization)
    group = models.ForeignKey(Group, null=True)
    user = models.ForeignKey(User, related_name='member')
    code = models.CharField(max_length=255, null=True, db_index=True)
    org1 = models.CharField(max_length=100, null=True)
    org2 = models.CharField(max_length=100, null=True)
    org3 = models.CharField(max_length=100, null=True)
    org4 = models.CharField(max_length=100, null=True)
    org5 = models.CharField(max_length=100, null=True)
    org6 = models.CharField(max_length=100, null=True)
    org7 = models.CharField(max_length=100, null=True)
    org8 = models.CharField(max_length=100, null=True)
    org9 = models.CharField(max_length=100, null=True)
    org10 = models.CharField(max_length=100, null=True)
    item1 = models.CharField(max_length=100, null=True)
    item2 = models.CharField(max_length=100, null=True)
    item3 = models.CharField(max_length=100, null=True)
    item4 = models.CharField(max_length=100, null=True)
    item5 = models.CharField(max_length=100, null=True)
    item6 = models.CharField(max_length=100, null=True)
    item7 = models.CharField(max_length=100, null=True)
    item8 = models.CharField(max_length=100, null=True)
    item9 = models.CharField(max_length=100, null=True)
    item10 = models.CharField(max_length=100, null=True)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)
    updated_by = models.ForeignKey(User, related_name='updater_members', null=True)
    updated = models.DateTimeField(auto_now=True, db_index=True, null=True)
    updated_org = models.ForeignKey(Organization, related_name='updater_org_member', null=True)
    created_by = models.ForeignKey(User, related_name='creator_members')
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    creator_org = models.ForeignKey(Organization, related_name='creator_org_member')

    class Meta:
        app_label = 'gx_member'
        unique_together = ('org', 'user', 'is_active', 'is_delete')

    def __unicode__(self):
        return self.code

    @classmethod
    def find_active_by_code(cls, org, code):
        return cls.objects.filter(
            org=org,
            code=code,
            is_active=True,
            is_delete=False,
        ).order_by('id')

    @classmethod
    def find_active_by_email(cls, org, email):
        return cls.objects.filter(
            org=org,
            user__email=email,
            is_active=True,
            is_delete=False,
        ).order_by('id')

    @classmethod
    def find_active_by_org(cls, org):
        return cls.objects.filter(
            org=org,
            is_active=True,
            is_delete=False,
        ).order_by('id')

    @classmethod
    def find_backup_by_code(cls, org, code):
        return cls.objects.filter(
            org=org,
            code=code,
            is_active=False,
            is_delete=False,
        ).order_by('id')

    @classmethod
    def find_backup_by_email(cls, org, email):
        return cls.objects.filter(
            org=org,
            user__email=email,
            is_active=False,
            is_delete=False,
        ).order_by('id')

    @classmethod
    def find_delete_by_code(cls, org, code):
        return cls.objects.filter(
            org=org,
            code=code,
            is_active=False,
            is_delete=True,
        ).order_by('id')

    @classmethod
    def find_delete_by_email(cls, org, email):
        return cls.objects.filter(
            org=org,
            user__email=email,
            is_active=False,
            is_delete=True,
        ).order_by('id')

    @classmethod
    def delete_backup(cls, org):
        return cls.objects.filter(
            org=org,
            is_active=False,
            is_delete=False,
        ).delete()

    @classmethod
    def change_active_to_backup(cls, org):
        result = []
        for member in cls.objects.filter(org=org, is_active=True):
            member.is_active = False
            member.save()
            result.append(member)
        return result

    @classmethod
    def change_active_to_backup_one(cls, org, code):
        return cls.objects.filter(
            org=org,
            code=code,
            is_active=True
        ).update(is_active=False)

    @classmethod
    def change_active_to_backup_one_email(cls, org, email):
        return cls.objects.filter(
            org=org,
            user__email=email,
            is_active=True
        ).update(is_active=False)


class MemberTaskHistory(models.Model):
    organization = models.ForeignKey(Organization)
    task_id = models.CharField(max_length=255, db_index=True, null=True)
    result = models.BooleanField(default=False)
    messages = models.TextField(null=True)
    requester = models.ForeignKey(User)
    updated = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'gx_member'

    @classmethod
    def create(cls, organization, requester):
        return cls.objects.create(
            organization=organization,
            requester=requester
        )

    @classmethod
    def find_by_organization(cls, organization):
        return cls.objects.filter(organization=organization).order_by('-created')

    def link_to_task(self, task):
        """
        Link to Task instance.

        :param task: ga_task.Task instance
        """
        self.task_id = task.task_id
        self.save()

    def update_result(self, result, messages):
        """
        Update task result

        :param result task result
        :param messages task result messages
        """
        self.result = result
        self.messages = messages
        self.updated = datetime.now()
        self.save()


class MemberRegisterTaskTarget(models.Model):
    """
    Member task target
    """
    class Meta:
        app_label = 'gx_member'
        ordering = ['id']

    history = models.ForeignKey(MemberTaskHistory)
    created = models.DateTimeField(auto_now_add=True)
    member = models.CharField(max_length=6000)

    @classmethod
    def bulk_create(cls, history, members):
        targets = [cls(
            history=history,
            member=member,
        ) for member in members]
        cls.objects.bulk_create(targets)

    @classmethod
    def find_by_history_id(cls, history_id):
        return cls.objects.filter(
            history_id=history_id,
        )


class MemberRegisterMail(models.Model):
    class Meta:
        app_label = 'gx_member'
        ordering = ['org_id']

    def __unicode__(self):
        return self.org_id.org_name

    org_id = models.ForeignKey(Organization)
    mail_to = models.CharField(max_length=255)
    mail_subject = models.CharField(max_length=128)
    mail_body = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, null=True, blank=True)

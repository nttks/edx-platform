from collections import OrderedDict
from datetime import datetime
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.ga_contract.models import Contract
from django.db import models


class ParentCondition(models.Model):
    """
    ParentCondition model.
    """
    SETTING_TYPE_SIMPLE = 1
    SETTING_TYPE_ADVANCED = 2
    SETTING_TYPES = ((SETTING_TYPE_SIMPLE, _('Simple Setting')), (SETTING_TYPE_ADVANCED, _('Advanced Setting')))

    contract = models.ForeignKey(Contract, db_index=True)
    parent_condition_name = models.CharField(max_length=255)
    setting_type = models.IntegerField(choices=SETTING_TYPES)
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='creator_parent_condition')
    modified = models.DateTimeField(auto_now=True, null=True)
    modified_by = models.ForeignKey(User, null=True, related_name='modifier_parent_condition')

    class Meta:
        app_label = 'gx_save_register_condition'

    def __unicode__(self):
        return self.contract.contract_name


class ChildCondition(models.Model):
    """
    ChildCondition model.
    """
    # COMPARISON_TYPE
    COMPARISON_TYPE_EQUAL_NO = 1
    COMPARISON_TYPE_NOT_EQUAL_NO = 2
    COMPARISON_TYPE_CONTAINS_NO = 3
    COMPARISON_TYPE_NOT_CONTAINS_NO = 4
    COMPARISON_TYPE_STARTSWITH_NO = 5
    COMPARISON_TYPE_ENDSWITH_NO = 6
    COMPARISON_TYPE_IN_NO = 7
    COMPARISON_TYPE_NOT_IN_NO = 8
    COMPARISON_TYPE_EQUAL_NO_NAME = _('Comparison Equal')
    COMPARISON_TYPE_NOT_EQUAL_NO_NAME = _('Comparison Not Equal')
    COMPARISON_TYPE_CONTAINS_NO_NAME = _('Comparison Contains')
    COMPARISON_TYPE_NOT_CONTAINS_NO_NAME = _('Comparison Not Contains')
    COMPARISON_TYPE_STARTSWITH_NO_NAME = _('Comparison Starts With')
    COMPARISON_TYPE_ENDSWITH_NO_NAME = _('Comparison Ends With')
    COMPARISON_TYPE_IN_NO_NAME = _('Comparison Equal In')
    COMPARISON_TYPE_NOT_IN_NO_NAME = _('Comparison Not Equal In')
    COMPARISON_TYPES = (
        (COMPARISON_TYPE_EQUAL_NO, COMPARISON_TYPE_EQUAL_NO_NAME),
        (COMPARISON_TYPE_NOT_EQUAL_NO, COMPARISON_TYPE_NOT_EQUAL_NO_NAME),
        (COMPARISON_TYPE_CONTAINS_NO, COMPARISON_TYPE_CONTAINS_NO_NAME),
        (COMPARISON_TYPE_NOT_CONTAINS_NO, COMPARISON_TYPE_NOT_CONTAINS_NO_NAME),
        (COMPARISON_TYPE_STARTSWITH_NO, COMPARISON_TYPE_STARTSWITH_NO_NAME),
        (COMPARISON_TYPE_ENDSWITH_NO, COMPARISON_TYPE_ENDSWITH_NO_NAME),
        (COMPARISON_TYPE_IN_NO, COMPARISON_TYPE_IN_NO_NAME),
        (COMPARISON_TYPE_NOT_IN_NO, COMPARISON_TYPE_NOT_IN_NO_NAME)
    )
    # COMPARISON_TYPE_OPERATOR
    COMPARISON_TYPE_OPERATOR = OrderedDict()
    COMPARISON_TYPE_OPERATOR[COMPARISON_TYPE_EQUAL_NO] = 'exact'
    COMPARISON_TYPE_OPERATOR[COMPARISON_TYPE_NOT_EQUAL_NO] = 'iexact'
    COMPARISON_TYPE_OPERATOR[COMPARISON_TYPE_CONTAINS_NO] = 'contains'
    COMPARISON_TYPE_OPERATOR[COMPARISON_TYPE_NOT_CONTAINS_NO] = 'icontains'
    COMPARISON_TYPE_OPERATOR[COMPARISON_TYPE_STARTSWITH_NO] = 'startswith'
    COMPARISON_TYPE_OPERATOR[COMPARISON_TYPE_ENDSWITH_NO] = 'endswith'
    COMPARISON_TYPE_OPERATOR[COMPARISON_TYPE_IN_NO] = 'in'
    COMPARISON_TYPE_OPERATOR[COMPARISON_TYPE_NOT_IN_NO] = 'not in'

    # COMPARISON_TARGET
    COMPARISON_TARGET_USERNAME = 'username'
    COMPARISON_TARGET_EMAIL = 'email'
    COMPARISON_TARGET_LOGIN_CODE = 'login_code'
    COMPARISON_TARGET_CODE = 'code'
    COMPARISON_TARGET_GROUP_NAME = 'group_name'
    COMPARISON_TARGET_ORG_LIST = ['org' + str(i) for i in range(1, 11)]
    COMPARISON_TARGET_ITEM_LIST = ['item' + str(i) for i in range(1, 11)]
    COMPARISON_TARGET = (
        (COMPARISON_TARGET_USERNAME, _("Username")),
        (COMPARISON_TARGET_EMAIL, _("Email Address")),
        (COMPARISON_TARGET_LOGIN_CODE, _("Login Code")),
        (COMPARISON_TARGET_CODE, _("Member Code")),
        (COMPARISON_TARGET_GROUP_NAME, _("Organization Group Name")),
        (COMPARISON_TARGET_ORG_LIST[0], _("Organization") + '1'),
        (COMPARISON_TARGET_ORG_LIST[1], _("Organization") + '2'),
        (COMPARISON_TARGET_ORG_LIST[2], _("Organization") + '3'),
        (COMPARISON_TARGET_ORG_LIST[3], _("Organization") + '4'),
        (COMPARISON_TARGET_ORG_LIST[4], _("Organization") + '5'),
        (COMPARISON_TARGET_ORG_LIST[5], _("Organization") + '6'),
        (COMPARISON_TARGET_ORG_LIST[6], _("Organization") + '7'),
        (COMPARISON_TARGET_ORG_LIST[7], _("Organization") + '8'),
        (COMPARISON_TARGET_ORG_LIST[8], _("Organization") + '9'),
        (COMPARISON_TARGET_ORG_LIST[9], _("Organization") + '10'),
        (COMPARISON_TARGET_ITEM_LIST[0], _("Item") + '1'), (COMPARISON_TARGET_ITEM_LIST[1], _("Item") + '2'),
        (COMPARISON_TARGET_ITEM_LIST[2], _("Item") + '3'), (COMPARISON_TARGET_ITEM_LIST[3], _("Item") + '4'),
        (COMPARISON_TARGET_ITEM_LIST[4], _("Item") + '5'), (COMPARISON_TARGET_ITEM_LIST[5], _("Item") + '6'),
        (COMPARISON_TARGET_ITEM_LIST[6], _("Item") + '7'), (COMPARISON_TARGET_ITEM_LIST[7], _("Item") + '8'),
        (COMPARISON_TARGET_ITEM_LIST[8], _("Item") + '9'), (COMPARISON_TARGET_ITEM_LIST[9], _("Item") + '10'),
    )

    contract = models.ForeignKey(Contract, db_index=True)
    parent_condition = models.ForeignKey(ParentCondition, db_index=True)
    parent_condition_name = models.CharField(max_length=255)
    comparison_target = models.CharField(max_length=255, choices=COMPARISON_TARGET)
    comparison_type = models.IntegerField(choices=COMPARISON_TYPES)
    comparison_string = models.TextField(null=True)

    class Meta:
        app_label = 'gx_save_register_condition'

    def __unicode__(self):
        return self.contract.contract_name


class ReflectConditionTaskHistory(models.Model):
    """
    ReflectConditionTaskHistory model.
    """
    organization = models.ForeignKey(Organization)
    contract = models.ForeignKey(Contract)
    task_id = models.CharField(max_length=255, db_index=True, null=True)
    result = models.BooleanField(default=False)
    messages = models.TextField(null=True)
    requester = models.ForeignKey(User, null=True)
    updated = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'gx_save_register_condition'

    def __unicode__(self):
        return self.contract.contract_name

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
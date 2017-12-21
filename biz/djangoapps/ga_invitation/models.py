"""
Models for invitation feature
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _

from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.util import datetime_utils


INPUT_INVITATION_CODE = 'Input'
REGISTER_INVITATION_CODE = 'Register'
UNREGISTER_INVITATION_CODE = 'Unregister'

STATUS = (
    (INPUT_INVITATION_CODE, _('Input Invitation')),
    (REGISTER_INVITATION_CODE, _('Register Invitation')),
    (UNREGISTER_INVITATION_CODE, _('Unregister Invitation'))
)


class ContractRegisterManager(models.Manager):
    def enabled(self, **kwargs):
        today = datetime_utils.timezone_today()
        return self.filter(contract__start_date__lte=today, contract__end_date__gte=today)


class AdditionalInfoSetting(models.Model):
    """
    AdditionalInfo for user settings
    """
    class Meta(object):
        """
        Meta info
        """
        app_label = 'ga_invitation'
        unique_together = ('contract', 'user', 'display_name')

    user = models.ForeignKey(User)
    contract = models.ForeignKey(Contract)
    display_name = models.CharField(max_length=255)
    value = models.CharField(max_length=255, default='')
    created = models.DateTimeField(auto_now_add=True)

    @classmethod
    def set_value(cls, user, contract, additional_info, value):
        """
        Update value
        - If not exists, insert new record.
        """
        setting, _ = cls.objects.get_or_create(user=user, contract=contract, display_name=additional_info.display_name)
        setting.value = value
        setting.save()

    @classmethod
    def get_value(cls, user, contract, additional_info):
        """
        Get value
        - If not exists, insert new record.
        """
        setting, _ = cls.objects.get_or_create(user=user, contract=contract, display_name=additional_info.display_name)
        return setting.value

    @classmethod
    def get_value_by_display_name(cls, user, contract, display_name):
        """
        Get value by User and Contract and display_name of AdditionalInfo
        - If not exists, return None
        """
        try:
            return cls.objects.get(user=user, contract=contract, display_name=display_name).value
        except cls.DoesNotExist:
            return None

    @classmethod
    def find_by_user_and_contract(cls, user, contract):
        return cls.objects.filter(user=user, contract=contract)

    @classmethod
    def find_by_user(cls, user):
        return cls.objects.filter(user=user)

    @classmethod
    def find_by_contract(cls, contract):
        return cls.objects.filter(contract=contract).order_by('id')


class ContractRegister(models.Model):

    """
    Contract register for user
    """
    class Meta(object):
        """
        Meta info
        """
        app_label = 'ga_invitation'
        unique_together = ('contract', 'user')

    user = models.ForeignKey(User)
    contract = models.ForeignKey(Contract, related_name='contract_register')
    status = models.CharField(max_length=255, default=INPUT_INVITATION_CODE, choices=STATUS)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    objects = ContractRegisterManager()

    def save(self, *args, **kwargs):
        """
        Add history when saving.
        """
        super(ContractRegister, self).save(*args, **kwargs)

        ContractRegisterHistory(
            user=self.user,
            contract=self.contract,
            status=self.status,
            created=self.created,
            modified=self.modified
        ).save()

    def is_input(self):
        """
        Check status of input.
        """
        return self.status == INPUT_INVITATION_CODE

    def is_registered(self):
        """
        Check status of register.
        """
        return self.status == REGISTER_INVITATION_CODE

    def is_unregistered(self):
        """
        Check status of unregister.
        """
        return self.status == UNREGISTER_INVITATION_CODE

    @classmethod
    def get_by_user_contract(cls, user, contract):
        """
        Get ContractRegister if exists.
        """
        try:
            return cls.objects.get(user=user, contract=contract)
        except cls.DoesNotExist:
            return None

    @classmethod
    def find_enabled_register_by_user(cls, user):
        """
        Get ContractRegister of registered and Contract enabled.
        """
        return cls.objects.enabled().filter(
            user=user,
            status=REGISTER_INVITATION_CODE
        )

    @classmethod
    def find_by_contract(cls, contract):
        return cls.objects.filter(contract=contract).select_related('user__profile').order_by('id')

    @classmethod
    def find_input_and_register_by_contract(cls, contract):
        return cls.objects.filter(
            contract=contract,
            status__in=[INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE]
        ).order_by('id')

    @classmethod
    def has_input_and_register_by_user_and_contract_ids(cls, user, contract_ids):
        """
        Check user has status of input or register, contract ids and enabled.
        """
        return cls.objects.enabled().filter(
            user=user.id,
            status__in=[INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE],
            contract__id__in=contract_ids
        ).exists()

    @classmethod
    def find_by_ids(cls, register_ids):
        return cls.objects.filter(id__in=register_ids)

    @classmethod
    def get_by_login_code_contract(cls, login_code, contract):
        try:
            return cls.objects.select_related('user').get(user__bizuser__login_code=login_code, contract=contract)
        except cls.DoesNotExist:
            return None


class ContractRegisterHistory(models.Model):
    """
    History of contract register for user
    """
    user = models.ForeignKey(User)
    contract = models.ForeignKey(Contract)
    status = models.CharField(max_length=255)
    created = models.DateTimeField()
    modified = models.DateTimeField()

    class Meta:
        app_label = 'ga_invitation'

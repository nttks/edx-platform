"""
Models for invitation feature
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _

from biz.djangoapps.ga_contract.models import Contract


INPUT_INVITATION_CODE = 'Input'
REGISTER_INVITATION_CODE = 'Register'

STATUS = (
    (INPUT_INVITATION_CODE, _('Input Invitation')),
    (REGISTER_INVITATION_CODE, _('Register Invitation'))
)


class AdditionalInfoSetting(models.Model):
    """
    AdditionalInfo for user settings
    """
    class Meta(object):
        """
        Meta info
        """
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
    def find_by_user_and_contract(cls, user, contract):
        """
        """
        return cls.objects.filter(user=user, contract=contract).order_by('id')


class ContractRegister(models.Model):

    """
    Contract register for user
    """
    class Meta(object):
        """
        Meta info
        """
        unique_together = ('contract', 'user')

    user = models.ForeignKey(User)
    contract = models.ForeignKey(Contract, related_name='contract_register')
    status = models.CharField(max_length=255, default=INPUT_INVITATION_CODE, choices=STATUS)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

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

    def is_registered(self):
        """
        Check status of register.
        """
        return self.status == REGISTER_INVITATION_CODE

    @classmethod
    def get_by_user_contract(cls, user, contract):
        """
        Get OntractRegister if exists.
        """
        try:
            return cls.objects.get(user=user, contract=contract)
        except cls.DoesNotExist:
            return None

    @classmethod
    def find_register_by_user(cls, user):
        """
        Get OntractRegister of registered.
        """
        return cls.objects.filter(user=user, status=REGISTER_INVITATION_CODE)

    @classmethod
    def find_registered_by_contract(cls, contract):
        return cls.objects.filter(contract=contract, status=REGISTER_INVITATION_CODE).order_by('id')

    @classmethod
    def has_input_and_register_by_user_and_contract_ids(cls, user, contract_ids):
        """
        Check user has status of input or register, and contract ids.
        """
        return cls.objects.filter(
            user=user.id,
            status__in=[INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE],
            contract__id__in=contract_ids
        ).exists()


class ContractRegisterHistory(models.Model):
    """
    History of contract register for user
    """
    user = models.ForeignKey(User)
    contract = models.ForeignKey(Contract)
    status = models.CharField(max_length=255)
    created = models.DateTimeField()
    modified = models.DateTimeField()

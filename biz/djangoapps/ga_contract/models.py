from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _

from biz.djangoapps.ga_manager.models import Manager
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.util import datetime_utils
from xmodule_django.models import CourseKeyField

CONTRACT_TYPE_PF = ('PF', _('PF Contract'))
CONTRACT_TYPE_OWNERS = ('O', _('Owners Contract'))
CONTRACT_TYPE_GACCO_SERVICE = ('GS', _('Gacco Service Contract'))
CONTRACT_TYPE_OWNER_SERVICE = ('OS', _('Owner Service Contract'))
CONTRACT_TYPE = (CONTRACT_TYPE_PF, CONTRACT_TYPE_OWNERS, CONTRACT_TYPE_GACCO_SERVICE, CONTRACT_TYPE_OWNER_SERVICE)


class ContractManager(models.Manager):
    def enabled(self, **kwargs):
        today = datetime_utils.timezone_today()
        return self.filter(start_date__lte=today, end_date__gte=today)


class ContractDetailManager(models.Manager):
    def enabled(self, **kwargs):
        today = datetime_utils.timezone_today()
        return self.filter(contract__start_date__lte=today, contract__end_date__gte=today)


class Contract(models.Model):
    """
    This table contains contract info.
    """
    contract_name = models.CharField(max_length=255)
    contract_type = models.CharField(max_length=255, choices=CONTRACT_TYPE)
    invitation_code = models.CharField(max_length=255, unique=True)
    contractor_organization = models.ForeignKey(Organization, related_name='org_contractor_contracts')
    owner_organization = models.ForeignKey(Organization, related_name='org_owner_contracts')
    start_date = models.DateField()
    end_date = models.DateField()
    created_by = models.ForeignKey(User)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = ContractManager()

    def is_enabled(self):
        """
        Check period of contract is available in this contract.
        """
        today = datetime_utils.timezone_today()
        return self.start_date <= today <= self.end_date

    def is_available_for_aggregator(self):
        """
        Returns whether Aggregator can use this contract.
        """
        return self.contract_type == CONTRACT_TYPE_OWNERS[0]

    def is_available_for_director_or_manager(self):
        """
        Returns whether Director or Manager can use this contract.
        """
        return self.contract_type in [
            CONTRACT_TYPE_PF[0],
            CONTRACT_TYPE_GACCO_SERVICE[0],
            CONTRACT_TYPE_OWNER_SERVICE[0],
        ]

    @property
    def is_spoc_available(self):
        """
        Returns whether SPOC is available in this contract.
        """
        return self.contract_type in [
            CONTRACT_TYPE_PF[0],
            CONTRACT_TYPE_OWNERS[0],
            CONTRACT_TYPE_OWNER_SERVICE[0],
        ]

    @classmethod
    def get_contract_types(cls, manager):
        """
        Get contract types related to manager's permissions

        :param manager: Manager object
        :return: list of contract types
        """
        contract_types = []
        if manager.is_aggregator():
            contract_types.append(CONTRACT_TYPE_OWNERS[0])
        if manager.is_director() or manager.is_manager():
            contract_types.append(CONTRACT_TYPE_PF[0])
            contract_types.append(CONTRACT_TYPE_GACCO_SERVICE[0])
            contract_types.append(CONTRACT_TYPE_OWNER_SERVICE[0])
        return contract_types

    @classmethod
    def get_contract_types_by_managers(cls, managers):
        """
        Get contract types related to managers' permissions

        :param managers: list of Manager
        :return: list of contract types
        """
        contract_types = []
        if any([manager.is_aggregator() for manager in managers]):
            contract_types.append(CONTRACT_TYPE_OWNERS[0])
        if any([manager.is_director() or manager.is_manager() for manager in managers]):
            contract_types.append(CONTRACT_TYPE_PF[0])
            contract_types.append(CONTRACT_TYPE_GACCO_SERVICE[0])
            contract_types.append(CONTRACT_TYPE_OWNER_SERVICE[0])
        return contract_types

    @classmethod
    def get_enabled_by_manager_and_contract_id(cls, manager, contract_id):
        """
        Get by contract types related to manager's permissions and contract id

        :param manager: Manager object
        :param contract_id: contract id
        :return: Contract object, or raise DoesNotExist if not exist
        """
        contract_types = cls.get_contract_types(manager)
        return cls.objects.enabled().get(
            pk=contract_id,
            contractor_organization__id=manager.org.id,
            contract_type__in=contract_types,
        )

    @classmethod
    def get_by_invitation_code(cls, invitation_code):
        try:
            return cls.objects.get(invitation_code=invitation_code)
        except cls.DoesNotExist:
            return None

    @classmethod
    def find_by_owner(cls, owner_org):
        return cls.objects.filter(owner_organization=owner_org).order_by('-created')

    @classmethod
    def find_enabled_by_contractor(cls, contractor_org_id):
        return cls.objects.enabled().filter(contractor_organization__id=contractor_org_id)

    @classmethod
    def find_enabled_by_user(cls, user):
        """
        Filter by contract types related to managers' permissions of user

        :param user: User object
        :return: Contract objects
        """
        managers = Manager.get_managers(user)
        contract_types = cls.get_contract_types_by_managers(managers)
        return cls.objects.enabled().filter(
            contractor_organization__managers__user=user,
            contract_type__in=contract_types,
        ).order_by('-created')

    @classmethod
    def find_enabled_by_manager(cls, manager):
        """
        Filter by contract types related to manager's permissions

        :param manager: Manager object
        :return: Contract objects
        """
        contract_types = cls.get_contract_types(manager)
        return cls.objects.enabled().filter(
            contractor_organization__id=manager.org.id,
            contract_type__in=contract_types,
        )


class ContractDetail(models.Model):
    """
    This table contains contract detail info.
    """
    contract = models.ForeignKey(Contract, related_name='details')
    course_id = CourseKeyField(max_length=255, db_index=True)

    objects = ContractDetailManager()

    class Meta:
        ordering = ['id']

    @classmethod
    def find_enabled(cls):
        return cls.objects.enabled().all().order_by('id')

    @classmethod
    def find_enabled_by_contractors(cls, contractor_orgs):
        return cls.objects.enabled().filter(contract__contractor_organization__in=contractor_orgs).order_by('id')

    @classmethod
    def find_enabled_by_user(cls, user):
        """
        Filter by contract types related to managers' permissions of user

        :param user: User object
        :return: ContractDetail objects
        """
        managers = Manager.get_managers(user)
        contract_types = Contract.get_contract_types_by_managers(managers)
        return cls.objects.enabled().filter(
            contract__contractor_organization__managers__user=user,
            contract__contract_type__in=contract_types,
        ).order_by('id')

    @classmethod
    def find_enabled_by_contract_id(cls, contract_id):
        return cls.objects.enabled().filter(
            contract__id=contract_id,
        ).order_by('id')

    @classmethod
    def find_enabled_by_contractor_and_contract_id(cls, contractor_org_id, contract_id):
        return cls.objects.enabled().filter(
            contract__id=contract_id,
            contract__contractor_organization__id=contractor_org_id,
        )

    @classmethod
    def find_enabled_by_manager_and_contract(cls, manager, contract):
        """
        Filter by contract types related to manager's permissions and contract id

        :param manager: Manager object
        :param contract: Contract object
        :return: ContractDetail objects
        """
        contract_types = Contract.get_contract_types(manager)
        return cls.objects.enabled().filter(
            contract__id=contract.id,
            contract__contract_type__in=contract_types,
            contract__contractor_organization__id=manager.org.id,
        )

    @classmethod
    def find_enabled_by_manager_and_contract_and_course(cls, manager, contract, course):
        """
        Filter by contract types related to manager's permissions and contract id and course key

        :param manager: Manager object
        :param contract: Contract object
        :param course: course object
        :return: ContractDetail objects
        """
        contract_types = Contract.get_contract_types(manager)
        return cls.objects.enabled().filter(
            course_id=course.id,
            contract__id=contract.id,
            contract__contract_type__in=contract_types,
            contract__contractor_organization__id=manager.org.id,
        )

    @classmethod
    def find_spoc_by_course_key(cls, course_key):
        return cls.objects.filter(
            course_id=course_key,
            contract__contract_type__in=[
                CONTRACT_TYPE_PF[0],
                CONTRACT_TYPE_OWNERS[0],
                CONTRACT_TYPE_OWNER_SERVICE[0],
            ],
        ).select_related('contract')

    @classmethod
    def find_all_spoc(cls):
        """
        Returns all of spoc contract details even if contact is not enabled.

        :return: ContractDetails objects
        """
        return cls.objects.filter(
            contract__contract_type__in=[
                CONTRACT_TYPE_PF[0],
                CONTRACT_TYPE_OWNERS[0],
                CONTRACT_TYPE_OWNER_SERVICE[0],
            ]
        ).select_related('contract')


class AdditionalInfo(models.Model):
    """
    This table contains user additional info.
    """
    contract = models.ForeignKey(Contract, related_name='additional_info')
    display_name = models.CharField(max_length=255)

    class Meta:
        ordering = ['id']
        unique_together = ("contract", "display_name")

    @classmethod
    def find_by_contract_id(cls, contract_id):
        """
        Filter additional info by contract id

        :param contract_id: contract id
        :return: AdditionalInfo objects
        """
        return cls.objects.filter(contract_id=contract_id).order_by('id')

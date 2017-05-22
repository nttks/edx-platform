from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models
from django.utils.translation import ugettext_lazy as _

from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.ga_invitation.models import ContractRegister
from openedx.core.djangoapps.ga_task.models import Task


class ContractTaskHistory(models.Model):

    contract = models.ForeignKey(Contract)
    # task_id will use in order to relate with Task instance. This is not required.
    task_id = models.CharField(max_length=255, db_index=True, null=True)
    requester = models.ForeignKey(User)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'ga_contract_operation'

    @classmethod
    def create(cls, contract, requester):
        return cls.objects.create(
            contract=contract,
            requester=requester
        )

    @classmethod
    def find_by_contract(cls, contract):
        return cls.objects.filter(contract=contract).order_by('-created')

    @classmethod
    def find_by_contract_with_task(cls, contract):
        histories = cls.find_by_contract(contract).exclude(task_id__isnull=True).select_related('requester')
        task_ids = [history.task_id for history in histories]
        tasks = {task.task_id: task for task in Task.objects.filter(task_id__in=task_ids)}
        for history in histories:
            if history.task_id and history.task_id in tasks:
                yield (history, tasks[history.task_id])
            else:
                yield (history, None)

    def link_to_task(self, task):
        """
        Link to Task instance.

        :param task: ga_task.Task instance
        """
        self.task_id = task.task_id
        self.save()


class ContractTaskTarget(models.Model):

    class Meta:
        app_label = 'ga_contract_operation'
        unique_together = ('history', 'register')

    history = models.ForeignKey(ContractTaskHistory)
    register = models.ForeignKey(ContractRegister)
    completed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    @classmethod
    def bulk_create(cls, history, registers):
        targets = [cls(
            history=history,
            register=register,
        ) for register in registers]
        cls.objects.bulk_create(targets)

    @classmethod
    def find_by_history_id(cls, history_id):
        return cls.objects.filter(
            history_id=history_id,
        ).select_related('register__user')

    @classmethod
    def is_completed_by_user_and_contract(cls, user, contract):
        """
        Returns whether an user is completed in the whole history of the contract.
        """
        return cls.objects.filter(
            history__contract=contract,
            register__user=user,
            completed=True
        ).exists()

    def complete(self):
        self.completed = True
        self.save()


class StudentRegisterTaskTarget(models.Model):

    history = models.ForeignKey(ContractTaskHistory)
    student = models.CharField(max_length=1024)
    message = models.CharField(max_length=1024, null=True)
    completed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'ga_contract_operation'
        ordering = ['id']

    @classmethod
    def bulk_create(cls, history, students):
        targets = [cls(
            history=history,
            student=student,
        ) for student in students]
        cls.objects.bulk_create(targets)

    @classmethod
    def find_by_history_id(cls, history_id):
        return cls.objects.filter(
            history_id=history_id,
        )

    @classmethod
    def find_by_history_id_and_message(cls, history_id):
        return cls.objects.filter(
            history_id=history_id,
            message__isnull=False,
        )

    def complete(self, message=None):
        if message:
            self.message = message
        self.completed = True
        self.save()

    def incomplete(self, message):
        self.message = message
        self.completed = False
        self.save()


MAIL_TYPE_REGISTER_NEW_USER = 'RNU'
MAIL_TYPE_REGISTER_EXISTING_USER = 'REU'
MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE = 'RNUWLC'
MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE = 'REUWLC'
MAIL_TYPE = (
    (MAIL_TYPE_REGISTER_NEW_USER, _("For New User")),
    (MAIL_TYPE_REGISTER_EXISTING_USER, _("For Existing User")),
    (MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE, _("For New User with Login Code")),
    (MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE, _("For Existing User with Login Code")),
)

MAIL_PARAM_USERNAME = ('username', _("Replaced with the user name"))
MAIL_PARAM_EMAIL_ADDRESS = ('email_address', _("Replaced with the user e-mail address"))
MAIL_PARAM_PASSWORD = ('password', _("Replaced with the user password"))
MAIL_PARAM_LOGINCODE = ('logincode', _("Replaced with the login code"))
MAIL_PARAM_URLCODE = ('urlcode', _("Replaced with the URL code for login"))
MAIL_PARAMS = {
    MAIL_TYPE_REGISTER_NEW_USER: [
        MAIL_PARAM_USERNAME,
        MAIL_PARAM_EMAIL_ADDRESS,
        MAIL_PARAM_PASSWORD,
    ],
    MAIL_TYPE_REGISTER_EXISTING_USER: [
        MAIL_PARAM_USERNAME,
        MAIL_PARAM_EMAIL_ADDRESS,
    ],
    MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE: [
        MAIL_PARAM_USERNAME,
        MAIL_PARAM_EMAIL_ADDRESS,
        MAIL_PARAM_PASSWORD,
        MAIL_PARAM_LOGINCODE,
        MAIL_PARAM_URLCODE,
    ],
    MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE: [
        MAIL_PARAM_USERNAME,
        MAIL_PARAM_EMAIL_ADDRESS,
        MAIL_PARAM_LOGINCODE,
        MAIL_PARAM_URLCODE,
    ],
}


class ContractMail(models.Model):

    contract = models.ForeignKey(Contract, default=None, null=True, blank=True)
    mail_type = models.CharField(max_length=255, choices=MAIL_TYPE)
    mail_subject = models.CharField(max_length=128)
    mail_body = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'ga_contract_operation'
        unique_together = ('contract', 'mail_type')

    def __unicode__(self):
        return u'{}:{}'.format(
            _("Default Template") if self.contract is None else contract.contract_name,
            self.mail_type_name,
        )

    @property
    def mail_type_name(self):
        return dict(MAIL_TYPE).get(self.mail_type, '')

    @property
    def mail_params(self):
        return {p[0]: p[1] for p in MAIL_PARAMS[self.mail_type]}

    @property
    def has_mail_param_password(self):
        return MAIL_PARAM_PASSWORD[0] in self.mail_params

    @classmethod
    def is_mail_type(cls, mail_type):
        return mail_type in dict(MAIL_TYPE).keys()

    @classmethod
    def get_or_default(cls, contract, mail_type):
        if not contract.can_customize_mail:
            return cls.objects.get(contract=None, mail_type=mail_type)
        try:
            return cls.objects.get(contract=contract, mail_type=mail_type)
        except cls.DoesNotExist:
            return cls.objects.get(contract=None, mail_type=mail_type)

    @classmethod
    def get_register_new_user(cls, contract):
        return cls.get_or_default(contract, MAIL_TYPE_REGISTER_NEW_USER)

    @classmethod
    def get_register_existing_user(cls, contract):
        return cls.get_or_default(contract, MAIL_TYPE_REGISTER_EXISTING_USER)

    @classmethod
    def get_register_new_user_logincode(cls, contract):
        return cls.get_or_default(contract, MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE)

    @classmethod
    def get_register_existing_user_logincode(cls, contract):
        return cls.get_or_default(contract, MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE)

    @classmethod
    def register_replace_dict(cls, user, contract, password=None, login_code=None):
        replace_dict = {
            MAIL_PARAM_USERNAME[0]: user.username,
            MAIL_PARAM_EMAIL_ADDRESS[0]: user.email,
        }
        if password is not None:
            replace_dict[MAIL_PARAM_PASSWORD[0]] = password
        if contract.has_auth:
            replace_dict[MAIL_PARAM_LOGINCODE[0]] = login_code or (user.bizuser.login_code if hasattr(user, 'bizuser') else '')
            replace_dict[MAIL_PARAM_URLCODE[0]] = contract.contractauth.url_code
        return replace_dict

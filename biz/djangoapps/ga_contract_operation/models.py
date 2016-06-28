
from django.contrib.auth.models import User
from django.db import models

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

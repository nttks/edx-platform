from django.db import models
from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.ga_contract_operation.models import ContractTaskHistory
from model_utils.models import TimeStampedModel

# Create your models here.
STUDENT_REGISTER_BATCH = 'student_register_batch'
STUDENT_UNREGISTER_BATCH = 'student_unregister_batch'


class BatchSendMailFlag(models.Model):
    class Meta:
        app_label = 'gx_students_register_batch'
    def __unicode__(self):
        return self.contract.contract_name + ' : send_mail_flag' + str(self.send_mail)

    contract = models.OneToOneField(Contract)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, null=True, blank=True)
    send_mail = models.BooleanField(default=False)

class BatchTargetBase(models.Model):
    """
    Contract task base
    """
    class Meta:
        app_label = 'gx_students_register_batch'
        abstract = True
        ordering = ['id']

    history = models.ForeignKey(ContractTaskHistory)
    message = models.CharField(max_length=1024, null=True)
    completed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

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


class StudentsRegisterBatchTarget(BatchTargetBase):

    student = models.CharField(max_length=1024)

    @classmethod
    def bulk_create(cls, history, students):
        targets = [cls(
            history=history,
            student=student,
        ) for student in students]
        cls.objects.bulk_create(targets)

class StudentsRegisterBatchHistory(models.Model):
    class Meta:
        app_label = 'gx_students_register_batch'

    key = models.CharField(max_length=255, null=True)
    message = models.CharField(max_length=255)
    org_id = models.IntegerField(null=True)
    contract_id = models.IntegerField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

class S3BucketName(TimeStampedModel):
    class Meta:
        app_label = 'gx_students_register_batch'

    def __unicode__(self):
        return self.bucket_name + ' : ' + str(self.type)

    bucket_name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)


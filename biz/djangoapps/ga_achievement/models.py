"""
Models for achievement feature
"""
from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _

from biz.djangoapps.ga_contract.models import Contract
from xmodule_django.models import CourseKeyField

BATCH_STATUS_STARTED = 'Started'
BATCH_STATUS_FINISHED = 'Finished'
BATCH_STATUS_ERROR = 'Error'
BATCH_STATUS = (
    (BATCH_STATUS_STARTED, _(BATCH_STATUS_STARTED)),
    (BATCH_STATUS_FINISHED, _(BATCH_STATUS_FINISHED)),
    (BATCH_STATUS_ERROR, _(BATCH_STATUS_ERROR)),
)


class BatchStatusBase(models.Model):
    """
    Batch status base
    """
    class Meta:
        abstract = True

    contract = models.ForeignKey(Contract)
    course_id = CourseKeyField(max_length=255, db_index=True)
    status = models.CharField(max_length=255, db_index=True, choices=BATCH_STATUS)
    student_count = models.IntegerField(null=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    @transaction.autocommit
    def save_now(self):
        """
        Writes BatchStatus immediately, ensuring the transaction is committed.

        Autocommit annotation makes sure the database entry is committed.
        When called from any view that is wrapped by TransactionMiddleware,
        and thus in a "commit-on-success" transaction, this autocommit here
        will cause any pending transaction to be committed by a successful
        save here.  Any future database operations will take place in a
        separate transaction.
        """
        self.save()

    @classmethod
    def get_last_status(cls, contract_id, course_id):
        """
        Get the last status

        :param contract_id: Contract id
        :param course_id: CourseKey
        :return: the last created BatchStatus object with specified ids
        """
        obj = cls.objects.filter(contract_id=contract_id, course_id=course_id).order_by('-created', '-id')[:1]
        if obj.exists():
            return obj[0]
        else:
            return None

    @classmethod
    def save_for_started(cls, contract_id, course_id):
        """
        Save status when batch has started

        :param contract_id: Contract id
        :param course_id: CourseKey
        :return: saved object
        """
        return cls(
            contract_id=contract_id,
            course_id=course_id,
            status=BATCH_STATUS_STARTED,
        ).save_now()

    @classmethod
    def save_for_finished(cls, contract_id, course_id, student_count):
        """
        Save status when batch has finished

        :param contract_id: Contract id
        :param course_id: CourseKey
        :param student_count: number of records which have been saved successfully
        :return: saved object
        """
        return cls(
            contract_id=contract_id,
            course_id=course_id,
            status=BATCH_STATUS_FINISHED,
            student_count=student_count,
        ).save_now()

    @classmethod
    def save_for_error(cls, contract_id, course_id):
        """
        Save status when batch has raised error

        :param contract_id: Contract id
        :param course_id: CourseKey
        :return: saved object
        """
        return cls(
            contract_id=contract_id,
            course_id=course_id,
            status=BATCH_STATUS_ERROR,
        ).save_now()


class ScoreBatchStatus(BatchStatusBase):
    """
    Batch status for score
    """
    pass


class PlaybackBatchStatus(BatchStatusBase):
    """
    Batch status for playback
    """
    pass

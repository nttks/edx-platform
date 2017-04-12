"""
Models for achievement feature
"""
import datetime

from django.db import models
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
        app_label = 'ga_achievement'
        abstract = True

    contract = models.ForeignKey(Contract)
    course_id = CourseKeyField(max_length=255, db_index=True)
    status = models.CharField(max_length=255, db_index=True, choices=BATCH_STATUS)
    student_count = models.IntegerField(null=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

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
    def exists_today(cls, contract_id):
        """
        Return whether today's record exists for the specified Contract id

        :param contract_id: Contract id
        :return: True if today's record exists for the specified Contract id
        """
        today_min = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
        today_max = datetime.datetime.combine(datetime.date.today(), datetime.time.max)
        return cls.objects.filter(contract_id=contract_id, created__gte=today_min, created__lte=today_max).exists()

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
        ).save()

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
        ).save()

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
        ).save()


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

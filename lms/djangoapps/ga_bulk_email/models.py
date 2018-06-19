"""
Models for bulk email.
"""
from django.db import models
from django.utils.translation import ugettext_lazy as _

from biz.djangoapps.util import datetime_utils
from xmodule_django.models import CourseKeyField

BATCH_STATUS_STARTED = 'Started'
BATCH_STATUS_FINISHED = 'Finished'
BATCH_STATUS_ERROR = 'Error'
BATCH_STATUS = (
    (BATCH_STATUS_STARTED, _(BATCH_STATUS_STARTED)),
    (BATCH_STATUS_FINISHED, _(BATCH_STATUS_FINISHED)),
    (BATCH_STATUS_ERROR, _(BATCH_STATUS_ERROR)),
)


class CourseBatchStatusBase(models.Model):
    """
    Batch status base for course
    """
    class Meta:
        app_label = 'ga_bulk_email'
        abstract = True

    course_id = CourseKeyField(max_length=255, db_index=True)
    status = models.CharField(max_length=255, db_index=True, choices=BATCH_STATUS)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    @classmethod
    def save_for_started(cls, course_id):
        """
        Save status when batch has started

        :param course_id: CourseKey
        :return: saved object
        """
        return cls(
            course_id=course_id,
            status=BATCH_STATUS_STARTED,
        ).save()


class SelfPacedCourseClosureReminderBatchStatus(CourseBatchStatusBase):
    """
    Batch status for reminder of closure for self-paced course
    """
    success_count = models.IntegerField(null=True)
    failure_count = models.IntegerField(null=True)

    @classmethod
    def save_for_finished(cls, course_id, success_count, failure_count):
        """
        Save status when batch has finished

        :param course_id: CourseKey
        :param success_count: number of records which have been processed successfully
        :param failure_count: number of records which have failed accidentally
        :return: saved object
        """
        return cls(
            course_id=course_id,
            status=BATCH_STATUS_FINISHED,
            success_count=success_count,
            failure_count=failure_count,
        ).save()

    @classmethod
    def save_for_error(cls, course_id, success_count=None, failure_count=None):
        """
        Save status when batch has raised error

        :param course_id: CourseKey
        :param success_count: number of records which have been processed successfully
        :param failure_count: number of records which have failed accidentally
        :return: saved object
        """
        return cls(
            course_id=course_id,
            status=BATCH_STATUS_ERROR,
            success_count=success_count,
            failure_count=failure_count,
        ).save()


class CourseMailBase(models.Model):
    """
    Abstract base class for mail settings for course 
    """
    class Meta(object):
        app_label = 'ga_bulk_email'
        abstract = True
        unique_together = ('course_id', 'mail_type')
        ordering = ['id']

    MAIL_TYPE = ()
    MAIL_PARAMS = {}

    mail_type = models.CharField(max_length=255)
    mail_subject = models.CharField(max_length=128)
    mail_body = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    course_id = CourseKeyField(max_length=255, db_index=True, default=None, blank=True, null=True)

    def __init__(self, *args, **kwargs):
        self._meta.get_field('mail_type')._choices = self.MAIL_TYPE
        super(CourseMailBase, self).__init__(*args, **kwargs)

    def __unicode__(self):
        return u'{}:{}'.format(
            _("Default Template") if self.course_id is None else self.course_id,
            self.mail_type_name,
        )

    @property
    def mail_type_name(self):
        return dict(self.MAIL_TYPE).get(str(self.mail_type), '')

    @property
    def mail_params(self):
        return {p[0]: p[1] for p in self.MAIL_PARAMS[str(self.mail_type)]}

    @classmethod
    def is_mail_type(cls, mail_type):
        return mail_type in dict(cls.MAIL_TYPE).keys()


class SelfPacedCourseClosureReminderMail(CourseMailBase):

    MAIL_TYPE_SELF_PACED_COURSE_CLOSURE_REMINDER = 'SPCCR'
    MAIL_TYPE = (
        (MAIL_TYPE_SELF_PACED_COURSE_CLOSURE_REMINDER, _("Closure reminder email for self-paced course")),
    )

    MAIL_PARAM_FULLNAME = ('fullname', _("Replaced with the full name"))
    MAIL_PARAM_COURSE_ID = ('course_id', _("Replaced with the course id"))
    MAIL_PARAM_COURSE_NAME = ('course_name', _("Replaced with the course name"))
    MAIL_PARAM_TERMINATE_DATE_JP = ('terminate_date_jp', _("Replaced with the terminate date of JP"))
    MAIL_PARAM_TERMINATE_DATE_EN = ('terminate_date_en', _("Replaced with the terminate date of EN"))
    MAIL_PARAMS = {
        MAIL_TYPE_SELF_PACED_COURSE_CLOSURE_REMINDER: [
            MAIL_PARAM_FULLNAME,
            MAIL_PARAM_COURSE_ID,
            MAIL_PARAM_COURSE_NAME,
            MAIL_PARAM_TERMINATE_DATE_JP,
            MAIL_PARAM_TERMINATE_DATE_EN,
        ],
    }

    REMINDER_EMAIL_DAYS_MIN_VALUE = 1
    REMINDER_EMAIL_DAYS_MAX_VALUE = 14

    reminder_email_days = models.IntegerField(null=True)

    @classmethod
    def get_or_default(cls, course_id, mail_type):
        query = cls.objects.filter(course_id=course_id, mail_type=mail_type)
        if query.exists():
            return query[0]

        # Not found for specified course_id, get default
        query = cls.objects.filter(course_id=CourseKeyField.Empty, mail_type=mail_type)
        if query.exists():
            return query[0]

        return None

    @classmethod
    def replace_dict(cls, fullname, course_id, course_name, terminate_date_jp, terminate_date_en):
        def convert_utf8(s):
            return s if isinstance(s, str) else s.encode('utf-8')

        fullname = convert_utf8(fullname)
        course_id = convert_utf8(course_id)
        course_name = convert_utf8(course_name)
        terminate_date_jp = convert_utf8(terminate_date_jp)
        terminate_date_en = convert_utf8(terminate_date_en)

        replace_dict = {
            cls.MAIL_PARAM_FULLNAME[0]: fullname,
            cls.MAIL_PARAM_COURSE_ID[0]: course_id,
            cls.MAIL_PARAM_COURSE_NAME[0]: course_name,
            cls.MAIL_PARAM_TERMINATE_DATE_JP[0]: terminate_date_jp,
            cls.MAIL_PARAM_TERMINATE_DATE_EN[0]: terminate_date_en,
        }
        return replace_dict

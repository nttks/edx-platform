import hashlib
import json
import logging
from collections import OrderedDict
from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models

from xmodule_django.models import CourseKeyField

log = logging.getLogger(__name__)


class DiagnosisInfo(models.Model):
    """
    Creates the database table model.
    """

    user = models.ForeignKey(User)
    course_id = CourseKeyField(max_length=255, db_index=True)
    finished = models.BooleanField(default=False)
    finished_date = models.DateTimeField(null=True)
    regulation_state = models.IntegerField(null=True)

    timestamp1 = models.DateTimeField(null=True, blank=True)
    timestamp2_1 = models.DateTimeField(null=True, blank=True)
    timestamp2_2 = models.DateTimeField(null=True, blank=True)
    timestamp3 = models.DateTimeField(null=True, blank=True)
    timestamp4 = models.DateTimeField(null=True, blank=True)

    block1_01_1 = models.CharField(blank=True, max_length=255)
    block1_01_2 = models.CharField(blank=True, max_length=255)
    block1_02_1 = models.CharField(blank=True, max_length=255)
    block1_02_2 = models.CharField(blank=True, max_length=255)
    block1_03 = models.CharField(blank=True, max_length=2)
    block1_04_1 = models.CharField(blank=True, max_length=4)
    block1_04_2 = models.CharField(blank=True, max_length=2)
    block1_04_3 = models.CharField(blank=True, max_length=2)
    block1_05 = models.EmailField(blank=True, max_length=75)

    block2_01 = models.CharField(blank=True, max_length=16)
    block2_02 = models.CharField(blank=True, max_length=1)
    block2_03 = models.CharField(blank=True, max_length=1)
    block2_04 = models.CharField(blank=True, max_length=1)
    block2_05 = models.CharField(blank=True, max_length=1)
    block2_06 = models.CharField(blank=True, max_length=1)
    block2_07 = models.CharField(blank=True, max_length=1)
    block2_08 = models.CharField(blank=True, max_length=1)
    block2_09 = models.CharField(blank=True, max_length=1)
    block2_10 = models.CharField(blank=True, max_length=1)
    block2_11 = models.CharField(blank=True, max_length=1)
    block2_12 = models.CharField(blank=True, max_length=1)
    block2_13 = models.CharField(blank=True, max_length=1)
    block2_14 = models.CharField(blank=True, max_length=1)
    block2_15 = models.CharField(blank=True, max_length=1)
    block2_16 = models.CharField(blank=True, max_length=1)
    block2_17 = models.CharField(blank=True, max_length=1)
    block2_18 = models.CharField(blank=True, max_length=1)
    block2_19 = models.CharField(blank=True, max_length=1)
    block2_20 = models.CharField(blank=True, max_length=1)
    block2_21 = models.CharField(blank=True, max_length=1)
    block2_22 = models.CharField(blank=True, max_length=1)
    block2_23 = models.CharField(blank=True, max_length=1)
    block2_24 = models.CharField(blank=True, max_length=1)
    block2_25 = models.CharField(blank=True, max_length=1)
    block2_26 = models.CharField(blank=True, max_length=1)
    block2_27 = models.CharField(blank=True, max_length=1)

    block2b_3 = models.CharField(blank=True, max_length=3)

    block3_01 = models.CharField(blank=True, max_length=255)
    block3_02 = models.CharField(blank=True, max_length=255)
    block3_03_1 = models.CharField(blank=True, max_length=5)
    block3_03_2 = models.CharField(blank=True, max_length=5)
    block3_03_3 = models.CharField(blank=True, max_length=5)
    block3_04 = models.CharField(blank=True, max_length=255)
    block3_05 = models.CharField(blank=True, max_length=255)
    block3_06 = models.CharField(blank=True, max_length=255)
    block3_07 = models.CharField(blank=True, max_length=3)
    block3_08 = models.CharField(blank=True, max_length=255)
    block3_09_1 = models.CharField(blank=True, max_length=4)
    block3_09_2 = models.CharField(blank=True, max_length=2)
    block3_09_3 = models.CharField(blank=True, max_length=4)
    block3_09_4 = models.CharField(blank=True, max_length=2)
    block3_10 = models.CharField(blank=True, max_length=20)
    block3_11 = models.CharField(blank=True, max_length=20)
    block3_12 = models.CharField(blank=True, max_length=4)
    block3_13 = models.CharField(blank=True, max_length=4)
    block3_14 = models.CharField(blank=True, max_length=20)
    block3_15 = models.CharField(blank=True, max_length=255)
    block3_16 = models.CharField(blank=True, max_length=1024)
    block3_17 = models.CharField(blank=True, max_length=255)
    block3_18 = models.CharField(blank=True, max_length=4)
    block3_19 = models.CharField(blank=True, max_length=4)

    REGULATION_A = u'1'
    REGULATION_B = u'2'

    TIMESTAMP1 = 'timestamp1'
    TIMESTAMP2_1 = 'timestamp2_1'
    TIMESTAMP2_2 = 'timestamp2_2'
    TIMESTAMP3 = 'timestamp3'
    TIMESTAMP4 = 'timestamp4'

    def set_timestamp(self, timestamp_id):
        now = datetime.now()
        if self.TIMESTAMP1 == timestamp_id:
            self.timestamp1 = now
        elif self.TIMESTAMP2_1 == timestamp_id:
            self.timestamp2_1 = now
        elif self.TIMESTAMP2_2 == timestamp_id:
            self.timestamp2_2 = now
        elif self.TIMESTAMP3 == timestamp_id:
            self.timestamp3 = now
        elif self.TIMESTAMP4 == timestamp_id:
            self.timestamp4 = now

    def set_finished(self):
        self.finished = True
        self.finished_date = datetime.now()

    def get_score(self):
        result = OrderedDict()
        offset, basis = settings.GA_DIAGNOSIS_SCORE_BASIS
        for key, n in sorted(basis.items()):
            result[key] = sum(
                [int(getattr(self, 'block2_{:02d}'.format(i))) for i in range(offset, offset + n)]
            )
            offset += n
        result[self.AVERAGE_E] = eval(settings.GA_DIAGNOSIS_CALC_E.format(**result))
        return result

    def get_average(self, is_pre_result):
        assert self.block2_01
        if is_pre_result:
            return Average.get_average(code=settings.GA_DIAGNOSIS_STANDARD_AVERAGE_CODE, param=self.block2_01)
        else:
            assert self.block3_18
            return Average.get_average(code=self.block3_18, param=self.block2_01)

    def get_chart_data(self, is_pre_result):
        return [
            settings.GA_DIAGNOSIS_DATA2,
            [
                [v for v in self.get_score().values()],
                [float(v) for v in self.get_average(is_pre_result).values()],
            ],
        ]

    AVERAGE_A = 'A'
    AVERAGE_B = 'B'
    AVERAGE_C = 'C'
    AVERAGE_D = 'D'
    AVERAGE_E = 'E'
    THINK_AB = 'AB'
    THINK_CD = 'CD'
    THINK_AD = 'AD'
    THINK_BC = 'BC'

    @classmethod
    def get_think(cls, point_dict):
        return {
            cls.THINK_AB: eval(settings.GA_DIAGNOSIS_CHART_AB.format(**point_dict)),
            cls.THINK_CD: eval(settings.GA_DIAGNOSIS_CHART_CD.format(**point_dict)),
            cls.THINK_AD: eval(settings.GA_DIAGNOSIS_CHART_AD.format(**point_dict)),
            cls.THINK_BC: eval(settings.GA_DIAGNOSIS_CHART_BC.format(**point_dict)),
        }

    @classmethod
    def is_finished(cls, user, course_key):
        try:
            return cls.objects.get(user=user, course_id=course_key).finished
        except cls.DoesNotExist:
            return False

    class Meta:
        app_label = 'ga_diagnosis'
        unique_together = ('user', 'course_id')


class Average(models.Model):
    code = models.CharField(max_length=4, db_index=True, unique=True)
    average01 = models.CharField(max_length=255)
    average02 = models.CharField(max_length=255)
    average03 = models.CharField(max_length=255)
    average04 = models.CharField(max_length=255)
    average05 = models.CharField(max_length=255)
    average06 = models.CharField(max_length=255)
    average07 = models.CharField(max_length=255)
    average08 = models.CharField(max_length=255)
    average09 = models.CharField(max_length=255)
    average10 = models.CharField(max_length=255)
    average11 = models.CharField(max_length=255)
    average12 = models.CharField(max_length=255)
    average13 = models.CharField(max_length=255)

    @classmethod
    def get_average(cls, code, param):
        for i, data_list in enumerate(settings.GA_DIAGNOSIS_DATA1):
            if data_list[0] <= int(param) <= data_list[1]:
                average = cls.objects.get(code=code)
                tmp = json.loads(getattr(average, 'average{:02d}'.format(i + 1)))
                return OrderedDict(sorted(tmp.items()))
        raise ValueError

    class Meta:
        app_label = 'ga_diagnosis'


class GeneratePDFState(models.Model):
    downloadable = 'downloadable'
    error = 'error'
    generating = 'generating'

    diagnosis_info = models.OneToOneField(DiagnosisInfo)
    download_url = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=32, default=generating)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    error_reason = models.CharField(max_length=512, blank=True, default='')
    key = models.CharField(max_length=32, blank=True, default='')

    @staticmethod
    def make_hashkey(seed):
        """
        Generate a string key by hashing
        """
        md5 = hashlib.md5()
        md5.update(str(seed))
        return md5.hexdigest()

    def async_generate_pdf(self):
        # The following import here to prevent circular reference detected.
        from .tasks import perform_create_pdf

        try:
            perform_create_pdf.delay(diagnosis_info_id=self.diagnosis_info.id)
        except Exception as e:
            # zabbix hook
            log.error('ga_diagnosis: Notify Celery task operation was failed(sender). DiagnosisInfo.id={}'.format(
                self.diagnosis_info.id
            ))
            log.exception(u'Caught some Exception\n{}'.format(e))
            error_message = u'Notify Celery task operation was failed\n{}\nDiagnosisInfo.id={},username={}'.format(
                e,
                self.diagnosis_info.id,
                self.diagnosis_info.user.username,
            )
            self.status = self.error
            self.error_reason = error_message
            self.save()
            send_mail(
                subject='ga_diagnosis: Notify Celery task (perform_create_pdf) operation was failed.',
                message=error_message,
                from_email=settings.GA_DIAGNOSIS_SERVICE_SUPPORT_SENDER,
                recipient_list=settings.GA_DIAGNOSIS_SERVICE_SUPPORT_EMAIL,
            )

    class Meta:
        app_label = 'ga_diagnosis'

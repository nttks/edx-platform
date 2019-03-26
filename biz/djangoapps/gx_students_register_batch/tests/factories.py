from factory.django import DjangoModelFactory
from biz.djangoapps.gx_students_register_batch.models import BatchSendMailFlag, StudentsRegisterBatchHistory, S3BucketName, StudentsRegisterBatchTarget

class BatchSendMailFlagFactory(DjangoModelFactory):
    class Meta(object):
        model = BatchSendMailFlag


class StudentsRegisterBatchHistoryFactory(DjangoModelFactory):
    class Meta(object):
        model = StudentsRegisterBatchHistory


class StudentsRegisterBatchTargetFactory(DjangoModelFactory):
    class Meta(object):
        model = StudentsRegisterBatchTarget


class S3BucketNameFactory(DjangoModelFactory):
    class Meta(object):
        model = S3BucketName
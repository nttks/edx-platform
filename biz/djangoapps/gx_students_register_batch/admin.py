from django.contrib import admin
from biz.djangoapps.gx_students_register_batch.models import BatchSendMailFlag, S3BucketName

# Register your models here.
class BatchSendMailFlagAdmin(admin.ModelAdmin):
    pass


class S3BucketNameAdmin(admin.ModelAdmin):
    pass


admin.site.register(BatchSendMailFlag)
admin.site.register(S3BucketName)



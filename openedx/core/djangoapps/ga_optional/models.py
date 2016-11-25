
from django.db import models
from django.utils.translation import ugettext_lazy as _

from config_models.models import ConfigurationModel
from xmodule_django.models import CourseKeyField


OPTIONAL_FEATURES = [
    ('ora2-staff-assessment', _("Staff Assessment for Peer Grading")),
]


class CourseOptionalConfiguration(ConfigurationModel):

    KEY_FIELDS = ('key', 'course_key', )

    key = models.CharField(max_length=100, choices=OPTIONAL_FEATURES, db_index=True, verbose_name=_("Feature"))
    course_key = CourseKeyField(max_length=255, db_index=True, verbose_name=_("Course ID"))

    class Meta(object):
        app_label = "ga_optional"
        verbose_name = _("Settings for the course optional feature")
        verbose_name_plural = _("Settings for the course optional feature")

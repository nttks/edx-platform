
from django.db import models
from django.utils.translation import get_language, ugettext_lazy as _

from config_models.models import ConfigurationModel
from xmodule_django.models import CourseKeyField

CUSTOM_LOGO_OPTION_KEY = 'custom-logo-for-settings'
OPTIONAL_FEATURES = [
    ('ora2-staff-assessment', _("Staff Assessment for Peer Grading")),
    (CUSTOM_LOGO_OPTION_KEY, _("Custom Logo for Settings")),
]


class CourseOptionalConfiguration(ConfigurationModel):

    KEY_FIELDS = ('key', 'course_key', )

    key = models.CharField(max_length=100, choices=OPTIONAL_FEATURES, db_index=True, verbose_name=_("Feature"))
    course_key = CourseKeyField(max_length=255, db_index=True, verbose_name=_("Course ID"))

    class Meta(object):
        app_label = "ga_optional"
        verbose_name = _("Settings for the course optional feature")
        verbose_name_plural = _("Settings for the course optional feature")


DASHBOARD_OPTIONAL_FEATURES = [
    ('view-course-button', _("View course button for Mypage")),
]


class DashboardOptionalConfiguration(ConfigurationModel):
    KEY_FIELDS = ('key', 'course_key', )

    key = models.CharField(max_length=255, choices=DASHBOARD_OPTIONAL_FEATURES, verbose_name=_("Feature"))
    course_key = CourseKeyField(max_length=255, db_index=True, verbose_name=_("Course ID"))
    parts_title_en = models.CharField(blank=True, max_length=255, verbose_name=_("Parts Title (EN)"))
    parts_title_ja = models.CharField(blank=True, max_length=255, verbose_name=_("Parts Title (JP)"))
    href = models.CharField(null=True, max_length=255, verbose_name=_("href"))

    @classmethod
    def get_dict(cls, key, course_key):
        conf = cls.current(key, course_key)
        return {
            'parts_title': conf.parts_title_ja if get_language() in ['ja', 'ja-jp'] else conf.parts_title_en,
            'href': conf.href,
        } if conf.enabled else {}

    class Meta(object):
        app_label = "ga_optional"
        verbose_name = _("Settings for mypage optional feature")
        verbose_name_plural = _("Settings for mypage optional feature")


from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import get_language, ugettext_lazy as _

from config_models.models import ConfigurationModel, ConfigurationModelManager
from xmodule_django.models import CourseKeyField

CUSTOM_LOGO_OPTION_KEY = 'custom-logo-for-settings'
DISCCUSION_IMAGE_UPLOAD_KEY = 'disccusion-image-upload-settings'
LIBRARY_OPTION_KEY = 'library-for-settings'
PROGRESS_RESTRICTION_OPTION_KEY = 'progress-restriction-settings'
OPTIONAL_FEATURES = [
    ('ora2-staff-assessment', _("Staff Assessment for Peer Grading")),
    (CUSTOM_LOGO_OPTION_KEY, _("Custom Logo for Settings")),
    (DISCCUSION_IMAGE_UPLOAD_KEY, _("Providing Image Server for Discussion")),
    (LIBRARY_OPTION_KEY, _("Library for Settings")),
    (PROGRESS_RESTRICTION_OPTION_KEY, _("Progress Restriction by Correct Answer Rate")),
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


class UserOptionalConfigurationManager(ConfigurationModelManager):
    def current_set(self):
        """
        extends ConfigurationModelManager.
        Because where block's `id` is not identify it.
        --  OperationalError: (1052, "Column 'id' in IN/ALL/ANY subquery is ambiguous")
        """
        assert self.model.KEY_FIELDS != (), "Just use model.current() if there are no KEY_FIELDS"
        return self.get_queryset().extra(           # pylint: disable=no-member
            where=["`{tablename}`.id IN ({subquery})".format(tablename=self.model._meta.db_table, subquery=self._current_ids_subquery())],
            select={'is_active': 1},  # This annotation is used by the admin changelist. sqlite requires '1', not 'True'
        )

    def with_active_flag(self):
        """
        extends ConfigurationModelManager.
        Because where block's `id` is not identify it.
        --  OperationalError: (1052, "Column 'id' in IN/ALL/ANY subquery is ambiguous")
        """
        if self.model.KEY_FIELDS:
            subquery = self._current_ids_subquery()
            return self.get_queryset().extra(           # pylint: disable=no-member
                select={'is_active': "`{tablename}`.id IN ({subquery})".format(tablename=self.model._meta.db_table, subquery=subquery)}
            )
        else:
            return self.get_queryset().extra(           # pylint: disable=no-member
                select={'is_active': "`{tablename}`.id = {pk}".format(tablename=self.model._meta.db_table, pk=self.model.current().pk)}
            )


USERPOFILE_OPTION_KEY = 'hide-email-settings'
OPTIONAL_USEROPTIONAL_FEATURES = [
    (USERPOFILE_OPTION_KEY, _("Hide the e-mail on the Account Settings")),
]


class UserOptionalConfiguration(ConfigurationModel):

    KEY_FIELDS = ('key', 'user_id', )

    key = models.CharField(max_length=100, choices=OPTIONAL_USEROPTIONAL_FEATURES, db_index=True, verbose_name=_("Feature"))
    user = models.ForeignKey(User, related_name="useroptional", verbose_name=_("Username"))

    objects = UserOptionalConfigurationManager()

    class Meta(object):
        app_label = "ga_optional"
        verbose_name = _("Settings for the user optional feature")
        verbose_name_plural = _("Settings for the user optional feature")

    @classmethod
    def is_available(cls, key, user=None):
        if user is not None:
            return cls.current(key, user.id).enabled
        return False

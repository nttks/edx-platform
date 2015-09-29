from factory.django import DjangoModelFactory

from openedx.core.djangoapps.course_global.models import CourseGlobalSetting


class CourseGlobalSettingFactory(DjangoModelFactory):
    """
    Factory for the CourseGlobalSetting model.
    """
    class Meta(object):
        model = CourseGlobalSetting

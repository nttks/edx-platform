from factory.django import DjangoModelFactory

from ga_bulk_email.models import SelfPacedCourseClosureReminderMail


class SelfPacedCourseClosureReminderMailFactory(DjangoModelFactory):
    """Factory for the SelfPacedCourseClosureReminderMail model"""

    class Meta(object):
        model = SelfPacedCourseClosureReminderMail

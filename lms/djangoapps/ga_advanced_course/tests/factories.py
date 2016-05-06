from datetime import date, timedelta
import time

from django.utils import timezone

from factory.django import DjangoModelFactory

from opaque_keys.edx.locator import CourseLocator
from ..models import AdvancedF2FCourse, AdvancedCourseTicket


class AdvancedF2FCourseFactory(DjangoModelFactory):
    FACTORY_FOR = AdvancedF2FCourse

    course_id = CourseLocator('org', 'course', 'run')
    display_name = 'test display_name'
    start_date = date.today()
    start_time = time.strftime('%H:%M:%S', time.gmtime())
    end_time = time.strftime('%H:%M:%S', time.gmtime())
    capacity = 10
    description = 'test desctiption'
    content = 'test content'
    place_name = 'test place'
    place_link = 'http://example.com'
    place_address = 'test address'
    place_access = 'test access'


class AdvancedCourseTicketFactory(DjangoModelFactory):
    FACTORY_FOR = AdvancedCourseTicket

    display_name = 'test event_ticket'
    sell_by_date = timezone.now() + timedelta(days=1)

import json
import pytz
from datetime import datetime
from opaque_keys.edx.keys import UsageKey
from student.models import CourseEnrollment, CourseEnrollmentAttribute
from courseware.models import StudentModule
from ga_survey.models import SurveySubmission
from lms.djangoapps.courseware.ga_mongo_utils import PlaybackFinishStore


class AttendanceStatusExecutor(object):
    """
    ex: executor = AttendanceStatusExecutor(enrollment=enrollment)
    """
    NAMESPACE = 'ga'
    NAME = 'attended_status'
    KEY_ATTENDED_DATE = 'attended_date'
    KEY_COMPLETE_DATE = 'completed_date'

    def __init__(self, enrollment):
        """
        :param enrollment: CourseEnrollment.objects.get()
        """
        self.enrollment = enrollment
        # get coruse_enrollment
        try:
            self.attr = CourseEnrollmentAttribute.objects.filter(
                enrollment=self.enrollment, namespace=self.NAMESPACE, name=self.NAME).last()
        except CourseEnrollmentAttribute.DoesNotExist:
            self.attr = None

    @property
    def has_attr(self):
        """
        Check exist CourseEnrollmentAttribute data.
        """
        return self.attr is not None

    @property
    def is_attended(self):
        """
        ex: AttendanceStatusUtil(enrollment).is_attended
        """
        result = False
        if self.has_attr:
            json_dict = json.loads(self.attr.value)
            if self.KEY_ATTENDED_DATE in json_dict and json_dict[self.KEY_ATTENDED_DATE]:
                result = True
        return result

    @property
    def is_completed(self):
        """
        ex: AttendanceStatusUtil(enrollment).is_completed
        """
        result = False
        if self.has_attr:
            json_dict = json.loads(self.attr.value)
            if self.KEY_COMPLETE_DATE in json_dict and json_dict[self.KEY_COMPLETE_DATE]:
                result = True
        return result

    def get_attended_datetime(self):
        attended_datetime = None
        if self.is_attended:
            attr_value = json.loads(self.attr.value)
            attended_datetime = datetime.strptime(attr_value[self.KEY_ATTENDED_DATE][0:26], '%Y-%m-%dT%H:%M:%S.%f')
            attended_datetime = pytz.UTC.localize(attended_datetime)

        return attended_datetime

    def get_completed_datetime(self):
        attended_datetime = None
        if self.is_completed:
            attr_value = json.loads(self.attr.value)
            attended_datetime = datetime.strptime(attr_value[self.KEY_COMPLETE_DATE][0:26], '%Y-%m-%dT%H:%M:%S.%f')
            attended_datetime = pytz.UTC.localize(attended_datetime)

        return attended_datetime

    def set_attended(self, attended_date):
        """
        ex: AttendanceStatusUtil(enrollment).set_attended(datetime.now())
        :param attended_date: date
        """
        self._set(self.KEY_ATTENDED_DATE, attended_date)

    def set_completed(self, completed_date):
        """
        ex: AttendanceStatusUtil(enrollment).set_completed(datetime.now())
        :param completed_date: date
        """
        self._set(self.KEY_COMPLETE_DATE, completed_date)

    @staticmethod
    def check_attendance_status(course, user_id):

        return_flg = True

        if course.is_status_managed:
            for chapter in course.get_children():
                for section in chapter.get_children():
                    for vertical in section.get_children():
                        for module in vertical.get_children():
                            if hasattr(module, 'is_status_managed') and module.is_status_managed:
                                if module.location.category == 'html':
                                    if SurveySubmission.objects.filter(
                                            course_id=course.id,
                                            unit_id=vertical.location.block_id,
                                            user=user_id
                                    ).count() is 0:
                                        return_flg = False
                                        break
                                if module.location.category == 'problem':
                                    module_state_key = UsageKey.from_string(module.location.to_deprecated_string())
                                    if StudentModule.objects.filter(
                                            module_state_key=module_state_key,
                                            module_type__exact='problem',
                                            student=user_id,
                                            course_id=course.id,
                                            grade__isnull=False
                                    ).count() is 0:
                                        return_flg = False
                                        break
                                if module.location.category in ['video', 'jwplayerxblock']:
                                    if not PlaybackFinishStore().find_status_true_data(user_id, unicode(course.id),
                                                                                       module.location.block_id):
                                        return_flg = False
                                        break
                                if not return_flg:
                                    break
                            if not return_flg:
                                break
                        if not return_flg:
                            break
                    if not return_flg:
                        break
                if not return_flg:
                    break
        return return_flg

    def get_attendance_status_str(self, course, user):
        now = datetime.now(pytz.UTC)
        # check 'previous'
        if course.start and course.start > now:
            return 'previous'

        student_module_count = StudentModule.objects.filter(student=user, course_id=course.id).count()
        is_course_end = True if course.end and course.end < now else False

        if student_module_count or self.is_attended:
            if course.is_status_managed and self.is_completed:
                return 'completed'
            else:
                return 'closing' if is_course_end else 'working'
        else:
            return 'closing' if is_course_end else 'waiting'

    def _set(self, key, date):
        if self.has_attr:
            attr_value = json.loads(self.attr.value)
            attr_value[key] = date.isoformat()
            self.attr.value = json.dumps(attr_value)
            self.attr.save()
        else:
            self.attr = CourseEnrollmentAttribute.objects.create(
                enrollment=self.enrollment,
                namespace=self.NAMESPACE,
                name=self.NAME,
                value=json.dumps({key: date.isoformat()})
            )

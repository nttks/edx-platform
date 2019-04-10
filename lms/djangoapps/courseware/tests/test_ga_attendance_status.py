from pytz import UTC
from freezegun import freeze_time
from datetime import datetime
from nose.plugins.attrib import attr
from biz.djangoapps.ga_organization.tests.factories import OrganizationFactory
from courseware.tests.factories import StudentModuleFactory, PlaybackFinishFactory
from ga_survey.tests.factories import SurveySubmissionFactory
from lms.djangoapps.courseware.tests.test_ga_mongo_utils import PlaybackFinishTestBase
from student.models import CourseEnrollmentAttribute
from student.tests.factories import UserFactory, CourseEnrollmentFactory, CourseEnrollmentAttributeFactory
from util.ga_attendance_status import AttendanceStatusExecutor
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory


@attr('shard_1')
class AttendanceStatusExecutorTests(ModuleStoreTestCase, PlaybackFinishTestBase):
    """
    Test for common/djangoapps/util/ga_attendance_status.py
    Note: Put this tests file on 'lms' because do not test at 'cms'.
    """

    def setUp(self):
        super(AttendanceStatusExecutorTests, self).setUp()
        self.user = UserFactory.create()
        self.gacco_org = OrganizationFactory.create(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,
            created_by=UserFactory.create(),
        )
        self.course = CourseFactory.create(
            org='gacco', number='course', run='run1', start=datetime(2000, 3, 3, tzinfo=UTC),
            end=datetime(2001, 3, 3, tzinfo=UTC))
        self.enrollment = CourseEnrollmentFactory(user=self.user, course_id=self.course.id)

    """
    Test for init on when multi records exists
    """
    def test_init_when_multi_records_exits(self):
        # arrange
        attr1 = CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='sample1')
        attr2 = CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='sample2')
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        # assert
        self.assertEqual(executor.attr.id, attr1.id)
        self.assertEqual(1, CourseEnrollmentAttribute.objects.filter(
            enrollment=self.enrollment, namespace='ga', name='attended_status').count())

    """
    Test for get_attended_datetime
    """
    def test_get_attended_datetime(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value='{"attended_date": "2010-03-15T10:01:20.123456+00:00"}')
        # act
        act = AttendanceStatusExecutor(enrollment=self.enrollment).get_attended_datetime()
        # assert
        self.assertEqual(act.isoformat(), '2010-03-15T10:01:20.123456+00:00')

    """
    Test for get_attended_datetime
    """
    def test_get_completed_datetime(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value='{"completed_date": "2010-03-15T10:01:20.123456+00:00"}')
        # act
        act = AttendanceStatusExecutor(enrollment=self.enrollment).get_completed_datetime()
        # assert
        self.assertEqual(act.isoformat(), '2010-03-15T10:01:20.123456+00:00')

    """
    Test for is_attended
    """
    def test_is_attended_true(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='{"attended_date": "test"}')
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        # assert
        self.assertTrue(executor.is_attended)

    def test_is_attended_false_when_attr_none(self):
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        # assert
        self.assertFalse(executor.is_attended)

    def test_is_attended_false_when_value_is_empty(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='{}')
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        # assert
        self.assertFalse(executor.is_attended)

    """
    Test for is_completed
    """
    def test_is_completed_true(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='{"completed_date": "test"}')
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        # assert
        self.assertTrue(executor.is_completed)

    def test_is_completed_false_when_attr_none(self):
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        # assert
        self.assertFalse(executor.is_completed)

    def test_is_completed_false_when_value_is_empty(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='{}')
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        # assert
        self.assertFalse(executor.is_completed)

    """
    Test for set_attended
    """
    def test_set_attended_create(self):
        # act
        AttendanceStatusExecutor(enrollment=self.enrollment).set_attended(datetime(2013, 9, 18, 11, 30, 00))
        # assert
        self.assertEqual(1, CourseEnrollmentAttribute.objects.filter(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value='{"attended_date": "2013-09-18T11:30:00"}').count())

    def test_set_attended_update(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value=u'{"attended_date": "test"}')
        # act
        AttendanceStatusExecutor(enrollment=self.enrollment).set_attended(datetime(2013, 9, 18, 11, 30, 00))
        # assert
        self.assertEqual(1, CourseEnrollmentAttribute.objects.filter(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value='{"attended_date": "2013-09-18T11:30:00"}').count())

    """
    Test for set_completed
    """
    def test_set_completed_create(self):
        # act
        AttendanceStatusExecutor(enrollment=self.enrollment).set_completed(datetime(2013, 9, 18, 11, 30, 00))
        # assert
        self.assertEqual(1, CourseEnrollmentAttribute.objects.filter(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value='{"completed_date": "2013-09-18T11:30:00"}').count())

    def test_set_completed_update(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value='{"completed_date": "test"}')
        # act
        AttendanceStatusExecutor(enrollment=self.enrollment).set_completed(datetime(2013, 9, 18, 11, 30, 00))
        # assert
        self.assertEqual(1, CourseEnrollmentAttribute.objects.filter(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value='{"completed_date": "2013-09-18T11:30:00"}').count())

    """
    Test for get_attendance_status_str
    get_attendance_status_str(self, start, end, course_id, is_status_managed, user):
    """
    @freeze_time('2000-03-01 00:00:00')
    def test_get_attendance_status_str_when_previous(self):
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        status = executor.get_attendance_status_str(
            start=self.course.start, end=self.course.end, course_id=self.course.id,
            is_status_managed=self.course.is_status_managed, user=self.user)
        # assert
        self.assertEqual(status, 'previous')

    @freeze_time('2001-03-02 00:00:00')
    def test_get_attendance_status_str_when_not_attended(self):
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        status = executor.get_attendance_status_str(
            start=self.course.start, end=self.course.end, course_id=self.course.id,
            is_status_managed=self.course.is_status_managed, user=self.user)
        # assert
        self.assertEqual(status, 'waiting')

    def test_get_attendance_status_str_when_complete(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value='{"attended_date": "test", "completed_date": "test"}')
        self.course.is_status_managed = True
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        status = executor.get_attendance_status_str(
            start=self.course.start, end=self.course.end, course_id=self.course.id,
            is_status_managed=self.course.is_status_managed, user=self.user)
        # assert
        self.assertEqual(status, 'completed')

    @freeze_time('2002-03-01 00:00:00')
    def test_get_attendance_status_str_when_not_complete_and_close(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='{"attended_date": "test"}')
        self.course.is_status_managed = True
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        status = executor.get_attendance_status_str(
            start=self.course.start, end=self.course.end, course_id=self.course.id,
            is_status_managed=self.course.is_status_managed, user=self.user)
        # assert
        self.assertEqual(status, 'closing')

    @freeze_time('2001-02-01 00:00:00')
    def test_get_attendance_status_str_when_not_complete_and_not_close(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='{"attended_date": "test"}')
        self.course.is_status_managed = True
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        status = executor.get_attendance_status_str(
            start=self.course.start, end=self.course.end, course_id=self.course.id,
            is_status_managed=self.course.is_status_managed, user=self.user)
        # assert
        self.assertEqual(status, 'working')

    @freeze_time('2001-02-01 00:00:00')
    def test_get_attendance_status_str_when_not_is_managed(self):
        # arrange
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='{"attended_date": "test"}')
        self.course.is_status_managed = False
        # act
        executor = AttendanceStatusExecutor(enrollment=self.enrollment)
        status = executor.get_attendance_status_str(
            start=self.course.start, end=self.course.end, course_id=self.course.id,
            is_status_managed=self.course.is_status_managed, user=self.user)
        # assert
        self.assertEqual(status, 'working')

    """
    Test for check_attendance_status
    """
    def _setup_course_modules(self):
        """
        course
          |- chapter_x
          |   |- section_x1
          |   |  |- vertical_x11
          |   |  |    |- module_x11_problem1, module_x11_problem2, module_x11_problem3
          |   |  |- vertical_x12
          |   |  |    |- module_x12_video1, module_x12_video2, module_x12_video3
          |   |  |- vertical_x13
          |   |  |    |- module_x13_survey1
          |   |  |- vertical_x14
          |   |  |    |- module_x14_survey1
          |   |  |- vertical_x15
          |   |  |    |- module_x15_survey1
          |- chapter_y
          |   |- section_y1
        """
        self.course.is_status_managed = True
        self.chapter_x = ItemFactory.create(parent=self.course, category='chapter', display_name="chapter_x",
                                            metadata={'start': datetime(2000, 1, 1, 0, 0, 0)})
        self.section_x1 = ItemFactory.create(parent=self.chapter_x, category='sequential', display_name="section_x1",
                                             metadata={'start': datetime(2000, 1, 1, 0, 0, 0)})
        # vertical_x11
        self.vertical_x11 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x11")
        self.module_x11_problem1 = ItemFactory.create(
            category='problem', parent_location=self.vertical_x11.location, display_name='module_x11_problem1',
            metadata={'is_status_managed': True})
        self.module_x11_problem2 = ItemFactory.create(
            category='problem', parent_location=self.vertical_x11.location, display_name='module_x11_problem2',
            metadata = {'is_status_managed': True})
        self.module_x11_problem3 = ItemFactory.create(
            category='problem', parent_location=self.vertical_x11.location, display_name='module_x11_problem3',
            metadata = {'is_status_managed': False})
        # vertical_x12
        self.vertical_x12 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x12")
        self.module_x12_video1 = ItemFactory.create(
            category='video', parent_location=self.vertical_x12.location, display_name='module_x12_video1',
            metadata = {'is_status_managed': True})
        self.module_x12_video2 = ItemFactory.create(
            category='video', parent_location=self.vertical_x12.location, display_name='module_x12_video2',
            metadata = {'is_status_managed': True})
        self.module_x12_video3 = ItemFactory.create(
            category='video', parent_location=self.vertical_x12.location, display_name='module_x12_video3',
            metadata = {'is_status_managed': False})
        # vertical_x13
        self.vertical_x13 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x13")
        self.vertical_x13_survey1 = ItemFactory.create(
            category='html', parent_location=self.vertical_x13.location, display_name='vertical_x13_survey1',
            metadata = {'is_status_managed': True})
        # vertical_x14
        self.vertical_x14 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x14")
        self.vertical_x14_survey1 = ItemFactory.create(
            category='html', parent_location=self.vertical_x14.location, display_name='vertical_x14_survey1',
            metadata = {'is_status_managed': True})
        # vertical_x15
        self.vertical_x15 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x15")
        self.vertical_x15_survey1 = ItemFactory.create(
            category='html', parent_location=self.vertical_x15.location, display_name='vertical_x15_survey1',
            metadata = {'is_status_managed': False})
        # chapter_y
        self.chapter_y = ItemFactory.create(parent=self.course, category='chapter', display_name="chapter_y",
                                            metadata={'start': datetime(2000, 1, 1, 0, 0, 0)})
        self.section_y1 = ItemFactory.create(parent=self.chapter_y, category='sequential', display_name="section_y1",
                                             metadata={'start': datetime(2000, 1, 1, 0, 0, 0)})

    def test_check_attendance_status_when_completed(self):
        # arrange
        self._setup_course_modules()
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x11_problem1.location, student=self.user,
            grade=1, max_grade=4, state=None)
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x11_problem2.location, student=self.user,
            grade=1, max_grade=4, state=None)
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x12_video1, status=True)])
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x12_video2, status=True)])
        SurveySubmissionFactory.create(
            course_id=self.course.id, unit_id=self.vertical_x13.location.block_id, user=self.user,
            survey_name=self.vertical_x13_survey1.display_name, survey_answer='')
        SurveySubmissionFactory.create(
            course_id=self.course.id, unit_id=self.vertical_x14.location.block_id, user=self.user,
            survey_name=self.vertical_x14_survey1.display_name, survey_answer='')
        # act
        act = AttendanceStatusExecutor(
            enrollment=self.enrollment).check_attendance_status(course=self.course, user_id=self.user.id)
        # assert
        self.assertTrue(act)

    def test_check_attendance_status_when_not_attended_survey(self):
        # arrange
        self._setup_course_modules()
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x11_problem1.location, student=self.user,
            grade=1, max_grade=4, state=None)
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x11_problem2.location, student=self.user,
            grade=1, max_grade=4, state=None)
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x12_video1, status=True)])
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x12_video2, status=True)])
        SurveySubmissionFactory.create(
            course_id=self.course.id, unit_id=self.vertical_x13.location.block_id, user=self.user,
            survey_name=self.vertical_x13_survey1.display_name, survey_answer='')
        # act
        act = AttendanceStatusExecutor(
            enrollment=self.enrollment).check_attendance_status(course=self.course, user_id=self.user.id)
        # assert
        self.assertFalse(act)

    def test_check_attendance_status_when_not_attended_problem(self):
        # arrange
        self._setup_course_modules()
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x11_problem1.location, student=self.user,
            grade=1, max_grade=4, state=None)
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x12_video1, status=True)])
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x12_video2, status=True)])
        SurveySubmissionFactory.create(
            course_id=self.course.id, unit_id=self.vertical_x13.location.block_id, user=self.user,
            survey_name=self.vertical_x13_survey1.display_name, survey_answer='')
        SurveySubmissionFactory.create(
            course_id=self.course.id, unit_id=self.vertical_x14.location.block_id, user=self.user,
            survey_name=self.vertical_x14_survey1.display_name, survey_answer='')
        # act
        act = AttendanceStatusExecutor(
            enrollment=self.enrollment).check_attendance_status(course=self.course, user_id=self.user.id)
        # assert
        self.assertFalse(act)

    def test_check_attendance_status_when_not_attended_movie(self):
        # arrange
        self._setup_course_modules()
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x11_problem1.location, student=self.user,
            grade=1, max_grade=4, state=None)
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x11_problem2.location, student=self.user,
            grade=1, max_grade=4, state=None)
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x12_video1, status=True)])
        SurveySubmissionFactory.create(
            course_id=self.course.id, unit_id=self.vertical_x13.location.block_id, user=self.user,
            survey_name=self.vertical_x13_survey1.display_name, survey_answer='')
        SurveySubmissionFactory.create(
            course_id=self.course.id, unit_id=self.vertical_x14.location.block_id, user=self.user,
            survey_name=self.vertical_x14_survey1.display_name, survey_answer='')
        # act
        act = AttendanceStatusExecutor(
            enrollment=self.enrollment).check_attendance_status(course=self.course, user_id=self.user.id)
        # assert
        self.assertFalse(act)

    """
    Test for get_attendance_values
    """
    def test_get_attendance_values(self):
        # arrange
        course2 = CourseFactory.create(
            org='gacco', number='course2', run='run1', start=datetime(2000, 3, 3, tzinfo=UTC),
            end=datetime(2001, 3, 3, tzinfo=UTC))
        enrollment2 = CourseEnrollmentFactory(user=self.user, course_id=course2.id)
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='sample1')
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status', value='sample2')
        CourseEnrollmentAttributeFactory.create(
            enrollment=enrollment2, namespace='ga', name='attended_status', value='sample3')
        # act
        act = AttendanceStatusExecutor.get_attendance_values([self.enrollment.id, enrollment2.id])
        # assert
        self.assertEqual(2, len(act))
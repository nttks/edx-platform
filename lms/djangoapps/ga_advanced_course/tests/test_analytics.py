
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.translation import ugettext as _

from opaque_keys.edx.locator import CourseLocator
from student.tests.factories import CourseEnrollmentFactory, UserFactory
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from ..analytics import advanced_course_purchased_features, Features
from ..analytics import Features
from .factories import AdvancedF2FCourseFactory, AdvancedCourseTicketFactory
from .utils import purchase_ticket, start_purchase_ticket


RESULT_PARAMS_MAP = {p: p for p in ['p{}'.format(str(i).zfill(3)) for i in range(1, 100)]}


@override_settings(
    CC_PROCESSOR_NAME='GMO',
    CC_PROCESSOR={
        'GMO': {
            'RESULT_PARAMS_MAP': RESULT_PARAMS_MAP
        }
    }
)
class AnalyticsTest(ModuleStoreTestCase):

    def setUp(self):
        super(AnalyticsTest, self).setUp()

        self.features = [
            Features.USER_ID, Features.EMAIL, Features.USERNAME, Features.NAME,
            Features.ADVANCED_COURSE_NAME, Features.ADVANCED_COURSE_TICKET_NAME,
            Features.ENTRY_DATE, Features.PAYMENT_METHOD, Features.ENROLLMENT
        ]

        self.course_id_1 = CourseLocator('org', self._testMethodName + '_1', 'run')
        self.course_id_2 = CourseLocator('org', self._testMethodName + '_2', 'run')

        # Create course
        CourseFactory.create(
            org=self.course_id_1.org, number=self.course_id_1.course, run=self.course_id_1.run
        )
        CourseFactory.create(
            org=self.course_id_2.org, number=self.course_id_2.course, run=self.course_id_2.run
        )

        # Create advanced course
        self.advanced_course_1_1 = AdvancedF2FCourseFactory.create(
            course_id=self.course_id_1, display_name='display name 1_1'
        )
        self.advanced_course_1_2 = AdvancedF2FCourseFactory.create(
            course_id=self.course_id_1, display_name='display name 1_2',
            is_active=False  # also become the target if advanced course is not active
        )
        self.advanced_course_2_1 = AdvancedF2FCourseFactory.create(
            course_id=self.course_id_2, display_name='display name 2_1'
        )

        self.advanced_course_ticket_1_1_1 = AdvancedCourseTicketFactory.create(
            advanced_course=self.advanced_course_1_1, display_name='display name 1_1_1'
        )
        self.advanced_course_ticket_1_1_2 = AdvancedCourseTicketFactory.create(
            advanced_course=self.advanced_course_1_1, display_name='display name 1_1_2'
        )
        self.advanced_course_ticket_1_2_1 = AdvancedCourseTicketFactory.create(
            advanced_course=self.advanced_course_1_2, display_name='display name 1_2_1'
        )
        self.advanced_course_ticket_2_1_1 = AdvancedCourseTicketFactory.create(
            advanced_course=self.advanced_course_2_1, display_name='display name 2_1_1'
        )

        # Create user and enrollement and order
        self.users = [UserFactory.create() for _ in range(60)]
        self.purchase_time = timezone.now()

        for i, user in enumerate(self.users):
            # Enrolled and purchased
            if i % 6 == 0:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
                # Credit Card
                purchase_ticket(user, self.advanced_course_ticket_1_1_1, self.purchase_time, '0')
            elif i % 6 == 1:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
                # Docomo
                purchase_ticket(user, self.advanced_course_ticket_1_2_1, self.purchase_time, '9')
            # Enrolled only
            elif i % 6 == 2:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
            # Enrolled but paying
            elif i % 6 == 3:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
                start_purchase_ticket(user, self.advanced_course_ticket_1_2_1)
            # Purchased but not enrolled
            elif i % 6 == 4:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_2)
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1, is_active=False)
                # Unknown payment type
                purchase_ticket(user, self.advanced_course_ticket_1_1_2, self.purchase_time, '99')
            # Enrolled but purchase other courses's ticket
            elif i % 6 == 5:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
                purchase_ticket(user, self.advanced_course_ticket_2_1_1)

    def test_advanced_course_purchased_features(self):

        def _convert(*target):
            return {
                Features.USER_ID: target[0],
                Features.EMAIL: target[1],
                Features.USERNAME: target[2],
                Features.NAME: target[3],
                Features.ADVANCED_COURSE_NAME: target[4],
                Features.ADVANCED_COURSE_TICKET_NAME: target[5],
                Features.ENTRY_DATE: target[6],
                Features.PAYMENT_METHOD: target[7],
                Features.ENROLLMENT: target[8],
            }

        expected = [
            _convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_1.display_name, self.advanced_course_ticket_1_1_1.display_name,
                self.purchase_time, _('Credit Card'), _('Enrolled'),
            )
            for i, user in enumerate(self.users) if i % 6 == 0
        ]
        expected.extend([
            _convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_2.display_name, self.advanced_course_ticket_1_2_1.display_name,
                self.purchase_time, _('Docomo Mobile Payment'), _('Enrolled'),
            )
            for i, user in enumerate(self.users) if i % 6 == 1
        ])
        expected.extend([
            _convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_1.display_name, self.advanced_course_ticket_1_1_2.display_name,
                self.purchase_time, _('Unknown'), _('Not Enrolled'),
            )
            for i, user in enumerate(self.users) if i % 6 == 4
        ])

        _sort_key = lambda x: x[Features.USER_ID]
        self.assertListEqual(
            sorted(expected, key=_sort_key),
            sorted(advanced_course_purchased_features(self.course_id_1, self.features), key=_sort_key)
        )

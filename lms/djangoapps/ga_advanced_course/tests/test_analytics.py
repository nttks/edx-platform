
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.translation import ugettext as _

from opaque_keys.edx.locator import CourseLocator
from student.tests.factories import CourseEnrollmentFactory, CourseModeFactory, UserFactory
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from ..analytics import advanced_course_purchased_features, paid_course_purchased_features, Features
from .factories import AdvancedF2FCourseFactory, AdvancedCourseTicketFactory
from .utils import purchase_ticket, start_purchase_ticket
from course_modes.models import CourseMode
from verify_student.views import _purchase_with_shoppingcart as purchase_with_shoppingcart

from ga_shoppingcart.tests.factories import PersonalInfoFactory, PersonalInfoSettingFactory


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
            Features.ENTRY_DATE, Features.PAYMENT_METHOD, Features.ENROLLMENT,
            Features.FULL_NAME, Features.KANA, Features.POSTAL_CODE,
            Features.ADDRESS_LINE_1, Features.ADDRESS_LINE_2, Features.PHONE_NUMBER,
            Features.GACCATZ_CHECK, Features.FREE_ENTRY_FIELD_1, Features.FREE_ENTRY_FIELD_2,
            Features.FREE_ENTRY_FIELD_3, Features.FREE_ENTRY_FIELD_4, Features.FREE_ENTRY_FIELD_5,
        ]

        self.course_id_1 = CourseLocator('org', self._testMethodName + '_1', 'run')
        self.course_id_2 = CourseLocator('org', self._testMethodName + '_2', 'run')

        # Create course
        self.course1 = CourseFactory.create(
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
        self.advanced_course_1_3 = AdvancedF2FCourseFactory.create(
            course_id=self.course_id_1, display_name='display name 1_3'
        )
        self.advanced_course_2_1 = AdvancedF2FCourseFactory.create(
            course_id=self.course_id_2, display_name='display name 2_1'
        )

        # Create Ticket
        self.advanced_course_ticket_1_1_1 = AdvancedCourseTicketFactory.create(
            advanced_course=self.advanced_course_1_1, display_name='display name 1_1_1'
        )
        self.advanced_course_ticket_1_1_2 = AdvancedCourseTicketFactory.create(
            advanced_course=self.advanced_course_1_1, display_name='display name 1_1_2'
        )
        self.advanced_course_ticket_1_2_1 = AdvancedCourseTicketFactory.create(
            advanced_course=self.advanced_course_1_2, display_name='display name 1_2_1'
        )
        self.advanced_course_ticket_1_3_1 = AdvancedCourseTicketFactory.create(
            advanced_course=self.advanced_course_1_3, display_name='display name 1_3_1'
        )
        self.advanced_course_ticket_2_1_1 = AdvancedCourseTicketFactory.create(
            advanced_course=self.advanced_course_2_1, display_name='display name 2_1_1'
        )

        # Create personal info setting
        self.personal_info_setting_for_advanced_course = PersonalInfoSettingFactory.create(**dict(
            advanced_course=self.advanced_course_1_3,
            free_entry_field_1_title='aaa',
            free_entry_field_2_title='bbb',
            free_entry_field_3_title='ccc',
            free_entry_field_4_title='ddd',
            free_entry_field_5_title='eee',
        ))

        # Create user and enrollement and order
        self.users = [UserFactory.create() for _ in range(70)]
        self.purchase_time = timezone.now()
        self.personal_info_list = []
        self.order_list = []

        for i, user in enumerate(self.users):
            # Enrolled and purchased
            if i % 7 == 0:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
                # Credit Card
                self.order_list.append(
                    purchase_ticket(user, self.advanced_course_ticket_1_1_1, self.purchase_time, '0')
                )
                self.personal_info_list.append(None)
            elif i % 7 == 1:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
                # Docomo
                self.order_list.append(
                    purchase_ticket(user, self.advanced_course_ticket_1_2_1, self.purchase_time, '9')
                )
                self.personal_info_list.append(None)
            # Enrolled only
            elif i % 7 == 2:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
                self.personal_info_list.append(None)
            # Enrolled but paying
            elif i % 7 == 3:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
                start_purchase_ticket(user, self.advanced_course_ticket_1_2_1)
                self.personal_info_list.append(None)
            # Purchased but not enrolled
            elif i % 7 == 4:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_2)
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1, is_active=False)
                # Unknown payment type
                self.order_list.append(
                    purchase_ticket(user, self.advanced_course_ticket_1_1_2, self.purchase_time, '99')
                )
                self.personal_info_list.append(None)
            # Credit Card with personal info
            elif i % 7 == 5:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
                order = purchase_ticket(user, self.advanced_course_ticket_1_3_1, self.purchase_time, '0')
                self.order_list.append(order)
                self.personal_info_list.append(
                    PersonalInfoFactory.create(**dict(
                        user=user,
                        order_id=order.id,
                        choice=self.personal_info_setting_for_advanced_course,
                    ))
                )
            # Enrolled but purchase other courses's ticket
            elif i % 7 == 6:
                CourseEnrollmentFactory.create(user=user, course_id=self.course_id_1)
                purchase_ticket(user, self.advanced_course_ticket_2_1_1)
                self.personal_info_list.append(None)

    @staticmethod
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
            Features.FULL_NAME: target[9] or '#N/A',
            Features.KANA: target[10] or '#N/A',
            Features.POSTAL_CODE: target[11] or '#N/A',
            Features.ADDRESS_LINE_1: target[12] or '#N/A',
            Features.ADDRESS_LINE_2: target[13] or '#N/A',
            Features.PHONE_NUMBER: target[14] or '#N/A',
            Features.GACCATZ_CHECK: target[15] or '#N/A',
            Features.FREE_ENTRY_FIELD_1: target[16] or '#N/A',
            Features.FREE_ENTRY_FIELD_2: target[17] or '#N/A',
            Features.FREE_ENTRY_FIELD_3: target[18] or '#N/A',
            Features.FREE_ENTRY_FIELD_4: target[19] or '#N/A',
            Features.FREE_ENTRY_FIELD_5: target[20] or '#N/A',
        }

    def test_advanced_course_purchased_features(self):

        expected = [
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_1.display_name, self.advanced_course_ticket_1_1_1.display_name,
                self.purchase_time, _('Credit Card'), _('Enrolled'),
                None, None, None, None, None, None, None, None, None, None, None, None,
            )
            for i, user in enumerate(self.users) if i % 7 == 0
        ]
        expected.extend([
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_2.display_name, self.advanced_course_ticket_1_2_1.display_name,
                self.purchase_time, _('Docomo Mobile Payment'), _('Enrolled'),
                None, None, None, None, None, None, None, None, None, None, None, None,
            )
            for i, user in enumerate(self.users) if i % 7 == 1
        ])
        expected.extend([
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_1.display_name, self.advanced_course_ticket_1_1_2.display_name,
                self.purchase_time, _('Unknown'), _('Not Enrolled'),
                None, None, None, None, None, None, None, None, None, None, None, None,
            )
            for i, user in enumerate(self.users) if i % 7 == 4
        ])
        expected.extend([
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_3.display_name, self.advanced_course_ticket_1_3_1.display_name,
                self.purchase_time, _('Credit Card'), _('Enrolled'),
                personal_info.full_name, personal_info.kana, personal_info.postal_code,
                personal_info.address_line_1, personal_info.address_line_2, personal_info.phone_number,
                personal_info.gaccatz_check, personal_info.free_entry_field_1, personal_info.free_entry_field_2,
                personal_info.free_entry_field_3, personal_info.free_entry_field_4, personal_info.free_entry_field_5,
            )
            for i, (user, personal_info) in enumerate(zip(
                self.users, self.personal_info_list
            )) if i % 7 == 5
        ])

        _sort_key = lambda x: x[Features.USER_ID]
        self.assertListEqual(
            sorted(expected, key=_sort_key),
            sorted(advanced_course_purchased_features(self.course_id_1, self.features), key=_sort_key)
        )

    def test_advanced_course_purchased_features_cancel_case(self):
        for order in self.order_list:
            if order.user.id % 2 == 0:
                order.refund()

        expected = [
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_1.display_name, self.advanced_course_ticket_1_1_1.display_name,
                self.purchase_time, _('Credit Card'), _('Enrolled'),
                None, None, None, None, None, None, None, None, None, None, None, None,
            )
            for i, user in enumerate(self.users) if i % 7 == 0 and i % 2 == 1
        ]
        expected.extend([
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_2.display_name, self.advanced_course_ticket_1_2_1.display_name,
                self.purchase_time, _('Docomo Mobile Payment'), _('Enrolled'),
                None, None, None, None, None, None, None, None, None, None, None, None,
            )
            for i, user in enumerate(self.users) if i % 7 == 1 and i % 2 == 1
        ])
        expected.extend([
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_1.display_name, self.advanced_course_ticket_1_1_2.display_name,
                self.purchase_time, _('Unknown'), _('Not Enrolled'),
                None, None, None, None, None, None, None, None, None, None, None, None,
            )
            for i, user in enumerate(self.users) if i % 7 == 4 and i % 2 == 1
        ])
        expected.extend([
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.advanced_course_1_3.display_name, self.advanced_course_ticket_1_3_1.display_name,
                self.purchase_time, _('Credit Card'), _('Enrolled'),
                personal_info.full_name, personal_info.kana, personal_info.postal_code,
                personal_info.address_line_1, personal_info.address_line_2, personal_info.phone_number,
                personal_info.gaccatz_check, personal_info.free_entry_field_1, personal_info.free_entry_field_2,
                personal_info.free_entry_field_3, personal_info.free_entry_field_4, personal_info.free_entry_field_5,
            )
            for i, (user, personal_info) in enumerate(zip(
                 self.users, self.personal_info_list
            )) if i % 7 == 5 and i % 2 == 1
        ])

        _sort_key = lambda x: x[Features.USER_ID]
        self.assertListEqual(
            sorted(expected, key=_sort_key),
            sorted(advanced_course_purchased_features(self.course_id_1, self.features), key=_sort_key)
        )


@override_settings(
    CC_PROCESSOR_NAME='GMO',
    CC_PROCESSOR={
        'GMO': {
            'RESULT_PARAMS_MAP': RESULT_PARAMS_MAP
        }
    }
)
class AnalyticsForPaidCourseTest(ModuleStoreTestCase):

    def setUp(self):
        super(AnalyticsForPaidCourseTest, self).setUp()

        self.features = [
            Features.USER_ID, Features.EMAIL, Features.USERNAME, Features.NAME,
            Features.ENTRY_DATE, Features.PAYMENT_METHOD, Features.ENROLLMENT,
            Features.FULL_NAME, Features.KANA, Features.POSTAL_CODE,
            Features.ADDRESS_LINE_1, Features.ADDRESS_LINE_2, Features.PHONE_NUMBER,
            Features.GACCATZ_CHECK, Features.FREE_ENTRY_FIELD_1, Features.FREE_ENTRY_FIELD_2,
            Features.FREE_ENTRY_FIELD_3, Features.FREE_ENTRY_FIELD_4, Features.FREE_ENTRY_FIELD_5,
        ]

        self.course_id_1 = CourseLocator('org', self._testMethodName + '_1', 'run')
        self.course_id_2 = CourseLocator('org', self._testMethodName + '_2', 'run')
        self.course_id_3 = CourseLocator('org', self._testMethodName + '_3', 'run')

        # Create course
        self.course1 = CourseFactory.create(
            org=self.course_id_1.org, number=self.course_id_1.course, run=self.course_id_1.run
        )
        self.course2 = CourseFactory.create(
            org=self.course_id_2.org, number=self.course_id_2.course, run=self.course_id_2.run
        )
        self.course3 = CourseFactory.create(
            org=self.course_id_3.org, number=self.course_id_3.course, run=self.course_id_3.run
        )

        # Create course mode
        self.course_mode1 = CourseModeFactory(mode_slug=CourseMode.NO_ID_PROFESSIONAL_MODE,
                                              course_id=self.course_id_1,
                                              min_price=1)

        self.course_mode2 = CourseModeFactory(mode_slug=CourseMode.NO_ID_PROFESSIONAL_MODE,
                                              course_id=self.course_id_2,
                                              min_price=1)

        self.course_mode3 = CourseModeFactory(mode_slug=CourseMode.NO_ID_PROFESSIONAL_MODE,
                                              course_id=self.course_id_3,
                                              min_price=1)

        # Create personal info setting
        self.personal_info_setting_for_paid_course3 = PersonalInfoSettingFactory.create(**dict(
            course_mode=self.course_mode3,
            free_entry_field_1_title='aaa',
            free_entry_field_2_title='bbb',
            free_entry_field_3_title='ccc',
            free_entry_field_4_title='ddd',
            free_entry_field_5_title='eee',
        ))

        # Create user and enrollement and order
        self.users = [UserFactory.create() for _ in range(30)]
        self.purchase_time = timezone.now()
        self.personal_info_list = []
        self.order_list = []

        def _set_up_order(_user, course_id, course_mode, payment_method):
            CourseEnrollmentFactory.create(user=_user, course_id=course_id)
            _order = purchase_with_shoppingcart(_user, course_mode, course_id, 1)
            _item = _order.orderitem_set.all().select_subclasses()[0]
            _item.order.purchase_time = self.purchase_time
            _item.order.processor_reply_dump = '{{"p022": "{}"}}'.format(payment_method)
            _item.order.status = _item.status = 'purchased'
            _item.order.save()
            _item.save()
            return _order

        for i, user in enumerate(self.users):
            # Enrolled and purchased
            if i % 3 == 0:
                # Credit Card
                order = _set_up_order(user, self.course_id_1, self.course_mode1, 0)
                self.personal_info_list.append(None)
            elif i % 3 == 1:
                # Docomo
                order = _set_up_order(user, self.course_id_2, self.course_mode2, 9)
                self.personal_info_list.append(None)
            # Credit Card with personal info
            else:
                order = _set_up_order(user, self.course_id_3, self.course_mode3, 0)
                self.personal_info_list.append(
                    PersonalInfoFactory.create(**dict(
                        user=user,
                        order_id=order.id,
                        choice=self.personal_info_setting_for_paid_course3,
                    ))
                )
            self.order_list.append(order)

    @staticmethod
    def _convert(*target):
        return {
            Features.USER_ID: target[0],
            Features.EMAIL: target[1],
            Features.USERNAME: target[2],
            Features.NAME: target[3],
            Features.ENTRY_DATE: target[4],
            Features.PAYMENT_METHOD: target[5],
            Features.ENROLLMENT: target[6],
            Features.FULL_NAME: target[7] or '#N/A',
            Features.KANA: target[8] or '#N/A',
            Features.POSTAL_CODE: target[9] or '#N/A',
            Features.ADDRESS_LINE_1: target[10] or '#N/A',
            Features.ADDRESS_LINE_2: target[11] or '#N/A',
            Features.PHONE_NUMBER: target[12] or '#N/A',
            Features.GACCATZ_CHECK: target[13] or '#N/A',
            Features.FREE_ENTRY_FIELD_1: target[14] or '#N/A',
            Features.FREE_ENTRY_FIELD_2: target[15] or '#N/A',
            Features.FREE_ENTRY_FIELD_3: target[16] or '#N/A',
            Features.FREE_ENTRY_FIELD_4: target[17] or '#N/A',
            Features.FREE_ENTRY_FIELD_5: target[18] or '#N/A',
        }

    def test_paid_course_purchased_features(self):
        expected1 = [
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.purchase_time, _('Credit Card'), _('Enrolled'),
                None, None, None, None, None, None, None, None, None, None, None, None,
            )
            for i, user in enumerate(self.users) if i % 3 == 0
        ]
        expected2 = [
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.purchase_time, _('Docomo Mobile Payment'), _('Enrolled'),
                None, None, None, None, None, None, None, None, None, None, None, None,
            )
            for i, user in enumerate(self.users) if i % 3 == 1
        ]
        expected3 = [
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.purchase_time, _('Credit Card'), _('Enrolled'),
                personal_info.full_name, personal_info.kana, personal_info.postal_code,
                personal_info.address_line_1, personal_info.address_line_2, personal_info.phone_number,
                personal_info.gaccatz_check, personal_info.free_entry_field_1, personal_info.free_entry_field_2,
                personal_info.free_entry_field_3, personal_info.free_entry_field_4, personal_info.free_entry_field_5,
            )
            for i, (user, personal_info) in enumerate(zip(
                self.users, self.personal_info_list
            )) if i % 3 == 2
        ]

        _sort_key = lambda x: x[Features.USER_ID]
        expected_list = [expected1, expected2, expected3]
        course_id_list = [self.course_id_1, self.course_id_2, self.course_id_3]
        for expected, course_id in zip(expected_list, course_id_list):
            self.assertListEqual(
                sorted(expected, key=_sort_key),
                sorted(paid_course_purchased_features(course_id, self.features), key=_sort_key)
            )

    def test_paid_course_purchased_features_cancel_case(self):
        for order in self.order_list:
            if order.user.id % 2 == 0:
                order.refund()

        expected1 = [
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.purchase_time, _('Credit Card'), _('Enrolled'),
                None, None, None, None, None, None, None, None, None, None, None, None,
            )
            for i, user in enumerate(self.users) if i % 3 == 0 and i % 2 == 1
        ]
        expected2 = [
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.purchase_time, _('Docomo Mobile Payment'), _('Enrolled'),
                None, None, None, None, None, None, None, None, None, None, None, None,
            )
            for i, user in enumerate(self.users) if i % 3 == 1 and i % 2 == 1
        ]
        expected3 = [
            self._convert(
                user.id, user.email, user.username, user.profile.name,
                self.purchase_time, _('Credit Card'), _('Enrolled'),
                personal_info.full_name, personal_info.kana, personal_info.postal_code,
                personal_info.address_line_1, personal_info.address_line_2, personal_info.phone_number,
                personal_info.gaccatz_check, personal_info.free_entry_field_1, personal_info.free_entry_field_2,
                personal_info.free_entry_field_3, personal_info.free_entry_field_4, personal_info.free_entry_field_5,
            )
            for i, (user, personal_info) in enumerate(zip(
                self.users, self.personal_info_list
            )) if i % 3 == 2 and i % 2 == 1
        ]

        _sort_key = lambda x: x[Features.USER_ID]
        expected_list = [expected1, expected2, expected3]
        course_id_list = [self.course_id_1, self.course_id_2, self.course_id_3]
        for expected, course_id in zip(expected_list, course_id_list):
            self.assertListEqual(
                sorted(expected, key=_sort_key),
                sorted(paid_course_purchased_features(course_id, self.features), key=_sort_key)
            )

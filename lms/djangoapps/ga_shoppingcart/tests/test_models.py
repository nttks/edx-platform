import ddt
from mock import patch, MagicMock

from course_modes.models import CourseMode
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from student.tests.factories import CourseModeFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ga_advanced_course.models import AdvancedCourse
from ga_advanced_course.tests.factories import AdvancedF2FCourseFactory
from ga_shoppingcart.models import PersonalInfoSetting
from ga_shoppingcart.tests.factories import PersonalInfoSettingFactory
from ga_shoppingcart.tests.utils import get_order_from_advanced_course, get_order_from_paid_course


@ddt.ddt
class PersonalInfoSettingTest(ModuleStoreTestCase):
    def setUp(self, **kwargs):
        super(PersonalInfoSettingTest, self).setUp()
        self.course_for_advanced = CourseFactory.create(
            metadata={
                'is_f2f_course': True,
                'is_f2f_course_sell': True,
            }
        )
        self.advanced_course = AdvancedF2FCourseFactory.create(
            course_id=self.course_for_advanced.id,
            display_name='display_name',
            is_active=True
        )
        self.course_for_paid = CourseFactory.create()
        self.course_mode = CourseModeFactory(mode_slug='no-id-professional',
                                             course_id=self.course_for_paid.id,
                                             min_price=1, sku='')

    def _setup_personal_info_setting(self, is_selected_advanced, is_selected_paid):
        kwargs = {}
        if is_selected_advanced:
            kwargs.update(dict(advanced_course_id=self.advanced_course.id))
        if is_selected_paid:
            kwargs.update(dict(course_mode_id=self.course_mode.id))
        return kwargs

    @ddt.data(
        (True, True, False),
        (True, False, True),
        (True, False, True),
        (False, False, False),
    )
    @ddt.unpack
    def test__is_selected_event_or_course(self, is_selected_advanced, is_selected_paid, is_valid):
        kwargs = self._setup_personal_info_setting(is_selected_advanced, is_selected_paid)

        personal_input_setting = PersonalInfoSettingFactory.create(**kwargs)

        self.assertEqual(
            personal_input_setting._is_selected_event_or_course(),
            is_valid
        )

    def test_clean_success(self):
        kwargs = self._setup_personal_info_setting(True, False)
        personal_input_setting = PersonalInfoSettingFactory.create(**kwargs)
        try:
            personal_input_setting.clean()
        except ValidationError:
            self.fail("PersonalInfoSetting.clean() raised ValidationError unexpectedly!")

    def test_clean_course_select_error(self):
        kwargs = self._setup_personal_info_setting(
            is_selected_advanced=True,
            is_selected_paid=True
        )
        personal_input_setting = PersonalInfoSettingFactory.create(**kwargs)
        self.assertRaisesMessage(
            expected_exception=ValidationError,
            expected_message=_("You must select item 'Event id' or 'Professional course id'."),
            callable_obj=personal_input_setting.clean)

    @ddt.data(
        (True, False),
        (False, True),
    )
    @ddt.unpack
    def test_clean_address_line_select_error(self, select_address_line_1, select_address_line_2):
        kwargs = self._setup_personal_info_setting(
            is_selected_advanced=False,
            is_selected_paid=True
        )
        kwargs.update(dict(
            address_line_1=select_address_line_1,
            address_line_2=select_address_line_2
        ))
        personal_input_setting = PersonalInfoSettingFactory.create(**kwargs)
        self.assertRaisesMessage(
            expected_exception=ValidationError,
            expected_message=_("If you choose an Address Line 1 or 2, you must choose both."),
            callable_obj=personal_input_setting.clean)

    def test_clean_not_select_error(self):
        kwargs = self._setup_personal_info_setting(False, True)
        kwargs.update(dict(
            full_name=False,
            kana=False,
            postal_code=False,
            address_line_1=False,
            address_line_2=False,
            phone_number=False,
            gaccatz_check=False,
            free_entry_field_1_title='',
            free_entry_field_2_title='',
            free_entry_field_3_title='',
            free_entry_field_4_title='',
            free_entry_field_5_title='',
        ))
        personal_input_setting = PersonalInfoSettingFactory.create(**kwargs)
        self.assertRaisesMessage(
            expected_exception=ValidationError,
            expected_message=_("You must select one item except 'Event Id' and 'Professional course ID' and 'Address Line 2'"),
            callable_obj=personal_input_setting.clean)

    def test_has_personal_info_setting_for_advanced_course(self):
        kwargs = self._setup_personal_info_setting(
            is_selected_advanced=True,
            is_selected_paid=False
        )
        PersonalInfoSettingFactory.create(**kwargs)
        self.assertTrue(PersonalInfoSetting.has_personal_info_setting(advanced_course=self.advanced_course))
        self.assertFalse(PersonalInfoSetting.has_personal_info_setting(course_mode=self.course_mode))

    def test_has_personal_info_setting_for_paid_course(self):
        kwargs = self._setup_personal_info_setting(
            is_selected_advanced=False,
            is_selected_paid=True
        )
        PersonalInfoSettingFactory.create(**kwargs)
        self.assertFalse(PersonalInfoSetting.has_personal_info_setting(advanced_course=self.advanced_course))
        self.assertTrue(PersonalInfoSetting.has_personal_info_setting(course_mode=self.course_mode))

    def test_get_item_with_order_id_from_advanced_course(self):
        order, self.advanced_course = get_order_from_advanced_course(self.course_for_advanced, self.user)
        kwargs = self._setup_personal_info_setting(is_selected_advanced=True, is_selected_paid=False)
        PersonalInfoSettingFactory.create(**kwargs)
        setting = PersonalInfoSetting.get_item_with_order_id(order_id=order.id)
        self.assertTrue(isinstance(setting.advanced_course, AdvancedCourse))
        self.assertEquals(setting.course_mode, None)

    def test_get_item_with_order_id_from_paid_course(self):
        order = get_order_from_paid_course(self.course_mode, self.course_for_paid, self.user)
        kwargs = self._setup_personal_info_setting(is_selected_advanced=False, is_selected_paid=True)
        PersonalInfoSettingFactory.create(**kwargs)
        setting = PersonalInfoSetting.get_item_with_order_id(order_id=order.id)
        self.assertTrue(isinstance(setting.course_mode, CourseMode))
        self.assertEquals(setting.advanced_course, None)

    @patch('shoppingcart.models.OrderItem.objects.get_subclass', return_value=MagicMock())
    def test_get_item_with_order_id_error_case(self, get_subclass_mock):
        order = get_order_from_paid_course(self.course_mode, self.course_for_paid, self.user)
        kwargs = self._setup_personal_info_setting(is_selected_advanced=False, is_selected_paid=True)
        PersonalInfoSettingFactory.create(**kwargs)
        with self.assertRaises(PersonalInfoSetting.DoesNotExist) as cm:
            PersonalInfoSetting.get_item_with_order_id(order_id=order.id)
        self.assertEqual("'advanced_course' or 'course_mode' is required for PersonalInfoSetting.",
                         cm.exception.message)
        get_subclass_mock.assert_called_once_with(order_id=order.id)

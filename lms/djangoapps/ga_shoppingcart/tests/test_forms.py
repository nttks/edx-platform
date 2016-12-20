from mock import patch
from opaque_keys.edx.locator import CourseLocator
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ga_advanced_course.tests.factories import AdvancedF2FCourseFactory
from ga_shoppingcart.forms import PersonalInfoModelForm
from ga_shoppingcart.tests.factories import PersonalInfoSettingFactory


class PersonalInfoModelFormTest(ModuleStoreTestCase):
    def setUp(self, **kwargs):
        super(PersonalInfoModelFormTest, self).setUp()
        self.course_id_1 = CourseLocator('org', self._testMethodName + '_1', 'run')
        self.course1 = CourseFactory.create(
            org=self.course_id_1.org, number=self.course_id_1.course, run=self.course_id_1.run
        )
        self.advanced_course = AdvancedF2FCourseFactory.create(
            course_id=self.course_id_1, display_name='display name'
        )

    @patch('ga_shoppingcart.forms.get_language', return_value='ja')
    def test_init(self, get_language_mock):
        free_entry_field_dict = dict(
            free_entry_field_1='aaa',
            free_entry_field_2='bbb',
            free_entry_field_3='ccc',
            free_entry_field_4='ddd',
            free_entry_field_5='eee',
        )
        p = PersonalInfoSettingFactory.create(**dict(
            advanced_course=self.advanced_course,
            free_entry_field_1_title='aaa',
            free_entry_field_2_title='bbb',
            free_entry_field_3_title='ccc',
            free_entry_field_4_title='ddd',
            free_entry_field_5_title='eee',
        ))

        f = PersonalInfoModelForm(**dict(personal_info_setting=p))

        self.assertTrue(get_language_mock.called)
        for key in PersonalInfoModelForm.Meta.fields:
            self.assertIn(key, f.fields)
        for key in PersonalInfoModelForm.Meta.exclude:
            self.assertNotIn(key, f.fields)

        for k, v in free_entry_field_dict.iteritems():
            self.assertEquals(f.fields[k].label, v)

    @patch('ga_shoppingcart.forms.get_language', return_value='en')
    def test_init_english_case(self, get_language_mock):
        p = PersonalInfoSettingFactory.create(**dict(
            advanced_course=self.advanced_course,
            free_entry_field_1_title='aaa',
            free_entry_field_2_title='bbb',
            free_entry_field_3_title='ccc',
            free_entry_field_4_title='ddd',
            free_entry_field_5_title='eee',
        ))

        f = PersonalInfoModelForm(**dict(personal_info_setting=p))

        self.assertTrue(get_language_mock.called)
        for key in PersonalInfoModelForm.Meta.fields:
            if key == 'kana':
                self.assertNotIn(key, f.fields)
            else:
                self.assertIn(key, f.fields)

    @patch('ga_shoppingcart.forms.get_language', return_value='ja')
    def test_init_set_exclude_case(self, get_language_mock):
        p = PersonalInfoSettingFactory.create(**dict(
            advanced_course=self.advanced_course,
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

        f = PersonalInfoModelForm(**dict(personal_info_setting=p))

        self.assertFalse(get_language_mock.called)
        for key in PersonalInfoModelForm.Meta.fields:
            self.assertNotIn(key, f.fields)

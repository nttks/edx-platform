# -*- coding: utf-8 -*-
import factory
from factory.django import DjangoModelFactory

from ga_shoppingcart.models import PersonalInfo, PersonalInfoSetting


class PersonalInfoFactory(DjangoModelFactory):
    class Meta(object):
        model = PersonalInfo

    user = None
    order_id = None
    choice = None
    full_name = factory.Sequence(lambda n: 'Full Name{0}'.format(n))
    kana = u'フル　ネーム'
    postal_code = factory.Sequence(lambda n: '1{0:06}'.format(n))
    address_line_1 = factory.Sequence(lambda n: 'Address Line 1 {0}'.format(n))
    address_line_2 = factory.Sequence(lambda n: 'Address Line 2 {0}'.format(n))
    phone_number = factory.Sequence(lambda n: '{0:013}'.format(n))
    free_entry_field_1 = factory.Sequence(lambda n: 'Free Entry Field 1 {0}'.format(n))
    free_entry_field_2 = factory.Sequence(lambda n: 'Free Entry Field 2 {0}'.format(n))
    free_entry_field_3 = factory.Sequence(lambda n: 'Free Entry Field 3 {0}'.format(n))
    free_entry_field_4 = factory.Sequence(lambda n: 'Free Entry Field 4 {0}'.format(n))
    free_entry_field_5 = factory.Sequence(lambda n: 'Free Entry Field 5 {0}'.format(n))


class PersonalInfoSettingFactory(DjangoModelFactory):
    class Meta(object):
        model = PersonalInfoSetting

from ddt import ddt

from collections import OrderedDict

from django.utils.translation import ugettext as _

from biz.djangoapps.ga_course_anslist import views as view
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_org_group.tests.factories import GroupUtil
from biz.djangoapps.util.tests.testcase import BizViewTestBase


@ddt
class GetGridColumnsTest(BizViewTestBase):

    def setUp(self):
        self.EXPECTED_BASE_COLUMNS = [
            ("Organization Name", "text"),
            ("Member Code", "text"),
            ("Username", "text"),
            ("Email", "text"),
            ("Full Name", "text"),
            ("Login Code", "text"),
            ("Enroll Date", "date"),
        ]
        self.EXPECTED_BASE_COLUMNS_HIDDEN = [
            ("Group Code", "hidden"),
            ("Student Status", "hidden"),
        ]
        self.EXPECTED_ORGS_ITEMS_COLUMNS = [
            ( _("Organization") + "1", 'text'),
            ( _("Organization") + "2", 'text'),
            ( _("Organization") + "3", 'text'),
            (_("Item") + "1", 'text'),
            (_("Item") + "2", 'text'),
            (_("Item") + "3", 'text'),
        ]
        self.EXPECTED_ORGS_ITEMS_COLUMNS_HIDDEN = [
            (_("Organization") + "4", 'hidden'),
            (_("Organization") + "5", 'hidden'),
            (_("Organization") + "6", 'hidden'),
            (_("Organization") + "7", 'hidden'),
            (_("Organization") + "8", 'hidden'),
            (_("Organization") + "9", 'hidden'),
            (_("Organization") + "10", 'hidden'),
            (_("Item") + "4", 'hidden'),
            (_("Item") + "5", 'hidden'),
            (_("Item") + "6", 'hidden'),
            (_("Item") + "7", 'hidden'),
            (_("Item") + "8", 'hidden'),
            (_("Item") + "9", 'hidden'),
            (_("Item") + "10", 'hidden'),
        ]
        self.EXPECTED_ORG_ITEM_LIST = OrderedDict([
            ('org1', _("Organization") + "1"),
            ('org2', _("Organization") + "2"),
            ('org3', _("Organization") + "3"),
            ('org4', _("Organization") + "4"),
            ('org5', _("Organization") + "5"),
            ('org6', _("Organization") + "6"),
            ('org7', _("Organization") + "7"),
            ('org8', _("Organization") + "8"),
            ('org9', _("Organization") + "9"),
            ('org10', _("Organization") + "10"),
            ('item1', _("Item") + "1"),
            ('item2', _("Item") + "2"),
            ('item3', _("Item") + "3"),
            ('item4', _("Item") + "4"),
            ('item5', _("Item") + "5"),
            ('item6', _("Item") + "6"),
            ('item7', _("Item") + "7"),
            ('item8', _("Item") + "8"),
            ('item9', _("Item") + "9"),
            ('item10', _("Item") + "10"),
        ])

    def test_get_grid_columns_empty(self):
        expected = self.EXPECTED_BASE_COLUMNS + self.EXPECTED_ORGS_ITEMS_COLUMNS + self.EXPECTED_BASE_COLUMNS_HIDDEN + self.EXPECTED_ORGS_ITEMS_COLUMNS_HIDDEN
        actual = view._get_grid_columns([])
        self.assertEqual(expected, actual)

    def test_get_grid_columns_one(self):
        survey_names_list = [('11111111111111111111111111111111', 'survey1')]
        survey_names_list_mod = []
        for tpl in survey_names_list:
            survey_names_list_mod.append((tpl[1], 'text'))
        expected = self.EXPECTED_BASE_COLUMNS + survey_names_list_mod + self.EXPECTED_ORGS_ITEMS_COLUMNS + self.EXPECTED_BASE_COLUMNS_HIDDEN + self.EXPECTED_ORGS_ITEMS_COLUMNS_HIDDEN
        actual = view._get_grid_columns(survey_names_list)
        self.assertEqual(expected, actual)

    def test_get_grid_columns_two(self):
        survey_names_list = [('11111111111111111111111111111111', 'survey1'),
                             ('22222222222222222222222222222222', 'survey2'),
                             ]
        survey_names_list_mod = []
        for tpl in survey_names_list:
            survey_names_list_mod.append((tpl[1], 'text'))

        expected = self.EXPECTED_BASE_COLUMNS + survey_names_list_mod + self.EXPECTED_ORGS_ITEMS_COLUMNS + self.EXPECTED_BASE_COLUMNS_HIDDEN + self.EXPECTED_ORGS_ITEMS_COLUMNS_HIDDEN
        actual = view._get_grid_columns(survey_names_list)
        self.assertEqual(expected, actual)

    def test_get_org_item_list(self):
        expected = self.EXPECTED_ORG_ITEM_LIST
        actual = view._get_org_item_list()
        self.assertEqual(expected, actual)


class GetGroupChoiceListTest(BizContractTestBase):

    def setUp(self):
        super(GetGroupChoiceListTest, self).setUp()
        GroupUtil(org=self.contract_org, user=self.user).import_data()

    def test_get_group_choice_list(self):
        _manager = self._create_manager(
            org=self.contract_org,
            user=self.user,
            created=self.gacco_organization,
            permissions=[self.manager_permission]
        )
        group_ids = Group.objects.filter(
            org=self.contract_org, group_code__in=['G01-01', 'G01-01-01', 'G01-01-02']).values('id')

        # Test
        actual_result = view._get_group_choice_list(_manager, self.contract_org, group_ids)
        self.assertEqual(len(group_ids), len(actual_result))

    def test_get_group_choice_list_director(self):
        _director = self._create_manager(
            org=self.contract_org,
            user=self.user,
            created=self.gacco_organization,
            permissions=[self.director_permission]
        )

        # Test
        actual_result = view._get_group_choice_list(_director, self.contract_org, [])
        self.assertEqual(Group.objects.filter(org=self.contract_org).count(), len(actual_result))
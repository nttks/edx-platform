from unittest import TestCase
from ddt import ddt, data, file_data, unpack

from biz.djangoapps.ga_course_anslist import helpers as helper
from biz.djangoapps.ga_course_anslist.tests import factories as TestData

import logging
import copy
from collections import OrderedDict


LOG_LEBEL = logging.DEBUG
logging.basicConfig(level=LOG_LEBEL, format="[%(asctime)s][%(levelname)s](%(filename)s:%(lineno)s) %(message)s", datefmt="%Y/%m/%d %H:%M:%S")

log = logging.getLogger(__name__)


@ddt
class HelperTest(TestCase):
    EXPECTED_DATA_NO_DATA = []
    EXPECTED_DATA_ALL = [
       {
          'Item8':'',
          'Item9':'',
          'Item2':'jast2',
          'Item3':'jast3',
          'Item1':'jast1',
          'Item6':'',
          'Item7':'',
          'Item4':'',
          'Item5':'',
          'Login Code':'ohanna',
          'Org8':'',
          'Org9':'',
          'Org2':'gacco2',
          'Org3':'gacco3',
          'Organization Name':'Gacco100',
          'Org6':'',
          'Email':'ohanna.Harbour@sample.com',
          'Org4':'',
          'Org5':'',
          'Username':'manager-1001',
          'Org1':'gacco1',
          'Org10':'',
          'Item10':'',
          'id':'1',
          'Survey1':'2018-11-01',
          'Survey3':'2018-11-03',
          'Survey2':'2018-11-02',
          'Org7':'',
          'Student Status':'',
          'Full Name':'ohanna Harbour',
          'Group Code':'100',
          'Enroll Date':'2018-10-30',
          'recid':1,
          'Member Code':'1001'
       },
       {
          'Item8':'',
          'Item9':'',
          'Item2':'jast2',
          'Item3':'',
          'Item1':'jast1',
          'Item6':'',
          'Item7':'',
          'Item4':'',
          'Item5':'',
          'Login Code':'Deandre',
          'Org8':'',
          'Org9':'',
          'Org2':'gacco2',
          'Org3':'',
          'Organization Name':'Gacco110',
          'Org6':'',
          'Email':'Deandre.Morin@sample.com',
          'Org4':'',
          'Org5':'',
          'Username':'manager-1101',
          'Org1':'gacco1',
          'Org10':'',
          'Item10':'',
          'id':'2',
          'Survey1':'2018-11-01',
          'Survey3':'',
          'Survey2':'2018-11-02',
          'Org7':'',
          'Student Status':'',
          'Full Name':'Deandre Morin',
          'Group Code':'110',
          'Enroll Date':'2018-10-31',
          'recid':2,
          'Member Code':'1101'
       },
       {
          'Item8':'',
          'Item9':'',
          'Item2':'',
          'Item3':'',
          'Item1':'jast1',
          'Item6':'',
          'Item7':'',
          'Item4':'',
          'Item5':'',
          'Login Code':'Blossom',
          'Org8':'',
          'Org9':'',
          'Org2':'',
          'Org3':'',
          'Organization Name':'Gacco120',
          'Org6':'',
          'Email':'Blossom.Blick@sample.com',
          'Org4':'',
          'Org5':'',
          'Username':'user-1201',
          'Org1':'gacco1',
          'Org10':'',
          'Item10':'',
          'id':'3',
          'Survey1':'2018-11-01',
          'Survey3':'',
          'Survey2':'',
          'Org7':'',
          'Student Status':'',
          'Full Name':'Blossom Blick',
          'Group Code':'120',
          'Enroll Date':'2018-11-01',
          'recid':3,
          'Member Code':'1201'
       }
    ]
    _param_survey_name_condition_name_empty_on_on = [{'field': [u'survey_name'], 'survey_answered': [u'on'], 'survey_not_answered': [u'on'], 'value': [u'']}]
    _param_survey_name_condition_name_empty_off_on = [{'field': [u'survey_name'], 'survey_answered': [u''], 'survey_not_answered': [u'on'], 'value': [u'']}]
    _param_survey_name_condition_name_empty_on_off = [{'field': [u'survey_name'], 'survey_answered': [u'on'], 'survey_not_answered': [u''], 'value': [u'']}]
    _param_survey_name_condition_name_empty_off_off = [{'field': [u'survey_name'], 'survey_answered': [u''], 'survey_not_answered': [u''], 'value': [u'']}]
    _param_survey_name_condition_name_survey1_on_on =  [{'field': [u'survey_name'], 'survey_answered': [u'on'], 'survey_not_answered': [u'on'], 'value': [u'Survey1']}]
    _param_survey_name_condition_name_survey1_off_on = [{'field': [u'survey_name'], 'survey_answered': [u''], 'survey_not_answered': [u'on'], 'value': [u'Survey1']}]
    _param_survey_name_condition_name_survey1_on_off = [{'field': [u'survey_name'], 'survey_answered': [u'on'], 'survey_not_answered': [u''], 'value': [u'Survey1']}]
    _param_survey_name_condition_name_survey1_off_off = [{'field': [u'survey_name'], 'survey_answered': [u'on'], 'survey_not_answered': [u''], 'value': [u'Survey1']}]
    _param_survey_name_condition_name_survey2_on_on =  [{'field': [u'survey_name'], 'survey_answered': [u'on'], 'survey_not_answered': [u'on'], 'value': [u'Survey2']}]
    _param_survey_name_condition_name_survey2_off_on = [{'field': [u'survey_name'], 'survey_answered': [u''], 'survey_not_answered': [u'on'], 'value': [u'Survey2']}]
    _param_survey_name_condition_name_survey2_on_off = [{'field': [u'survey_name'], 'survey_answered': [u'on'], 'survey_not_answered': [u''], 'value': [u'Survey2']}]
    _param_survey_name_condition_name_survey2_off_off = [{'field': [u'survey_name'], 'survey_answered': [u''], 'survey_not_answered': [u''], 'value': [u'Survey2']}]

    ## for variables of test params
    _test_dct = {}

    def test_dummy(self):
        log.debug(' ------- start.')

    def _setup_test_dict(self):
        global _test_dct
        ## arrange data
        test_dct_lst = TestData.get_data_csv()
        ## test data is rows[0:2]
        test_dct_lst_ext = test_dct_lst[:3]
        test_dct = OrderedDict()
        for row_dct in test_dct_lst_ext:
            row_dct['obj'] = copy.deepcopy(row_dct)
            test_dct.update({row_dct['id'] : row_dct})

        _test_dct = test_dct

    @data((EXPECTED_DATA_ALL))
    def test_transform_grid_records_no_conditions(self, expected):
        global _test_dct
        self._setup_test_dict()
        actual = helper._transform_grid_records(_test_dct)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)

    @data(
        (_param_survey_name_condition_name_empty_on_on, EXPECTED_DATA_ALL),
        (_param_survey_name_condition_name_empty_on_off, EXPECTED_DATA_ALL),
        (_param_survey_name_condition_name_empty_off_on, EXPECTED_DATA_ALL),
        (_param_survey_name_condition_name_empty_off_off, EXPECTED_DATA_ALL),
    )
    @unpack
    def test_transform_grid_records_conditions_name_empty(self, conditions, expected):
        global _test_dct
        self._setup_test_dict()
        actual = helper._transform_grid_records(_test_dct, conditions)
        log.debug('actual_name_not_exists={}'.format(actual))
        #self.assertEqual(expected, actual)


    @data(
        (_param_survey_name_condition_name_survey1_on_on, EXPECTED_DATA_ALL),
        (_param_survey_name_condition_name_survey1_on_off, EXPECTED_DATA_ALL),
        (_param_survey_name_condition_name_survey1_off_on, EXPECTED_DATA_NO_DATA),
        (_param_survey_name_condition_name_survey1_off_off, EXPECTED_DATA_ALL),
    )
    @unpack
    def test_transform_grid_records_conditions_name(self, conditions, expected):
        global _test_dct
        self._setup_test_dict()
        actual = helper._transform_grid_records(_test_dct, conditions)
        log.debug('actual_name_exists={}'.format(actual))
        self.assertEqual(expected, actual)

    @data(
        (_param_survey_name_condition_name_survey2_on_on, EXPECTED_DATA_ALL),
        (_param_survey_name_condition_name_survey2_off_off, EXPECTED_DATA_ALL),
    )
    @unpack
    def test_transform_grid_records_conditions_name_survey2_all(self, conditions, expected):
        global _test_dct
        self._setup_test_dict()
        actual = helper._transform_grid_records(_test_dct, conditions)
        log.debug('actual_name_exists={}'.format(actual))
        self.assertEqual(expected, actual)

    @data(
        (_param_survey_name_condition_name_survey2_on_off, copy.deepcopy(EXPECTED_DATA_ALL[0:2])),
    )
    @unpack
    def test_transform_grid_records_conditions_name_survey2_on_off(self, conditions, expected):
        global _test_dct
        self._setup_test_dict()
        actual = helper._transform_grid_records(_test_dct, conditions)
        log.debug('actual_name_exists={}'.format(actual))
        self.assertEqual(expected, actual)

    @data(
        (_param_survey_name_condition_name_survey2_off_on, [EXPECTED_DATA_ALL[2]]),
    )
    @unpack
    def test_transform_grid_records_conditions_name_survey2_off_on(self, conditions, expected):
        global _test_dct
        self._setup_test_dict()
        expected_mod = copy.deepcopy(expected[0])
        expected_mod['recid'] = 1
        log.debug("expected={}".format(expected[0]))
        log.debug("expected_mod={}".format(expected_mod))
        actual = helper._transform_grid_records(_test_dct, conditions)
        log.debug('actual_name_exists={}'.format(actual))
        self.assertEqual([expected_mod], actual)

    # @data((1, -3, -2),
    #       (2, 3, 5))
    # @unpack
    # def test_add(self, a, b, expected):
    #     actual = helper.add(a, b)
    #     self.assertEqual(expected, actual)

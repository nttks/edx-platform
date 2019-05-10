from unittest import TestCase
from ddt import ddt, data, file_data, unpack

from biz.djangoapps.ga_course_anslist import helpers as helper
from biz.djangoapps.ga_course_anslist.tests import factories as TestData

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

import json
import logging
import copy

log = logging.getLogger(__name__)

GRID_COLUMNS = [
    ["Organization Name", "text"],
    ["Member Code", "text"],
    ["Username", "text"],
    ["Email", "text"],
    ["Full Name", "text"],
    ["Login Code", "text"],
    ["Student Status","text"],
    ["Enroll Date", "date"],
]

GRID_COLUMNS_NON_STATUS = [
    ["Organization Name", "text"],
    ["Member Code", "text"],
    ["Username", "text"],
    ["Email", "text"],
    ["Full Name", "text"],
    ["Login Code", "text"],
    ["Enroll Date", "date"],
]

GRID_COLUMNS_HIDDEN = [
    ["Group Code", "hidden"],
]

GRID_COLUMNS_TRANSFORMED = [
   ('Organization Name', 'text'),
   ('Member Code', 'text'),
   ('Username', 'text'),
   ('Email', 'text'),
   ('Full Name', 'text'),
   ('Login Code', 'text'),
   ('Enroll Date', 'date'),
   ('survey name 1', 'text'),
   ('survey name 2', 'text'),
   ('survey name 3', 'text'),
   ('Group Code', 'hidden'),
   ('Student Status', 'hidden'),
]

QUERY_STATEMENT_SURVEY_NAMES = '''
    SELECT 
            sbm2.id
          , sbm2.unit_id
          , sbm2.course_id
          , sbm2.survey_name
          , sbm2.created
    FROM
        (SELECT 
            sbm.unit_id
          , min(sbm.created) AS created_min
        FROM
          ga_survey_surveysubmission as sbm
        WHERE 1 = 1
        and sbm.course_id = '$course_id'
        group by sbm.unit_id, sbm.course_id
        ) AS min_data
        INNER JOIN ga_survey_surveysubmission sbm2
        ON min_data.unit_id = sbm2.unit_id
        AND min_data.created_min = sbm2.created
        '''

QUERY_STATEMENT_SURVEY_NAMES_EXPECTED = '''
    SELECT 
            sbm2.id
          , sbm2.unit_id
          , sbm2.course_id
          , sbm2.survey_name
          , sbm2.created
    FROM
        (SELECT 
            sbm.unit_id
          , min(sbm.created) AS created_min
        FROM
          ga_survey_surveysubmission as sbm
        WHERE 1 = 1
        and sbm.course_id = 'course-v1:xxxxxxxxxxx+2018_02'
        group by sbm.unit_id, sbm.course_id
        ) AS min_data
        INNER JOIN ga_survey_surveysubmission sbm2
        ON min_data.unit_id = sbm2.unit_id
        AND min_data.created_min = sbm2.created
        '''

QUERY_STATEMENT_SURVEY_NAMES_MAX = '''
    SELECT 
            sbm2.id
          , sbm2.unit_id
          , sbm2.course_id
          , sbm2.survey_name
          , sbm2.created
    FROM
        (SELECT 
            sbm.unit_id
          , max(sbm.created) AS created_max
        FROM
          ga_survey_surveysubmission as sbm
        WHERE 1 = 1
        and sbm.course_id = '$course_id'
        group by sbm.unit_id, sbm.course_id
        ) AS max_data
        INNER JOIN ga_survey_surveysubmission sbm2
        ON max_data.unit_id = sbm2.unit_id
        AND max_data.created_max = sbm2.created
        '''


QUERY_STATEMENT_SURVEY_NAMES_MAX_EXPECTED = '''
    SELECT 
            sbm2.id
          , sbm2.unit_id
          , sbm2.course_id
          , sbm2.survey_name
          , sbm2.created
    FROM
        (SELECT 
            sbm.unit_id
          , max(sbm.created) AS created_max
        FROM
          ga_survey_surveysubmission as sbm
        WHERE 1 = 1
        and sbm.course_id = 'course-v1:xxxxxxxxxxx+2018_02'
        group by sbm.unit_id, sbm.course_id
        ) AS max_data
        INNER JOIN ga_survey_surveysubmission sbm2
        ON max_data.unit_id = sbm2.unit_id
        AND max_data.created_max = sbm2.created
        '''

QUERY_STATEMENT_USER_NOT_MEMBERS = '''
    SELECT
        enroll.id
      , cntr.contractor_organization_id as org_id
      , det.contract_id
      , enroll.course_id
      , enroll.user_id
      , usr.username
      , usr.email
      , bzusr.login_code
      , prof.name
      , enroll.created
    FROM student_courseenrollment as enroll
    LEFT JOIN ga_contract_contractdetail as det
        ON enroll.course_id = det.course_id
    LEFT JOIN ga_contract_contract as cntr
        ON det.contract_id = cntr.id
    LEFT JOIN ga_organization_organization as org
        ON cntr.contractor_organization_id = org.id
    LEFT JOIN auth_user as usr
        ON enroll.user_id = usr.id
    LEFT JOIN ga_invitation_contractregister as reg
        ON enroll.user_id = reg.user_id
    LEFT JOIN ga_login_bizuser as bzusr
        ON usr.id = bzusr.user_id
    LEFT JOIN auth_userprofile as prof
        ON usr.id = prof.user_id
    WHERE 1=1
    AND org.id = $org_id
    AND enroll.course_id =  '$course_id'
    AND reg.contract_id = det.contract_id
    AND reg.contract_id = $contract_id
    AND usr.id not in ($user_ids)
    '''

QUERY_STATEMENT_USER_NOT_MEMBERS_ACTUAL = '''
    SELECT
        enroll.id
      , cntr.contractor_organization_id as org_id
      , det.contract_id
      , enroll.course_id
      , enroll.user_id
      , usr.username
      , usr.email
      , bzusr.login_code
      , prof.name
      , enroll.created
    FROM student_courseenrollment as enroll
    LEFT JOIN ga_contract_contractdetail as det
        ON enroll.course_id = det.course_id
    LEFT JOIN ga_contract_contract as cntr
        ON det.contract_id = cntr.id
    LEFT JOIN ga_organization_organization as org
        ON cntr.contractor_organization_id = org.id
    LEFT JOIN auth_user as usr
        ON enroll.user_id = usr.id
    LEFT JOIN ga_invitation_contractregister as reg
        ON enroll.user_id = reg.user_id
    LEFT JOIN ga_login_bizuser as bzusr
        ON usr.id = bzusr.user_id
    LEFT JOIN auth_userprofile as prof
        ON usr.id = prof.user_id
    WHERE 1=1
    AND org.id = 85
    AND enroll.course_id =  'course-v1:xxxxxxxxxxx+2018_02'
    AND reg.contract_id = det.contract_id
    AND reg.contract_id = 284
    AND usr.id not in (370196,345969)
    '''

CONST_ORG_ID = 85
CONST_CONTRACT_ID = 284
CONST_COURSE_ID = 'course-v1:xxxxxxxxxxx+2018_02'
CONST_USER_IDS = [370196, 345969]
CONST_SURVEY_NAME_LIST = [
        ('survey name 1', 'survey name 1'),
        ('survey name 2', 'survey name 2'),
        ('survey name 3', 'survey name 3'),
    ]

POST_DICT_DATA_INITIAL = {
   u'search': [u''],
   u'group_id': [u''],
   u'survey_name': [u''],
   u'survey_answered': 'on',
   u'survey_not_answered': 'on',
   u'detail_condition_member_name_1': [u''],
   u'detail_condition_member_1': [u''],
   u'detail_condition_member_name_2': [u''],
   u'detail_condition_member_2': [u''],
   u'detail_condition_member_name_3': [u''],
   u'detail_condition_member_3': [u''],
   u'detail_condition_member_name_4': [u''],
   u'detail_condition_member_4': [u''],
   u'detail_condition_member_name_5': [u''],
   u'detail_condition_member_5': [u''],
   u'limit': '100',
   u'offset': '0',
}


class HelperTest(ModuleStoreTestCase):

    def _create_course_data(self):
        self.course = CourseFactory.create(org='xxxxxxxxxxx', number='course', run='2018_02')
        self.overview = CourseOverview.get_from_id(self.course.id)

    def test_grid_columns(self):
        expected = json.dumps(GRID_COLUMNS)
        actual = json.dumps(helper.GRID_COLUMNS)
        self.assertEqual(expected, actual)
        log.debug('DONE')

    def test_grid_columns_non_status(self):
        expected = json.dumps(GRID_COLUMNS_NON_STATUS)
        actual = json.dumps(helper.GRID_COLUMNS_NON_STATUS)
        self.assertEqual(expected, actual)
        log.debug('DONE')

    def test_grid_columns_hidden(self):
        expected = json.dumps(GRID_COLUMNS_HIDDEN)
        actual = json.dumps(helper.GRID_COLUMNS_HIDDEN)
        self.assertEqual(expected, actual)
        log.debug('DONE')

    def test_query_statement_survey_names(self):
        expected = json.dumps(QUERY_STATEMENT_SURVEY_NAMES)
        actual = json.dumps(helper.QUERY_STATEMENT_SURVEY_NAMES)
        self.assertEqual(expected, actual)
        log.debug('DONE')

    def test_query_statement_survey_names_max(self):
        expected = json.dumps(QUERY_STATEMENT_SURVEY_NAMES_MAX)
        actual = json.dumps(helper.QUERY_STATEMENT_SURVEY_NAMES_MAX)
        self.assertEqual(expected, actual)
        log.debug('DONE')

    def test_create_survey_name_list_statement(self):
        expected = QUERY_STATEMENT_SURVEY_NAMES_EXPECTED
        # arrange
        course_id = CONST_COURSE_ID
        actual = helper._create_survey_name_list_statement(course_id)
        self.assertEqual(expected, actual)
        log.debug('DONE')

    def test_create_survey_name_list_max_statement(self):
        expected = QUERY_STATEMENT_SURVEY_NAMES_MAX_EXPECTED
        # arrange
        course_id = CONST_COURSE_ID
        flg_get_updated_survey_name = True
        actual = helper._create_survey_name_list_statement(course_id, flg_get_updated_survey_name)
        self.assertEqual(expected, actual)
        log.debug('DONE')

    def test_query_statement_user_not_members(self):
        expected = json.dumps(QUERY_STATEMENT_USER_NOT_MEMBERS)
        actual = json.dumps(helper.QUERY_STATEMENT_USER_NOT_MEMBERS)
        self.assertEqual(expected, actual)
        log.debug('DONE')

    def test_create_users_not_members_statement(self):
        expected = QUERY_STATEMENT_USER_NOT_MEMBERS_ACTUAL
        # arrange
        org_id = CONST_ORG_ID
        contract_id = CONST_CONTRACT_ID
        course_id = CONST_COURSE_ID
        user_ids = CONST_USER_IDS
        actual = helper._create_users_not_members_statement(org_id, contract_id, course_id, user_ids)
        self.assertEqual(expected, actual)
        log.debug('DONE')

    def test_get_grid_columns_base(self):
        self._create_course_data()
        expected = GRID_COLUMNS_TRANSFORMED[0:10]
        survey_names_list = CONST_SURVEY_NAME_LIST
        actual = helper._get_grid_columns_base(self.course.id, survey_names_list)
        self.assertEqual(expected, actual)
        log.debug('DONE')

    def test_populate_for_tsv(self):
        # arrange
        _test_data = TestData.get_data_csv()
        # log.debug(_test_data)
        # test data is rows[0:2]

        _test_dct_lst = copy.deepcopy(_test_data[:3])

        columns = GRID_COLUMNS_TRANSFORMED
        records = _test_dct_lst
        # log.debug('records={}'.format(records))

        expected_header = ['Organization Name', 'Member Code', 'Username', 'Email', 'Full Name', 'Login Code', 'Enroll Date', 'survey name 1', 'survey name 2', 'survey name 3', 'Group Code', 'Student Status']
        expected_rows = [['Gacco100', '1001', 'manager-1001', 'ohanna.Harbour@sample.com', 'ohanna Harbour', 'ohanna', '2018-10-30', '', '', '', '100', '', ],
                         ['Gacco110', '1101', 'manager-1101', 'Deandre.Morin@sample.com', 'Deandre Morin', 'Deandre', '2018-10-31', '', '', '', '110', '', ],
                         ['Gacco120', '1201', 'user-1201', 'Blossom.Blick@sample.com', 'Blossom Blick', 'Blossom', '2018-11-01', '', '', '', '120', '', ]
                         ]
        actual_header, actual_rows = helper._populate_for_tsv(columns, records)

        log.debug('actual_header={}'.format(actual_header))
        log.debug('actual_rows={}'.format(actual_rows))

        self.assertEqual(expected_header, actual_header)
        self.assertEqual(expected_rows, actual_rows)

    def test_populate_for_tsv_not_in_columns(self):
        # arrange
        _test_data = TestData.get_data_csv()
        # log.debug(_test_data)
        # test data is rows[0:2]
        _test_dct_lst = copy.deepcopy(_test_data[:3])

        columns = [
            ('Organization Name', 'text'),
            ('Group Code', 'text'),
            ('Member Code', 'text'),
            ('survey name 1', 'text'),
            ('survey name 2', 'text'),
            ('survey name 3', 'text'),
        ]
        records = _test_dct_lst
        # log.debug('records={}'.format(records))

        expected_header = ['Organization Name', 'Group Code', 'Member Code', 'survey name 1', 'survey name 2', 'survey name 3']
        expected_rows = [['Gacco100', '100', '1001', '', '', ''], ['Gacco110', '110', '1101', '', '', ''], ['Gacco120', '120', '1201', '', '', '']]
        actual_header, actual_rows = helper._populate_for_tsv(columns, records)

        log.debug('actual_header={}'.format(actual_header))
        log.debug('actual_rows={}'.format(actual_rows))

        self.assertEqual(expected_header, actual_header)
        self.assertEqual(expected_rows, actual_rows)


@ddt
class HelperUtilTest(TestCase):

    # def test_somoke_test(self):
    #     log.debug(' ------- start.')
    #     expected = 3
    #     actual   = helper._smoke_test(1,2)
    #     self.assertEqual(expected, actual)

    pattern_init = {
        u'group_id': [u''],
        u'survey_answered': [u'on'],
        u'survey_name': [u''],
        u'survey_not_answered': [u'on']
    }

    @data(
        (POST_DICT_DATA_INITIAL, pattern_init),
    )
    @unpack
    def test_serialize_post_data(self, param, expected):
        actual = helper._serialize_post_data(param)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)

    post_pattern_remove_1 = {
        u'survey_name': [u''],
        u'survey_answered': 'on',
        u'survey_not_answered': 'on',
    }
    ret_pattern_remove_1 = {
        u'group_id': [u''],
        u'survey_answered': [u'on'],
        u'survey_name': [u''],
        u'survey_not_answered': [u'on']
    }

    @data(
        (post_pattern_remove_1, ret_pattern_remove_1),
    )
    @unpack
    def test_serialize_post_data_remove_1(self, param, expected):
        actual = helper._serialize_post_data(param)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)

    post_pattern_remove_2 = {
        u'survey_answered': 'on',
        u'survey_not_answered': 'on',
    }
    ret_pattern_remove_2 = {
        u'group_id': [u''],
        u'survey_answered': [u'on'],
        u'survey_name': [u''],
        u'survey_not_answered': [u'on']
    }

    @data(
        (post_pattern_remove_2, ret_pattern_remove_2),
    )
    @unpack
    def test_serialize_post_data_remove_2(self, param, expected):
        actual = helper._serialize_post_data(param)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)

    post_pattern_remove_3 = {
        u'survey_not_answered': 'on',
    }
    ret_pattern_remove_3 = {
        u'group_id': [u''],
        u'survey_answered': [u''],
        u'survey_name': [u''],
        u'survey_not_answered': [u'on']
    }

    @data(
        (post_pattern_remove_3, ret_pattern_remove_3),
    )
    @unpack
    def test_serialize_post_data_remove_3(self, param, expected):
        actual = helper._serialize_post_data(param)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)

    post_pattern_remove_4 = {
    }
    ret_pattern_remove_4 = {
        u'group_id': [u''],
        u'survey_answered': [u''],
        u'survey_name': [u''],
        u'survey_not_answered': [u'']
    }

    @data(
        (post_pattern_remove_4, ret_pattern_remove_4),
    )
    @unpack
    def test_serialize_post_data_remove_4(self, param, expected):
        actual = helper._serialize_post_data(param)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)

    post_pattern_full = {
        u'group_id': '10',
        u'survey_name': 'Survey1',
        u'survey_answered': 'on',
        u'survey_not_answered': 'on',
    }
    ret_pattern_full = {
        u'group_id': [u'10'],
        u'survey_answered': [u'on'],
        u'survey_name': [u'Survey1'],
        u'survey_not_answered': [u'on']
    }

    @data(
        (post_pattern_full, ret_pattern_full),
    )
    @unpack
    def test_serialize_post_data_full(self, param, expected):
        actual = helper._serialize_post_data(param)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)

    post_pattern_01 = {
        u'group_id': [u''],
        u'survey_name': 'Survey1',
        u'survey_answered': 'on',
        u'survey_not_answered': 'on',
    }
    ret_pattern_01 = {
        u'group_id': [u''],
        u'survey_answered': [u'on'],
        u'survey_name': [u'Survey1'],
        u'survey_not_answered': [u'on']
    }

    @data(
        (post_pattern_01, ret_pattern_01),
    )
    @unpack
    def test_serialize_post_data_01(self, param, expected):
        actual  = helper._serialize_post_data(param)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)

    post_pattern_02 = {
        u'group_id': '10',
        u'survey_name': [u''],
        u'survey_answered': 'on',
        u'survey_not_answered': 'on',
    }
    ret_pattern_02 = {
        u'group_id': [u'10'],
        u'survey_answered': [u'on'],
        u'survey_name': [u''],
        u'survey_not_answered': [u'on']
    }

    @data(
        (post_pattern_02, ret_pattern_02),
    )
    @unpack
    def test_serialize_post_data_02(self, param, expected):
        actual = helper._serialize_post_data(param)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)

    post_pattern_03 = {
        u'group_id': '10',
        u'survey_name': 'Survey1',
        u'survey_answered': [u''],
        u'survey_not_answered': 'on',
    }
    ret_pattern_03 = {
        u'group_id': [u'10'],
        u'survey_answered': [u''],
        u'survey_name': [u'Survey1'],
        u'survey_not_answered': [u'on']
    }

    @data(
        (post_pattern_03, ret_pattern_03),
    )
    @unpack
    def test_serialize_post_data_03(self, param, expected):
        actual   = helper._serialize_post_data(param)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)

    post_pattern_04 = {
        u'group_id': '10',
        u'survey_name': 'Survey1',
        u'survey_answered': 'on',
        u'survey_not_answered': [u''],
    }
    ret_pattern_04 = {
        u'group_id': [u'10'],
        u'survey_answered': [u'on'],
        u'survey_name': [u'Survey1'],
        u'survey_not_answered': [u'']
    }

    @data(
        (post_pattern_04, ret_pattern_04),
    )
    @unpack
    def test_serialize_post_data_04(self, param, expected):
        actual   = helper._serialize_post_data(param)
        log.debug('actual={}'.format(actual))
        self.assertEqual(expected, actual)


@ddt
class HelperSetConditionTest(TestCase):

    post_pattern_init = {
       u'search': [u''],
       u'group_id': [u''],
       u'survey_name': [u''],
       u'survey_answered': 'on',
       u'survey_not_answered': 'on',
       u'detail_condition_member_name_1': [u''],
       u'detail_condition_member_1': [u''],
       u'detail_condition_member_name_2': [u''],
       u'detail_condition_member_2': [u''],
       u'detail_condition_member_name_3': [u''],
       u'detail_condition_member_3': [u''],
       u'detail_condition_member_name_4': [u''],
       u'detail_condition_member_4': [u''],
       u'detail_condition_member_name_5': [u''],
       u'detail_condition_member_5': [u''],
       u'limit': '100',
       u'offset': '0',
    }
    expected_member_condition_init = [
        {'field': [u'group_id'], 'value': [u'']},
    ]
    expected_survey_name_condition_init = [{
        'field': [u'survey_name'],
        'survey_answered': [u'on'],
        'survey_not_answered': [u'on'],
        'value': [u'']
    }]

    @data(
        (post_pattern_init, expected_member_condition_init, expected_survey_name_condition_init),
    )
    @unpack
    def test_set_conditions_initial(self, post_data, expected_member_condition, expected_survey_name_condition):
        actual_member_condition, actual_survey_name_condition= helper._set_conditions(post_data)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    @data(
        (post_pattern_init, expected_member_condition_init, expected_survey_name_condition_init),
    )
    @unpack
    def test_set_conditions_remove_group_id(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        del pdata[u'group_id']
        actual_member_condition, actual_survey_name_condition= helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    @data(
        (post_pattern_init, expected_member_condition_init, expected_survey_name_condition_init),
    )
    @unpack
    def test_set_conditions_group_id_empty(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        pdata.update({u'group_id': [u'']})
        actual_member_condition, actual_survey_name_condition= helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    expected_member_condition_group_id_inputted = [
        {'field': [u'group_id'], 'value': [u'10']},
    ]

    @data(
        (post_pattern_init, expected_member_condition_group_id_inputted, expected_survey_name_condition_init),
    )
    @unpack
    def test_set_conditions_group_id_inputted(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        pdata.update({u'group_id': u'10'})
        actual_member_condition, actual_survey_name_condition= helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    expected_member_condition_group_id_inputted = [
        {'field': [u'group_id'], 'value': [u'']},
    ]

    @data(
        (post_pattern_init, expected_member_condition_group_id_inputted, expected_survey_name_condition_init),
    )
    @unpack
    def test_set_conditions_member_name_1_empty(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        pdata.update({u'detail_condition_member_name_1': [u'']})
        pdata.update({u'detail_condition_member_1': u'dummy'})
        actual_member_condition , actual_survey_name_condition= helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    expected_member_condition_group_id_inputted1_1 = [
        {'field': [u'group_id'], 'value': [u'']},
        {'field': [u'org1'], 'value': u'gacco1'},
    ]

    @data(
        (post_pattern_init, expected_member_condition_group_id_inputted1_1, expected_survey_name_condition_init),
    )
    @unpack
    def test_set_conditions_member_name_1_inputted1_1(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        pdata.update({u'detail_condition_member_name_1': u'org1'})
        pdata.update({u'detail_condition_member_1': u'gacco1'})
        actual_member_condition , actual_survey_name_condition= helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    expected_member_condition_group_id_inputted1_2 = [
        {'field': [u'group_id'], 'value': [u'']},
        {'field': [u'org1'], 'value': u'gacco1'},
        {'field': [u'org3'], 'value': u'gacco3'},
    ]

    @data(
        (post_pattern_init, expected_member_condition_group_id_inputted1_2, expected_survey_name_condition_init),
    )
    @unpack
    def test_set_conditions_member_name_1_inputted1_2(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        pdata.update({u'detail_condition_member_name_1': u'org1'})
        pdata.update({u'detail_condition_member_1': u'gacco1'})
        pdata.update({u'detail_condition_member_name_2': u'org3'})
        pdata.update({u'detail_condition_member_2': u'gacco3'})
        actual_member_condition , actual_survey_name_condition= helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    expected_member_condition_group_id_inputted1_3 = [
        {'field': [u'group_id'], 'value': [u'']},
        {'field': [u'org1'], 'value': u'gacco1'},
        {'field': [u'org3'], 'value': u'gacco3'},
    ]

    @data(
        (post_pattern_init, expected_member_condition_group_id_inputted1_3, expected_survey_name_condition_init),
    )
    @unpack
    def test_set_conditions_member_name_1_inputted1_3(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        pdata.update({u'detail_condition_member_name_1': u'org1'})
        pdata.update({u'detail_condition_member_1': u'gacco1'})
        pdata.update({u'detail_condition_member_name_3': u'org3'})
        pdata.update({u'detail_condition_member_3': u'gacco3'})
        actual_member_condition, actual_survey_name_condition = helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    expected_member_condition_group_id_inputted1_4 = [
        {'field': [u'group_id'], 'value': [u'']},
        {'field': [u'item10'], 'value': u'item10'},
    ]

    @data(
        (post_pattern_init, expected_member_condition_group_id_inputted1_4, expected_survey_name_condition_init),
    )
    @unpack
    def test_set_conditions_member_name_1_inputted1_4(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        pdata.update({u'detail_condition_member_name_4': u'item10'})
        pdata.update({u'detail_condition_member_4': u'item10'})
        actual_member_condition , actual_survey_name_condition = helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    expected_member_condition_group_id_inputted1_5 = [
        {'field': [u'group_id'], 'value': [u'']},
        {'field': [u'item1'], 'value': u'item1'},
    ]

    @data(
        (post_pattern_init, expected_member_condition_group_id_inputted1_5, expected_survey_name_condition_init),
    )
    @unpack
    def test_set_conditions_member_name_1_inputted1_5(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        pdata.update({u'detail_condition_member_name_5': u'item1'})
        pdata.update({u'detail_condition_member_5': u'item1'})
        actual_member_condition , actual_survey_name_condition = helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    expected_member_condition_init = [
        {'field': [u'group_id'], 'value': [u'']},
    ]
    expected_survey_name_condition_inputted = [{
        'field': [u'survey_name'],
        'survey_answered': [u'on'],
        'survey_not_answered': [u'on'],
        'value': [u'Survey1']
    }]

    @data(
        (post_pattern_init, expected_member_condition_init, expected_survey_name_condition_inputted),
    )
    @unpack
    def test_set_conditions_inputted_survey_name(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        pdata.update({u'survey_name': u'Survey1'})
        actual_member_condition , actual_survey_name_condition= helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

    post_pattern_init_not_unicode ={
       u'search': [u''],
       u'group_id': [u''],
       u'survey_name': [u''],
       u'survey_answered': 'on',
       u'survey_not_answered': 'on',
       u'detail_condition_member_name_1': [''],
       u'detail_condition_member_1': [u''],
       u'detail_condition_member_name_2': [u''],
       u'detail_condition_member_2': [u''],
       u'detail_condition_member_name_3': [u''],
       u'detail_condition_member_3': [u''],
       u'detail_condition_member_name_4': [u''],
       u'detail_condition_member_4': [u''],
       u'detail_condition_member_name_5': [u''],
       u'detail_condition_member_5': [u''],
       u'limit': '100',
       u'offset': '0',
    }
    expected_member_condition_init_not_unicode = [
        {'field': [u'group_id'], 'value': [u'']},
    ]
    expected_survey_name_condition_inputted = [{
        'field': [u'survey_name'],
        'survey_answered': [u'on'],
        'survey_not_answered': [u'on'],
        'value': [u'Survey1']
    }]

    @data(
        (post_pattern_init_not_unicode, expected_member_condition_init, expected_survey_name_condition_inputted),
    )
    @unpack
    def test_set_conditions_initial_not_unicode(self, post_data, expected_member_condition, expected_survey_name_condition):
        pdata = copy.deepcopy(post_data)
        pdata.update({u'survey_name': u'Survey1'})
        actual_member_condition, actual_survey_name_condition = helper._set_conditions(pdata)
        log.debug('EXIST: actual_member_condition={}'.format(actual_member_condition))
        self.assertEqual(expected_member_condition, actual_member_condition)
        self.assertEqual(expected_survey_name_condition, actual_survey_name_condition)

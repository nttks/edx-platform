from ddt import ddt, data, file_data, unpack
import codecs
import json

## django
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _

## TestBase
from biz.djangoapps.util.tests.testcase import BizViewTestBase, BizStoreTestBase
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase

## factory
from xmodule.modulestore.tests.factories import CourseFactory
from student.tests.factories import UserFactory
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from ga_survey.tests.factories import SurveySubmissionFactory
from student.tests.factories import CourseEnrollmentFactory

#from biz.djangoapps.ga_course_anslist.tests.test_base import AnslistTestBase
from biz.djangoapps.ga_course_anslist import helpers as helper

@ddt
class ViewsReverseTest(BizViewTestBase):
    """
    Test course answer status list url
    """
    CONST_URL_SEARCH_API = u'/biz/course_anslist/search_api'

    def get_url_search_api(self):
        return reverse('biz:course_anslist:status_search_api')

    CONST_URL_DOWNLOAD = u'/biz/course_anslist/download'

    def get_url_download_api(self):
        return reverse('biz:course_anslist:status_download')

    @data((1, 3, 4))
    @unpack
    def test_smoke_test(self, a, b, expected):
        actual = helper._smoke_test(a, b)
        self.assertEqual(expected, actual)

    @data(CONST_URL_SEARCH_API)
    def test_url_search_api(self, expected):
        self.assertEqual(expected, self.get_url_search_api())

    @data(CONST_URL_DOWNLOAD)
    def test_url_download_csv(self, expected):
        self.assertEqual(expected, self.get_url_download_api())

@ddt
class CourseAnslistDownloadTest(BizContractTestBase, BizStoreTestBase):
#class CourseAnslistDownloadTest(AnslistTestBase):
    """
    Test course answer status list download
    """
    def setUp(self):
        #super(AnslistTestBase, self).setUp()
        #super(BizViewTestBase, self).setUp()
        super(BizContractTestBase, self).setUp()
        self.setup_user()

        ## organization
        self.org100 = self._create_organization(org_name='gacco100', org_code='gacco-100', creator_org=self.gacco_organization)
        ## course
        self.course10 = CourseFactory.create(org='gacco', number='course10', run='run10')
        ## contract
        self.contract1 = self._create_contract(
                            contract_name='contract1', contractor_organization=self.org100,
                            detail_courses=[self.course10.id], additional_display_names=['country', 'dept'],
                            send_submission_reminder=True,
        )
        ## director user
        ### set up self.user for director
        self._director = self._create_manager(
            org=self.org100,
            user=self.user,
            created=self.org100,
            permissions=[self.director_permission]
        )
        ## user
        self.user10 = UserFactory.create(username='na10000', email='nauser10000@example.com')
        ## manager user10
        self._manager = self._create_manager(
            org=self.org100,
            user=self.user10,
            created=self.gacco_organization,
            permissions=[self.manager_permission]
        )
        self.user11 = UserFactory.create(username='na11000', email='nauser11000@example.com')
        self.user12 = UserFactory.create(username='na12000', email='nauser12000@example.com')

        ## group
        self.group1000 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='1000', group_name='G1000', org=self.org100,
            created_by=self.user, modified_by=self.user)
        self.group1100 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='1100', group_name='G1100', org=self.org100,
            created_by=self.user, modified_by=self.user)
        self.group1200 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='1200', group_name='G1200', org=self.org100,
            created_by=self.user, modified_by=self.user)

        ## member
        self.member10 = MemberFactory.create(
            org=self.org100,
            group=self.group1000,
            user=self.user10,
            code='0010',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco1',
        )
        self.member11 = MemberFactory.create(
            org=self.org100,
            group=self.group1100,
            user=self.user11,
            code='0011',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco1',
            org2='gacco11',
        )
        ## enrollment
        self.enroll10 = CourseEnrollmentFactory.create(user=self.user10, course_id=self.course10.id)
        self.enroll11 = CourseEnrollmentFactory.create(user=self.user11, course_id=self.course10.id)
        ### user10
        submission10_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user10,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission10_c10_survey1 = SurveySubmissionFactory.create(**submission10_c10_survey1_data)

        submission10_c10_survey2_data = {
            'course_id': self.course10.id,
            'unit_id': '22222222222222222222222222222222',
            'user': self.user10,
            'survey_name': 'survey2',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission10_c10_survey2 = SurveySubmissionFactory.create(**submission10_c10_survey2_data)

        ### user11
        submission11_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user11,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission11_c10_survey1 = SurveySubmissionFactory.create(**submission11_c10_survey1_data)


    POST_DATA_INIT = {
       u'group_id':[u''],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u''],
       u'detail_condition_member_1':[u''],
       u'detail_condition_member_name_2':[u''],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u''],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u''],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u''],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }



    def _validate_bom(self, content):
        return self._validate_bom_utf16(content)

    def _validate_bom_utf16(self, content):
        # UTF8 no BOM
        return not content.startswith(codecs.BOM_UTF8)

    def _convert_csv_rows(self, content):
        body = content.rstrip('\n').replace('\r', '')
        return body.split('\n')

    def _get_url_download(self):
        return reverse('biz:course_anslist:status_download')

    def _get_url_search(self):
        return reverse('biz:course_anslist:status_search_api')

    def test_request_anslist_search_o100_c10(self):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            expected_len = 3
            self.POST_DATA_INIT["search-download"] = "search-download"
            actual_response = self.client.post(self._get_url_search(), self.POST_DATA_INIT)
            self.assertEqual('application/json', actual_response['Content-Type'], )
            actual_content = actual_response.content
            json_obj = json.loads(actual_content)
            actual_len = len(json_obj)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)

    def test_request_anslist_download_o100_c10(self):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            expected_len = 4
            self.POST_DATA_INIT["search-download"] = "search-download"
            actual_response = self.client.post(self._get_url_download(), self.POST_DATA_INIT)
            self.assertEqual('text/tab-separated-values', actual_response['Content-Type'], )
            actual_content = actual_response.content
            self.assertTrue(self._validate_bom(actual_content))
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)


    def test_request_anslist_search_o100_c10_sorted(self):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_search(), self.POST_DATA_INIT)
            expected_len = 2
            expected_rows_group_code_0 = u'' + self.group1000.group_code
            expected_rows_group_code_1 = u'' + self.group1100.group_code
            actual_content = actual_response.content
            json_obj = json.loads(actual_content)
            actual_rows = json.loads(json_obj['resp_records_json'])
            actual_rows_group_code_0 = actual_rows[0][_('Group Code')]
            actual_rows_group_code_1 = actual_rows[1][_('Group Code')]
            self.assertEqual(expected_len, len(actual_rows))
            self.assertEqual(expected_rows_group_code_0, actual_rows_group_code_0)
            self.assertEqual(expected_rows_group_code_1, actual_rows_group_code_1)

        self.assertEqual(200, actual_response.status_code)


    def test_request_anslist_download_o100_c10_sorted(self):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), self.POST_DATA_INIT)
            expected_len = 4
            #expected_rows_group_code_0 = u'' + "\'" + self.group1000.group_code + "\'"
            #expected_rows_group_code_1 = u'' + "\'" + self.group1100.group_code + "\'"
            expected_rows_group_code_0 = u"\x00'\x001\x000\x000\x000\x00'\x00"
            expected_rows_group_code_1 = u"\x00'\x001\x001\x000\x000\x00'\x00"
            self.POST_DATA_INIT["search-download"] = "search-download"
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            actual_rows_group_code_0 = u'' + rows[1].split('\t')[15]
            actual_rows_group_code_1 = u'' + rows[2].split('\t')[15]
            self.assertEqual(expected_len, actual_len)
            self.assertEqual(expected_rows_group_code_0, actual_rows_group_code_0)
            self.assertEqual(expected_rows_group_code_1, actual_rows_group_code_1)

        self.assertEqual(200, actual_response.status_code)

    def test_url_download_not_allowed_method(self):
        with self.skip_check_course_selection(
                current_organization=self.org100,
                current_contract=self.contract1,
                current_course=self.course10):
            response = self.client.get(self._get_url_download())
            self.assertEqual(405, response.status_code)


    def test_url_search_not_allowed_method(self):
        with self.skip_check_course_selection(
                current_organization=self.org100,
                current_contract=self.contract1,
                current_course=self.course10):
            response = self.client.get(self._get_url_search())
            self.assertEqual(405, response.status_code)


    POST_DATA_EMPTY = {u'csrfmiddlewaretoken': [u'FwScQwdW2lH9l3GEYXUgn2cWsSASHa62']}
    @data((POST_DATA_EMPTY, 4))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_empty(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)

    POST_DATA_CONDITION_0 = {
       u'group_id':[u''],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u'org1'],
       u'detail_condition_member_1':[u'g'],
       u'detail_condition_member_name_2':[u''],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u''],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u''],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u''],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }
    @data((POST_DATA_CONDITION_0, 4))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_0(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)


    POST_DATA_CONDITION_1 = {
       u'group_id':[u''],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u'org2'],
       u'detail_condition_member_1':[u'g'],
       u'detail_condition_member_name_2':[u''],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u''],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u''],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u''],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }
    @data((POST_DATA_CONDITION_1, 3))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_1(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)


    POST_DATA_CONDITION_2 = {
       u'group_id':[u''],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u'org3'],
       u'detail_condition_member_1':[u'g'],
       u'detail_condition_member_name_2':[u''],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u''],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u''],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u''],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }
    @data((POST_DATA_CONDITION_2, 2))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_2(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)



    POST_DATA_CONDITION_3 = {
       u'group_id':[u''],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u'org3'],
       u'detail_condition_member_1':[u'g'],
       u'detail_condition_member_name_2':[u'org4'],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u'org5'],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u'org6'],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u'org7'],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }
    @data((POST_DATA_CONDITION_3, 2))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_3(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)

    POST_DATA_CONDITION_4 = {
       u'group_id':[u''],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u'org8'],
       u'detail_condition_member_1':[u'g'],
       u'detail_condition_member_name_2':[u'org9'],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u'org10'],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u''],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u''],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }
    @data((POST_DATA_CONDITION_4, 2))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_4(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)


    POST_DATA_CONDITION_5 = {
       u'group_id':[u''],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u'item1'],
       u'detail_condition_member_1':[u'g'],
       u'detail_condition_member_name_2':[u'item2'],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u'item3'],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u'item4'],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u'item5'],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }
    @data((POST_DATA_CONDITION_5, 2))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_5(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)


    POST_DATA_CONDITION_6 = {
       u'group_id':[u''],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u'item1'],
       u'detail_condition_member_1':[u'g'],
       u'detail_condition_member_name_2':[u'item2'],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u'item3'],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u'item4'],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u'item5'],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }
    @data((POST_DATA_CONDITION_6, 2))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_6(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)

    POST_DATA_CONDITION_7 = {
       u'group_id':[u''],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u'item6'],
       u'detail_condition_member_1':[u'g'],
       u'detail_condition_member_name_2':[u'item7'],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u'item8'],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u'item9'],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u'item10'],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }
    @data((POST_DATA_CONDITION_7, 2))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_7(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)


    POST_DATA_CONDITION_8 = {
       u'group_id':[u'1111'],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u''],
       u'detail_condition_member_1':[u''],
       u'detail_condition_member_name_2':[u''],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u''],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u''],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u''],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }
    @data((POST_DATA_CONDITION_8, 2))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_8(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)

    POST_DATA_CONDITION_99 = {
       u'group_id':[u''],
       u'survey_name':[u''],
       u'survey_answered':[u'on'],
       u'survey_not_answered':[u'on'],
       u'detail_condition_member_name_1':[u'org11'],
       u'detail_condition_member_1':[u''],
       u'detail_condition_member_name_2':[u''],
       u'detail_condition_member_2':[u''],
       u'detail_condition_member_name_3':[u''],
       u'detail_condition_member_3':[u''],
       u'detail_condition_member_name_4':[u''],
       u'detail_condition_member_4':[u''],
       u'detail_condition_member_name_5':[u''],
       u'detail_condition_member_5':[u''],
       u'search':[u''],
       u'limit':[u'100'],
       u'offset':[u'0'],
    }
    @data((POST_DATA_CONDITION_99, 4))
    @unpack
    def test_request_anslist_download_o100_c10_post_condition_99(self, post_data, expected_len):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            actual_response = self.client.post(self._get_url_download(), post_data)
            actual_content = actual_response.content
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)


class CourseAnslistDownloadAddTest(BizContractTestBase, BizStoreTestBase):

    def setUp(self):
        #super(AnslistTestBase, self).setUp()
        #super(BizViewTestBase, self).setUp()
        super(BizContractTestBase, self).setUp()
        self.setup_user()

        ## organization
        self.org100 = self._create_organization(org_name='gacco100', org_code='gacco-100', creator_org=self.gacco_organization)
        ## course
        self.course10 = CourseFactory.create(org='gacco', number='course10', run='run10')
        ## contract
        self.contract1 = self._create_contract(
                            contract_name='contract1', contractor_organization=self.org100,
                            detail_courses=[self.course10.id], additional_display_names=['country', 'dept'],
                            send_submission_reminder=True,
        )
        ## director user
        ### set up self.user for director
        self._director = self._create_manager(
            org=self.org100,
            user=self.user,
            created=self.org100,
            permissions=[self.director_permission]
        )
        ## user
        self.user10 = UserFactory.create(username='na10000', email='nauser10000@example.com')
        ## manager user10
        self._manager = self._create_manager(
            org=self.org100,
            user=self.user10,
            created=self.gacco_organization,
            permissions=[self.manager_permission]
        )
        self.user11 = UserFactory.create(username='na11000', email='nauser11000@example.com')
        self.user12 = UserFactory.create(username='na12000', email='nauser12000@example.com')

        ## register
        self.user60 = UserFactory.create(username='na60000', email='nauser60000@example.com')
        self.reg60 = self._register_contract(self.contract1, self.user60)


        ## group
        self.group1000 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='1000', group_name='G1000', org=self.org100,
            created_by=self.user, modified_by=self.user)
        self.group1100 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='1100', group_name='G1100', org=self.org100,
            created_by=self.user, modified_by=self.user)
        self.group1200 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='1200', group_name='G1200', org=self.org100,
            created_by=self.user, modified_by=self.user)

        ## member
        self.member10 = MemberFactory.create(
            org=self.org100,
            group=self.group1000,
            user=self.user10,
            code='0010',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco1',
        )
        self.member11 = MemberFactory.create(
            org=self.org100,
            group=self.group1100,
            user=self.user11,
            code='0011',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco1',
            org2='gacco11',
        )
        ## enrollment
        self.enroll10 = CourseEnrollmentFactory.create(user=self.user10, course_id=self.course10.id)
        self.enroll11 = CourseEnrollmentFactory.create(user=self.user11, course_id=self.course10.id)
        ### user10
        submission10_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user10,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission10_c10_survey1 = SurveySubmissionFactory.create(**submission10_c10_survey1_data)

        submission10_c10_survey2_data = {
            'course_id': self.course10.id,
            'unit_id': '22222222222222222222222222222222',
            'user': self.user10,
            'survey_name': 'survey2',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission10_c10_survey2 = SurveySubmissionFactory.create(**submission10_c10_survey2_data)

        ### user11
        submission11_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user11,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission11_c10_survey1 = SurveySubmissionFactory.create(**submission11_c10_survey1_data)

    POST_DATA_INIT_OFF = {
        u'group_id': [u''],
        u'survey_name': [u''],
        u'survey_answered': [u'on'],
        u'survey_not_answered': [u'on'],
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
        u'search': [u''],
        u'is_filter': u'off',
        u'limit': [u'100'],
        u'offset': [u'0'],
    }
    POST_DATA_INIT_ON = {
        u'group_id': [u''],
        u'survey_name': [u''],
        u'survey_answered': [u'on'],
        u'survey_not_answered': [u'on'],
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
        u'search': [u''],
        u'is_filter': u'on',
        u'limit': [u'100'],
        u'offset': [u'0'],
    }

    def _validate_bom(self, content):
        return self._validate_bom_utf16(content)

    def _validate_bom_utf16(self, content):
        # UTF8 no BOM
        return not content.startswith(codecs.BOM_UTF8)

    def _convert_csv_rows(self, content):
        body = content.rstrip('\n').replace('\r', '')
        return body.split('\n')

    def _get_url_download(self):
        return reverse('biz:course_anslist:status_download')

    def _get_url_search(self):
        return reverse('biz:course_anslist:status_search_api')

    def test_request_anslist_search_o100_c10_off(self):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            expected_len = 3 ##FIXME
            self.POST_DATA_INIT_OFF["search-download"] = "search-download"
            actual_response = self.client.post(self._get_url_search(), self.POST_DATA_INIT_OFF)
            self.assertEqual('application/json', actual_response['Content-Type'], )
            actual_content = actual_response.content
            json_obj = json.loads(actual_content)
            actual_len = len(json_obj)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)


    def test_request_anslist_download_o100_c10_off(self):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            expected_len = 5
            self.POST_DATA_INIT_OFF["search-download"] = "search-download"
            actual_response = self.client.post(self._get_url_download(), self.POST_DATA_INIT_OFF)
            self.assertEqual('text/tab-separated-values', actual_response['Content-Type'], )
            actual_content = actual_response.content
            self.assertTrue(self._validate_bom(actual_content))
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)


    def test_request_anslist_search_o100_c10_on(self):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            expected_len = 3
            self.POST_DATA_INIT_ON["search-download"] = "search-download"
            actual_response = self.client.post(self._get_url_search(), self.POST_DATA_INIT_ON)
            self.assertEqual('application/json', actual_response['Content-Type'], )
            actual_content = actual_response.content
            json_obj = json.loads(actual_content)
            actual_len = len(json_obj)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)


    def test_request_anslist_download_o100_c10_on(self):
        with self.skip_check_course_selection(current_organization=self.org100, current_contract=self.contract1,
                                              current_course=self.course10, current_manager=self._director):
            expected_len = 4
            self.POST_DATA_INIT_ON["search-download"] = "search-download"
            actual_response = self.client.post(self._get_url_download(), self.POST_DATA_INIT_ON)
            self.assertEqual('text/tab-separated-values', actual_response['Content-Type'], )
            actual_content = actual_response.content
            self.assertTrue(self._validate_bom(actual_content))
            rows = self._convert_csv_rows(actual_content)
            actual_len = len(rows)
            self.assertEqual(expected_len, actual_len)

        self.assertEqual(200, actual_response.status_code)

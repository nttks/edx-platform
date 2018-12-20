"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from collections import OrderedDict
from datetime import datetime
from ddt import ddt
import json
from mock import patch
import pytz

from django.core.urlresolvers import reverse
from django.http import HttpResponse

from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore, ScoreStore
from biz.djangoapps.ga_achievement.tests.factories import PlaybackFactory, ScoreFactory, PlaybackBatchStatusFactory, \
    ScoreBatchStatusFactory
from biz.djangoapps.ga_contract.tests.factories import ContractFactory
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_org_group.tests.factories import RightFactory, GroupUtil
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.tests.testcase import BizStoreTestBase, BizViewTestBase

from util.file import course_filename_prefix_generator
from student.tests.factories import UserFactory

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@ddt
class ScoreViewTest(BizStoreTestBase, BizViewTestBase, ModuleStoreTestCase):

    def _index_view(self):
        return reverse('biz:achievement:score')

    def _ajax_view(self):
        return reverse('biz:achievement:score_search_ajax')

    def _download_csv_view(self):
        return reverse('biz:achievement:score_download_csv')

    def _setup(self, is_achievement_data_empty=False, record_count=1):
        self.maxDiff = None  # over max character in assertDictEqual
        self.expect_record_list = []
        self._set_date()
        self.setup_user()
        self._create_course_data()
        self._create_org_data()
        self._create_contract_data()
        self._create_achievement_column()
        if not is_achievement_data_empty:
            for i in range(record_count):
                self._create_achievement_data(suffix=str(i))

    def _setup_and_user_create(self, is_achievement_data_empty=False, record_count=1):
        self.maxDiff = None  # over max character in assertDictEqual
        self.expect_record_list = []
        self._set_date()
        self.setup_user()
        self._create_course_data()
        self._create_org_data()
        self._create_contract_data()
        self._create_achievement_column()
        if not is_achievement_data_empty:
            for i in range(record_count):
                self._create_achievement_data_and_user(suffix=str(i))

    def _setup_and_user_create_not_group(self, is_achievement_data_empty=False, record_count=1):
        self.maxDiff = None  # over max character in assertDictEqual
        self.expect_record_list = []
        self._set_date()
        self.setup_user()
        self._create_course_data()
        self._create_org_data()
        self._create_contract_data()
        self._create_achievement_column()
        if not is_achievement_data_empty:
            for i in range(record_count):
                self._create_achievement_data_and_user_not_group(suffix=str(i))

    def _create_achievement_column(self):
        self.dict_column_data = {
            ScoreStore.FIELD_CONTRACT_ID: self.contract.id,
            ScoreStore.FIELD_COURSE_ID: unicode(self.course.id),
            ScoreStore.FIELD_DOCUMENT_TYPE: ScoreStore.FIELD_DOCUMENT_TYPE__COLUMN,
            ScoreStore.FIELD_FULL_NAME: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_USERNAME: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_EMAIL: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_STUDENT_STATUS: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_CERTIFICATE_STATUS: ScoreStore.COLUMN_TYPE__TIME,
            ScoreStore.FIELD_TOTAL_SCORE: ScoreStore.COLUMN_TYPE__PERCENT,
            'SECTIONS': ScoreStore.COLUMN_TYPE__TEXT,
        }

    def _set_date(self):
        self.utc_datetime = datetime(2016, 3, 1, 16, 58, 30, 0, tzinfo=pytz.utc)
        self.utc_datetime_update = datetime(2016, 3, 10, 16, 58, 30, 0, tzinfo=pytz.utc)

    def _create_course_data(self):
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')

    def _create_org_data(self):
        self.org_a = self._create_organization(org_name='a', org_code='a', creator_org=self.gacco_organization)

    def _create_contract_data(self):
        self.contract = self._create_contract('contract_a', self.org_a, self.gacco_organization,
                                              self.user, 'invitation_code_a')

    def _create_contract(self, name, contractor, owner, created_by, invitation_code):
        return ContractFactory.create(contract_name=name, contractor_organization=contractor, owner_organization=owner,
                                      created_by=created_by, invitation_code=invitation_code)

    def _create_achievement_data(self, suffix=''):
        self.dict_data = {
            ScoreStore.FIELD_CONTRACT_ID: self.contract.id,
            ScoreStore.FIELD_COURSE_ID: unicode(self.course.id),
            ScoreStore.FIELD_DOCUMENT_TYPE: ScoreStore.FIELD_DOCUMENT_TYPE__RECORD,
            ScoreStore.FIELD_FULL_NAME: 'TEST TEST{}'.format(suffix),
            ScoreStore.FIELD_USERNAME: 'TEST{}'.format(suffix),
            ScoreStore.FIELD_EMAIL: 'test{}@example.com'.format(suffix),
            ScoreStore.FIELD_STUDENT_STATUS: ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED,
            ScoreStore.FIELD_CERTIFICATE_STATUS: ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE,
            ScoreStore.FIELD_TOTAL_SCORE: 0.9,
            'SECTIONS': 'SECTION_{}'.format(suffix),
        }
        self.dict_data.update({ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: self.utc_datetime})
        self.expect_record_list.append(self.dict_data.copy())
        ScoreFactory.create(**self.dict_data)

    def _create_achievement_data_and_user(self, suffix=''):
        active_user = UserFactory.create()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        groups = Group.objects.filter(org=self.org_a, group_code='G02-01').first()
        MemberFactory.create(
            org=self.org_a,
            group=groups,
            user=active_user,
            code='code{}'.format(suffix),
            created_by=self.user,
            creator_org=self.org_a,
            updated_by=self.user,
            updated_org=self.org_a,
            is_active=True,
            is_delete=False,
            org1='org1',
        )
        self.dict_data = {
            ScoreStore.FIELD_CONTRACT_ID: self.contract.id,
            ScoreStore.FIELD_COURSE_ID: unicode(self.course.id),
            ScoreStore.FIELD_DOCUMENT_TYPE: ScoreStore.FIELD_DOCUMENT_TYPE__RECORD,
            ScoreStore.FIELD_FULL_NAME: 'TEST TEST{}'.format(suffix),
            ScoreStore.FIELD_USERNAME: active_user.username,
            ScoreStore.FIELD_EMAIL: active_user.email,
            ScoreStore.FIELD_STUDENT_STATUS: ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED,
            ScoreStore.FIELD_CERTIFICATE_STATUS: ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE,
            ScoreStore.FIELD_TOTAL_SCORE: 0.9,
            'SECTIONS': 'SECTION_{}'.format(suffix),
        }
        self.dict_data.update({ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: self.utc_datetime})

        self.expect_record_list.append(self.dict_data.copy())

        ScoreFactory.create(**self.dict_data)

    def _create_achievement_data_and_user_not_group(self, suffix=''):
        active_user = UserFactory.create()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        MemberFactory.create(
            org=self.org_a,
            group=None,
            user=active_user,
            code='code{}'.format(suffix),
            created_by=self.user,
            creator_org=self.org_a,
            updated_by=self.user,
            updated_org=self.org_a,
            is_active=True,
            is_delete=False,
            org1='org1',
        )
        self.dict_data = {
            ScoreStore.FIELD_CONTRACT_ID: self.contract.id,
            ScoreStore.FIELD_COURSE_ID: unicode(self.course.id),
            ScoreStore.FIELD_DOCUMENT_TYPE: ScoreStore.FIELD_DOCUMENT_TYPE__RECORD,
            ScoreStore.FIELD_FULL_NAME: 'TEST TEST{}'.format(suffix),
            ScoreStore.FIELD_USERNAME: active_user.username,
            ScoreStore.FIELD_EMAIL: active_user.email,
            ScoreStore.FIELD_STUDENT_STATUS: ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED,
            ScoreStore.FIELD_CERTIFICATE_STATUS: ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE,
            ScoreStore.FIELD_TOTAL_SCORE: 0.9,
            'SECTIONS': 'SECTION_{}'.format(suffix),
        }
        self.dict_data.update({ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: self.utc_datetime})

        self.expect_record_list.append(self.dict_data.copy())

        ScoreFactory.create(**self.dict_data)

    def _create_batch_status(self, status):
        self.batch_status = ScoreBatchStatusFactory.create(contract=self.contract,
                                                           course_id=unicode(self.course.id),
                                                           status=status,
                                                           student_count=4)

    def _assert_student_status(self, student_status):
        self.assertEqual(student_status, [
            ScoreStore.FIELD_STUDENT_STATUS__NOT_ENROLLED,
            ScoreStore.FIELD_STUDENT_STATUS__ENROLLED,
            ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED,
            ScoreStore.FIELD_STUDENT_STATUS__DISABLED,
            ScoreStore.FIELD_STUDENT_STATUS__EXPIRED
        ])

    def _get_csv_file_name(self, str_datetime):
        return u'{course_prefix}_{csv_name}_{timestamp_str}.csv'.format(
            course_prefix=course_filename_prefix_generator(self.course.id),
            csv_name='score_status',
            timestamp_str=str_datetime
        )

    def _assert_column_data(self, columns):
        self.assertDictEqual(dict(json.loads(columns)), {
            ScoreStore.FIELD_USERNAME: 'text',
            ScoreStore.FIELD_CERTIFICATE_STATUS: 'text',
            ScoreStore.FIELD_TOTAL_SCORE: 'percent',
            ScoreStore.FIELD_STUDENT_STATUS: 'text',
            ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: 'date',
            ScoreStore.FIELD_DOCUMENT_TYPE: 'text',
            'SECTIONS': 'text',
            ScoreStore.FIELD_FULL_NAME: 'text',
            ScoreStore.FIELD_EMAIL: 'text',
            'Organization Groups': 'text',
            'Organization1': 'text',
            'Organization2': 'text',
            'Organization3': 'text',
            'Organization4': 'hidden',
            'Organization5': 'hidden',
            'Organization6': 'hidden',
            'Organization7': 'hidden',
            'Organization8': 'hidden',
            'Organization9': 'hidden',
            'Organization10': 'hidden',
            'Item1': 'text',
            'Item2': 'text',
            'Item3': 'text',
            'Item4': 'hidden',
            'Item5': 'hidden',
            'Item6': 'hidden',
            'Item7': 'hidden',
            'Item8': 'hidden',
            'Item9': 'hidden',
            'Item10': 'hidden',
        })

    def _assert_status_list(self, status_list):
        self.assertEqual(status_list, {
            'Unregister': 'Unregister Invitation',
            'Input': 'Input Invitation',
            'Register': 'Register Invitation'
        })

    def _assert_member_org_item_list(self, member_org_item_list):
        self.assertEqual(member_org_item_list, OrderedDict([
            ('org1', 'Organization1'),
            ('org2', 'Organization2'),
            ('org3', 'Organization3'),
            ('org4', 'Organization4'),
            ('org5', 'Organization5'),
            ('org6', 'Organization6'),
            ('org7', 'Organization7'),
            ('org8', 'Organization8'),
            ('org9', 'Organization9'),
            ('org10', 'Organization10'),
            ('item1', 'Item1'),
            ('item2', 'Item2'),
            ('item3', 'Item3'),
            ('item4', 'Item4'),
            ('item5', 'Item5'),
            ('item6', 'Item6'),
            ('item7', 'Item7'),
            ('item8', 'Item8'),
            ('item9', 'Item9'),
            ('item10', 'Item10'),
        ]))

    def _assert_record_data(self, records):
        expect = {
            ScoreStore.FIELD_FULL_NAME: self.dict_data[ScoreStore.FIELD_FULL_NAME],
            ScoreStore.FIELD_USERNAME: self.dict_data[ScoreStore.FIELD_USERNAME],
            ScoreStore.FIELD_EMAIL: self.dict_data[ScoreStore.FIELD_EMAIL],
            ScoreStore.FIELD_STUDENT_STATUS: self.dict_data[ScoreStore.FIELD_STUDENT_STATUS],
            ScoreStore.FIELD_CERTIFICATE_STATUS: self.dict_data[ScoreStore.FIELD_CERTIFICATE_STATUS],
            ScoreStore.FIELD_TOTAL_SCORE: self.dict_data[ScoreStore.FIELD_TOTAL_SCORE],
            ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: datetime_utils.format_for_w2ui(
                self.dict_data[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE]),
            'SECTIONS': self.dict_data['SECTIONS'],
            ScoreStore.FIELD_DOCUMENT_TYPE: self.dict_data[ScoreStore.FIELD_DOCUMENT_TYPE],
            u'recid': 1,
        }
        self.assertDictEqual(json.loads(records)[0], json.loads(unicode(json.dumps(expect))))

    def _assert_record_data_member(self, records):
        expect = {
            ScoreStore.FIELD_FULL_NAME: self.dict_data[ScoreStore.FIELD_FULL_NAME],
            ScoreStore.FIELD_USERNAME: self.dict_data[ScoreStore.FIELD_USERNAME],
            ScoreStore.FIELD_EMAIL: self.dict_data[ScoreStore.FIELD_EMAIL],
            ScoreStore.FIELD_STUDENT_STATUS: self.dict_data[ScoreStore.FIELD_STUDENT_STATUS],
            ScoreStore.FIELD_CERTIFICATE_STATUS: self.dict_data[ScoreStore.FIELD_CERTIFICATE_STATUS],
            ScoreStore.FIELD_TOTAL_SCORE: self.dict_data[ScoreStore.FIELD_TOTAL_SCORE],
            ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE:
                datetime_utils.format_for_w2ui(self.dict_data[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE]),
            'SECTIONS': self.dict_data['SECTIONS'],
            ScoreStore.FIELD_DOCUMENT_TYPE: self.dict_data[ScoreStore.FIELD_DOCUMENT_TYPE],
            "Organization Groups": "G2-1",
            "Organization1": 'org1',
            "Organization2": None,
            "Organization3": None,
            "Organization4": None,
            "Organization5": None,
            "Organization6": None,
            "Organization7": None,
            "Organization8": None,
            "Organization9": None,
            "Organization10": None,
            "Item1": None,
            "Item2": None,
            "Item3": None,
            "Item4": None,
            "Item5": None,
            "Item6": None,
            "Item7": None,
            "Item8": None,
            "Item9": None,
            "Item10": None,
            'recid': 1,
        }
        self.assertDictEqual(json.loads(records)[0], json.loads(unicode(json.dumps(expect))))

    def _assert_record_count(self, records_count, expect_records_count):
        self.assertEqual(records_count, expect_records_count)

    def _create_param_search_ajax(self):
        param = {
            'student_status': '',
            'group_code': '',
            'offset': 0,
            'limit': 100,
            'certificate_status': '',
            'total_score_from': '',
            'total_score_to': '',
            'detail_condition_member_name_1': '',
            'detail_condition_member_1': '',
        }
        for i in range(1, 6):
            param['detail_condition_member_' + str(i)] = ''
            param['detail_condition_member_name_' + str(i)] = ''
            param['detail_condition_score_from_' + str(i)] = ''
            param['detail_condition_score_name_' + str(i)] = ''
            param['detail_condition_score_to_' + str(i)] = ''
        return param

    def test_index_views(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/score.html')

        self._assert_record_count(render_to_response_args[1]['update_datetime'],
                                  datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['score_columns'])
        self._assert_status_list(render_to_response_args[1]['status_list'])
        self._assert_member_org_item_list(render_to_response_args[1]['member_org_item_list'])
        self.assertEqual(render_to_response_args[1]['group_list'], [])
        self._assert_student_status(render_to_response_args[1]['student_status'])
        self.assertEqual(render_to_response_args[1]['score_section_names'], ['SECTIONS'])
        self._assert_record_data(render_to_response_args[1]['score_records'])

    def test_index_views_manager(self):
        status = 'Finished'

        self._setup()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.manager_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/score.html')

        self._assert_record_count(render_to_response_args[1]['update_datetime'],
                                  datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['score_columns'])
        self._assert_status_list(render_to_response_args[1]['status_list'])
        self._assert_member_org_item_list(render_to_response_args[1]['member_org_item_list'])
        self.assertEqual(render_to_response_args[1]['group_list'], [])
        self._assert_student_status(render_to_response_args[1]['student_status'])
        self.assertEqual(render_to_response_args[1]['score_section_names'], ['SECTIONS'])
        self.assertEqual('[]', render_to_response_args[1]['score_records'])

    def test_index_views_status_none(self):
        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/score.html')

        self._assert_record_count(render_to_response_args[1]['update_datetime'], '')
        self.assertEqual(render_to_response_args[1]['update_status'], '')
        self._assert_column_data(render_to_response_args[1]['score_columns'])
        self._assert_status_list(render_to_response_args[1]['status_list'])
        self._assert_member_org_item_list(render_to_response_args[1]['member_org_item_list'])
        self.assertEqual(render_to_response_args[1]['group_list'], [])
        self._assert_student_status(render_to_response_args[1]['student_status'])
        self.assertEqual(render_to_response_args[1]['score_section_names'], ['SECTIONS'])
        self._assert_record_data(render_to_response_args[1]['score_records'])

    def test_index_views_member(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/score.html')

        self._assert_record_count(render_to_response_args[1]['update_datetime'],
                                  datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['score_columns'])
        self._assert_status_list(render_to_response_args[1]['status_list'])
        self._assert_member_org_item_list(render_to_response_args[1]['member_org_item_list'])
        self.assertEqual(render_to_response_args[1]['group_list'], [
            (u'G01', 9, u'G1'), (u'G01-01', 3, u'G1-1'), (u'G01-01-01', 8, u'G1-1-1'), (u'G01-01-02', 7, u'G1-1-2'),
            (u'G01-02', 4, u'G1-2'), (u'G02', 10, u'G2'), (u'G02-01', 5, u'G2-1'), (u'G02-01-01', 1, u'G2-1-1'),
            (u'G02-01-02', 2, u'G2-1-2'), (u'G02-02', 6, u'G2-2')])
        self._assert_student_status(render_to_response_args[1]['student_status'])
        self.assertEqual(render_to_response_args[1]['score_section_names'], ['SECTIONS'])
        self._assert_record_data_member(render_to_response_args[1]['score_records'])

    def test_index_views_member_manager(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager_manager = self._create_manager(
            org=self.org_a, user=self.user, created=self.contract, permissions=[self.manager_permission])
        groups = Group.objects.filter(org=self.org_a, group_code='G01-01').first()
        RightFactory.create(org=self.org_a, group=groups, user=manager_manager.user, created_by=self.user,
                            creator_org=self.org_a)

        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager_manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/score.html')

        self._assert_record_count(render_to_response_args[1]['update_datetime'],
                                  datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['score_columns'])
        self._assert_status_list(render_to_response_args[1]['status_list'])
        self._assert_member_org_item_list(render_to_response_args[1]['member_org_item_list'])
        self.assertEqual(render_to_response_args[1]['group_list'],
                         [(u'G01-01', 3, u'G1-1'), (u'G01-01-01', 8, u'G1-1-1'), (u'G01-01-02', 7, u'G1-1-2')])
        self._assert_student_status(render_to_response_args[1]['student_status'])
        self.assertEqual(render_to_response_args[1]['score_section_names'], ['SECTIONS'])
        self.assertEqual('[]', render_to_response_args[1]['score_records'])

    def test_search_ajax(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['detail_condition_score_name_1'] = ''
            post_value['detail_condition_score_from_1'] = ''
            post_value['detail_condition_score_to_1'] = ''
            post_value['detail_condition_score_no_1'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_mismatch(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = '0'
            post_value['total_score_to'] = '0'
            post_value['detail_condition_score_name_1'] = 'SECTION_1'
            post_value['detail_condition_score_from_1'] = '0'
            post_value['detail_condition_score_to_1'] = '0'
            post_value['detail_condition_score_no_1'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_score_no(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['total_score_no'] = 'True'
            post_value['detail_condition_score_name_1'] = ''
            post_value['detail_condition_score_from_1'] = ''
            post_value['detail_condition_score_to_1'] = ''
            post_value['detail_condition_score_no_1'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_score_student_status(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['total_score_no'] = 'True'
            post_value['detail_condition_score_name_1'] = ''
            post_value['detail_condition_score_from_1'] = ''
            post_value['detail_condition_score_to_1'] = ''
            post_value['detail_condition_score_no_1'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_certificate_status(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['detail_condition_score_name_1'] = ''
            post_value['detail_condition_score_from_1'] = ''
            post_value['detail_condition_score_to_1'] = ''
            post_value['detail_condition_score_no_1'] = ''
            post_value['certificate_status'] = ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_detail_condition(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['detail_condition_score_name_1'] = 'SECTION_1'
            post_value['detail_condition_score_from_1'] = '0'
            post_value['detail_condition_score_to_1'] = '0'
            post_value['detail_condition_score_no_1'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_manager(self):
        status = 'Finished'

        self._setup()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.manager_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['detail_condition_score_name_1'] = ''
            post_value['detail_condition_score_from_1'] = ''
            post_value['detail_condition_score_to_1'] = ''
            post_value['detail_condition_score_no_1'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_intentional_exception(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = '0'
            post_value['total_score_to'] = '0'
            post_value['detail_condition_score_name_1'] = 'SECTION_1'
            post_value['detail_condition_score_from_1'] = '0'
            post_value['detail_condition_score_to_1'] = '0'
            post_value['detail_condition_score_no_1'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0.1'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(400, response.status_code)

    def test_search_ajax_not_list_detail_member(self):
        status = 'Finished'

        self._setup()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['detail_condition_score_name_1'] = ''
            post_value['detail_condition_score_from_1'] = ''
            post_value['detail_condition_score_to_1'] = ''
            post_value['detail_condition_score_no_1'] = ''
            post_value['detail_condition_member_name_1'] = ''
            post_value['detail_condition_member_name_2'] = 'org1'
            post_value['detail_condition_member_1'] = ''
            post_value['detail_condition_member_2'] = 'org1'
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_not_list_group_code(self):
        status = 'Finished'

        self._setup()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['detail_condition_score_name_1'] = ''
            post_value['detail_condition_score_from_1'] = ''
            post_value['detail_condition_score_to_1'] = ''
            post_value['detail_condition_score_no_1'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = '1234'
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_member_not_value(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['detail_condition_member_name_1'] = 'org1'
            post_value['detail_condition_member_1'] = 'abc'
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_member_group_none(self):
        status = 'Finished'

        self._setup_and_user_create_not_group()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = '1234'
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_member_group_mismatch(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = '1234'
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_member_manager(self):
        status = 'Finished'

        self._setup_and_user_create()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.manager_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['detail_condition_member_name_1'] = ''
            post_value['detail_condition_member_1'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_member_success(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_score_from'] = ''
            post_value['total_score_to'] = ''
            post_value['certificate_status'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_download_csv(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))

    def test_download_csv_batch_status_none(self):
        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name('no-timestamp')
        ))

    def test_download_csv_manager(self):
        status = 'Finished'

        self._setup()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.manager_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))

    def test_download_csv_member(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))

    def test_download_csv_member_manager(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.manager_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))

    def test_download_csv_field_types(self):
        status = 'Finished'

        self._setup(is_achievement_data_empty=True)
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        self.dict_column_data = {
            ScoreStore.FIELD_CONTRACT_ID: self.contract.id,
            ScoreStore.FIELD_COURSE_ID: unicode(self.course.id),
            ScoreStore.FIELD_DOCUMENT_TYPE: ScoreStore.FIELD_DOCUMENT_TYPE__COLUMN,
            ScoreStore.FIELD_FULL_NAME: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_USERNAME: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_EMAIL: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_STUDENT_STATUS: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_CERTIFICATE_STATUS: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_TOTAL_SCORE: ScoreStore.COLUMN_TYPE__TEXT,
            'SECTIONS_1': ScoreStore.COLUMN_TYPE__TEXT,
            'SECTIONS_2': ScoreStore.COLUMN_TYPE__TEXT,
            'SECTIONS_3': ScoreStore.COLUMN_TYPE__DATE,
            'SECTIONS_4': ScoreStore.COLUMN_TYPE__DATE,
            'SECTIONS_5': ScoreStore.COLUMN_TYPE__TIME,
            'SECTIONS_6': ScoreStore.COLUMN_TYPE__TIME,
            'SECTIONS_7': ScoreStore.COLUMN_TYPE__PERCENT,
            'SECTIONS_8': ScoreStore.COLUMN_TYPE__PERCENT,
            'SECTIONS_9': ScoreStore.COLUMN_TYPE__PERCENT,
            'SECTIONS_10': 'UnknownType',
            'SECTIONS_11': ScoreStore.COLUMN_TYPE__TIME,
        }
        ScoreFactory.create(**self.dict_column_data)
        suffix = 1
        self.dict_data = {
            ScoreStore.FIELD_CONTRACT_ID: self.contract.id,
            ScoreStore.FIELD_COURSE_ID: unicode(self.course.id),
            ScoreStore.FIELD_DOCUMENT_TYPE: ScoreStore.FIELD_DOCUMENT_TYPE__RECORD,
            ScoreStore.FIELD_FULL_NAME: 'TEST TEST{}'.format(suffix),
            ScoreStore.FIELD_USERNAME: 'TEST{}'.format(suffix),
            ScoreStore.FIELD_EMAIL: 'test{}@example.com'.format(suffix),
            ScoreStore.FIELD_STUDENT_STATUS: ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED,
            ScoreStore.FIELD_CERTIFICATE_STATUS: ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE,
            ScoreStore.FIELD_TOTAL_SCORE: 0.9,
            'SECTIONS_1': 'SECTION_{}'.format(suffix),
            'SECTIONS_2': suffix,
            'SECTIONS_3': datetime(2016, 3, 10, 16, 58, 30, 0, tzinfo=pytz.utc),
            'SECTIONS_4': '',
            'SECTIONS_5': '1',
            'SECTIONS_6': '',
            'SECTIONS_7': ScoreStore.VALUE__NOT_ATTEMPTED,
            'SECTIONS_8': 0.5,
            'SECTIONS_9': '',
            'SECTIONS_10': None,
            'SECTIONS_11': 0.5,
        }
        self.expect_record_list.append(self.dict_data.copy())
        ScoreFactory.create(**self.dict_data)

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))

    def test_download_searched_csv(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):

            param = self._create_param_search_ajax()
            param["search-download"] = "search-download"
            response = self.client.post(self._download_csv_view(), param)

        self.assertEqual(200, response.status_code)

@ddt
class PlaybackViewTest(BizStoreTestBase, BizViewTestBase, ModuleStoreTestCase):

    def _index_view(self):
        return reverse('biz:achievement:playback')

    def _ajax_view(self):
        return reverse('biz:achievement:playback_search_ajax')

    def _download_csv_view(self):
        return reverse('biz:achievement:playback_download_csv')

    def _setup(self, is_achievement_data_empty=False, record_count=1):
        self.expect_record_list = []
        self._set_date()
        self.setup_user()
        self._create_course_data()
        self._create_org_data()
        self._create_contract_data()
        if not is_achievement_data_empty:
            for i in range(record_count):
                self._create_achievement_data(suffix=str(i))

    def _setup_and_user_create(self, is_achievement_data_empty=False, record_count=1):
        self.expect_record_list = []
        self._set_date()
        self.setup_user()
        self._create_course_data()
        self._create_org_data()
        self._create_contract_data()
        if not is_achievement_data_empty:
            for i in range(record_count):
                self._create_achievement_data_and_user(suffix=str(i))

    def _setup_and_user_create_not_group(self, is_achievement_data_empty=False, record_count=1):
        self.expect_record_list = []
        self._set_date()
        self.setup_user()
        self._create_course_data()
        self._create_org_data()
        self._create_contract_data()
        if not is_achievement_data_empty:
            for i in range(record_count):
                self._create_achievement_data_and_user_not_group(suffix=str(i))

    def _set_date(self):
        self.utc_datetime_update = datetime(2016, 3, 10, 16, 58, 30, 0, tzinfo=pytz.utc)

    def _create_course_data(self):
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')

    def _create_org_data(self):
        self.org_a = self._create_organization(org_name='a', org_code='a', creator_org=self.gacco_organization)

    def _create_contract_data(self):
        self.contract = self._create_contract('contract_a', self.org_a, self.gacco_organization,
                                              self.user, 'invitation_code_a')

    def _create_contract(self, name, contractor, owner, created_by, invitation_code):
        return ContractFactory.create(contract_name=name, contractor_organization=contractor, owner_organization=owner,
                                      created_by=created_by, invitation_code=invitation_code)

    def _create_achievement_data(self, suffix=''):
        self.dict_column_data = {
            PlaybackStore.FIELD_CONTRACT_ID: self.contract.id,
            PlaybackStore.FIELD_COURSE_ID: unicode(self.course.id),
            PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN,
            PlaybackStore.FIELD_FULL_NAME: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_USERNAME: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_EMAIL: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_STUDENT_STATUS: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: PlaybackStore.COLUMN_TYPE__TIME,
            'SECTIONS': ScoreStore.COLUMN_TYPE__TEXT,
        }
        PlaybackFactory.create(**self.dict_column_data)
        self.dict_record_data = {
            PlaybackStore.FIELD_CONTRACT_ID: self.contract.id,
            PlaybackStore.FIELD_COURSE_ID: unicode(self.course.id),
            PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD,
            PlaybackStore.FIELD_FULL_NAME: 'TEST TEST{}'.format(suffix),
            PlaybackStore.FIELD_USERNAME: 'TEST{}'.format(suffix),
            PlaybackStore.FIELD_EMAIL: 'test{}@example.com'.format(suffix),
            PlaybackStore.FIELD_STUDENT_STATUS: PlaybackStore.FIELD_STUDENT_STATUS__UNENROLLED,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: 999,
            'SECTIONS': 'SECTION_{}'.format(suffix),
        }

        self.expect_record_list.append(self.dict_record_data.copy())

        PlaybackFactory.create(**self.dict_record_data)

    def _create_achievement_data_and_user(self, suffix=''):
        active_user = UserFactory.create()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        groups = Group.objects.filter(org=self.org_a, group_code='G02-01').first()
        MemberFactory.create(
            org=self.org_a,
            group=groups,
            user=active_user,
            code='code{}'.format(suffix),
            created_by=self.user,
            creator_org=self.org_a,
            updated_by=self.user,
            updated_org=self.org_a,
            is_active=True,
            is_delete=False,
            org1='org1',
        )
        self.dict_column_data = {
            PlaybackStore.FIELD_CONTRACT_ID: self.contract.id,
            PlaybackStore.FIELD_COURSE_ID: unicode(self.course.id),
            PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN,
            PlaybackStore.FIELD_FULL_NAME: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_USERNAME: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_EMAIL: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_STUDENT_STATUS: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: PlaybackStore.COLUMN_TYPE__TIME,
            'SECTIONS': ScoreStore.COLUMN_TYPE__TEXT,
        }
        PlaybackFactory.create(**self.dict_column_data)
        self.dict_record_data = {
            PlaybackStore.FIELD_CONTRACT_ID: self.contract.id,
            PlaybackStore.FIELD_COURSE_ID: unicode(self.course.id),
            PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD,
            PlaybackStore.FIELD_FULL_NAME: 'TEST TEST{}'.format(suffix),
            PlaybackStore.FIELD_USERNAME: active_user.username,
            PlaybackStore.FIELD_EMAIL: active_user.email,
            PlaybackStore.FIELD_STUDENT_STATUS: PlaybackStore.FIELD_STUDENT_STATUS__UNENROLLED,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: 999,
            'SECTIONS': 'SECTION_{}'.format(suffix),
        }

        self.expect_record_list.append(self.dict_record_data.copy())

        PlaybackFactory.create(**self.dict_record_data)

    def _create_achievement_data_and_user_not_group(self, suffix=''):
        active_user = UserFactory.create()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        MemberFactory.create(
            org=self.org_a,
            group=None,
            user=active_user,
            code='code{}'.format(suffix),
            created_by=self.user,
            creator_org=self.org_a,
            updated_by=self.user,
            updated_org=self.org_a,
            is_active=True,
            is_delete=False,
            org1='org1',
        )
        self.dict_column_data = {
            PlaybackStore.FIELD_CONTRACT_ID: self.contract.id,
            PlaybackStore.FIELD_COURSE_ID: unicode(self.course.id),
            PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN,
            PlaybackStore.FIELD_FULL_NAME: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_USERNAME: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_EMAIL: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_STUDENT_STATUS: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: PlaybackStore.COLUMN_TYPE__TIME,
            'SECTIONS': ScoreStore.COLUMN_TYPE__TEXT,
        }
        PlaybackFactory.create(**self.dict_column_data)
        self.dict_record_data = {
            PlaybackStore.FIELD_CONTRACT_ID: self.contract.id,
            PlaybackStore.FIELD_COURSE_ID: unicode(self.course.id),
            PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD,
            PlaybackStore.FIELD_FULL_NAME: 'TEST TEST{}'.format(suffix),
            PlaybackStore.FIELD_USERNAME: active_user.username,
            PlaybackStore.FIELD_EMAIL: active_user.email,
            PlaybackStore.FIELD_STUDENT_STATUS: PlaybackStore.FIELD_STUDENT_STATUS__UNENROLLED,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: 999,
            'SECTIONS': 'SECTION_{}'.format(suffix),
        }

        self.expect_record_list.append(self.dict_record_data.copy())

        PlaybackFactory.create(**self.dict_record_data)

    def _create_batch_status(self, status):
        self.batch_status = PlaybackBatchStatusFactory.create(contract=self.contract,
                                                              course_id=unicode(self.course.id),
                                                              status=status,
                                                              student_count=4)

    def _create_param_search_ajax(self):
        param = {
            'student_status': '',
            'group_code': '',
            'offset': 0,
            'limit': 100,
            'total_playback_time_from': '',
            'total_playback_time_to': '',
        }
        for i in range(1, 6):
            param['detail_condition_member_' + str(i)] = ''
            param['detail_condition_member_name_' + str(i)] = ''
            param['detail_condition_playback_from_' + str(i)] = ''
            param['detail_condition_playback_name_' + str(i)] = ''
            param['detail_condition_playback_to_' + str(i)] = ''
        return param

    def _assert_student_status(self, student_status):
        self.assertEqual(student_status, [
            ScoreStore.FIELD_STUDENT_STATUS__NOT_ENROLLED,
            ScoreStore.FIELD_STUDENT_STATUS__ENROLLED,
            ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED,
            ScoreStore.FIELD_STUDENT_STATUS__DISABLED,
            ScoreStore.FIELD_STUDENT_STATUS__EXPIRED
        ])

    def _get_csv_file_name(self, str_datetime):
        return u'{course_prefix}_{csv_name}_{timestamp_str}.csv'.format(
            course_prefix=course_filename_prefix_generator(self.course.id),
            csv_name='playback_status',
            timestamp_str=str_datetime
        )

    def _assert_column_data(self, columns):
        self.assertDictEqual(dict(json.loads(columns)), {
            PlaybackStore.FIELD_FULL_NAME: self.dict_column_data[PlaybackStore.FIELD_FULL_NAME],
            PlaybackStore.FIELD_USERNAME: self.dict_column_data[PlaybackStore.FIELD_USERNAME],
            PlaybackStore.FIELD_EMAIL: self.dict_column_data[PlaybackStore.FIELD_EMAIL],
            PlaybackStore.FIELD_STUDENT_STATUS: self.dict_column_data[PlaybackStore.FIELD_STUDENT_STATUS],
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: self.dict_column_data[PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME],
            'SECTIONS': 'text',
            "Organization Groups": "text",
            'Organization1': 'text',
            'Organization2': 'text',
            'Organization3': 'text',
            'Organization4': 'hidden',
            'Organization5': 'hidden',
            'Organization6': 'hidden',
            'Organization7': 'hidden',
            'Organization8': 'hidden',
            'Organization9': 'hidden',
            'Organization10': 'hidden',
            'Item1': 'text',
            'Item2': 'text',
            'Item3': 'text',
            'Item4': 'hidden',
            'Item5': 'hidden',
            'Item6': 'hidden',
            'Item7': 'hidden',
            'Item8': 'hidden',
            'Item9': 'hidden',
            'Item10': 'hidden',
        })

    def _assert_status_list(self, status_list):
        self.assertEqual(status_list, {
            'Unregister': 'Unregister Invitation',
            'Input': 'Input Invitation',
            'Register': 'Register Invitation'
        })

    def _assert_member_org_item_list(self, member_org_item_list):
        self.assertEqual(member_org_item_list, OrderedDict([
            ('org1', 'Organization1'),
            ('org2', 'Organization2'),
            ('org3', 'Organization3'),
            ('org4', 'Organization4'),
            ('org5', 'Organization5'),
            ('org6', 'Organization6'),
            ('org7', 'Organization7'),
            ('org8', 'Organization8'),
            ('org9', 'Organization9'),
            ('org10', 'Organization10'),
            ('item1', 'Item1'),
            ('item2', 'Item2'),
            ('item3', 'Item3'),
            ('item4', 'Item4'),
            ('item5', 'Item5'),
            ('item6', 'Item6'),
            ('item7', 'Item7'),
            ('item8', 'Item8'),
            ('item9', 'Item9'),
            ('item10', 'Item10'),
        ]))

    def _assert_record_data(self, records):
        expect = {
            PlaybackStore.FIELD_FULL_NAME: self.dict_record_data[PlaybackStore.FIELD_FULL_NAME],
            PlaybackStore.FIELD_USERNAME: self.dict_record_data[PlaybackStore.FIELD_USERNAME],
            PlaybackStore.FIELD_EMAIL: self.dict_record_data[PlaybackStore.FIELD_EMAIL],
            PlaybackStore.FIELD_STUDENT_STATUS:
                self.dict_record_data[PlaybackStore.FIELD_STUDENT_STATUS],
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: self.dict_record_data[
                PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME],
            PlaybackStore.FIELD_DOCUMENT_TYPE:
                self.dict_record_data[PlaybackStore.FIELD_DOCUMENT_TYPE],
            'SECTIONS': self.dict_record_data['SECTIONS'],
            u'recid': 1,
        }
        self.assertDictEqual(json.loads(records)[0], json.loads(unicode(json.dumps(expect))))

    def _assert_record_data_member(self, records):
        expect = {
            PlaybackStore.FIELD_FULL_NAME: self.dict_record_data[PlaybackStore.FIELD_FULL_NAME],
            PlaybackStore.FIELD_USERNAME: self.dict_record_data[PlaybackStore.FIELD_USERNAME],
            PlaybackStore.FIELD_EMAIL: self.dict_record_data[PlaybackStore.FIELD_EMAIL],
            PlaybackStore.FIELD_STUDENT_STATUS:
                self.dict_record_data[PlaybackStore.FIELD_STUDENT_STATUS],
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: self.dict_record_data[
                PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME],
            PlaybackStore.FIELD_DOCUMENT_TYPE:
                self.dict_record_data[PlaybackStore.FIELD_DOCUMENT_TYPE],
            'SECTIONS': self.dict_record_data['SECTIONS'],
            "Organization Groups": "G2-1",
            "Organization1": 'org1',
            "Organization2": None,
            "Organization3": None,
            "Organization4": None,
            "Organization5": None,
            "Organization6": None,
            "Organization7": None,
            "Organization8": None,
            "Organization9": None,
            "Organization10": None,
            "Item1": None,
            "Item2": None,
            "Item3": None,
            "Item4": None,
            "Item5": None,
            "Item6": None,
            "Item7": None,
            "Item8": None,
            "Item9": None,
            "Item10": None,
            u'recid': 1,
        }
        self.assertDictEqual(json.loads(records)[0], json.loads(unicode(json.dumps(expect))))

    def _assert_record_count(self, records_count, expect_records_count):
        self.assertEqual(records_count, expect_records_count)

    def test_index_views(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/playback.html')

        self._assert_record_count(render_to_response_args[1]['update_datetime'],
                                  datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['playback_columns'])
        self._assert_record_data(render_to_response_args[1]['playback_records'])
        self._assert_status_list(render_to_response_args[1]['status_list'])
        self._assert_member_org_item_list(render_to_response_args[1]['member_org_item_list'])
        self.assertEqual(render_to_response_args[1]['group_list'], [])
        self._assert_student_status(render_to_response_args[1]['student_status'])
        self.assertEqual(render_to_response_args[1]['playback_section_names'], ['SECTIONS'])

    def test_index_views_manager(self):
        status = 'Finished'

        self._setup()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.manager_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/playback.html')

        self._assert_record_count(render_to_response_args[1]['update_datetime'],
                                  datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['playback_columns'])
        self._assert_status_list(render_to_response_args[1]['status_list'])
        self._assert_member_org_item_list(render_to_response_args[1]['member_org_item_list'])
        self.assertEqual(render_to_response_args[1]['group_list'], [])
        self._assert_student_status(render_to_response_args[1]['student_status'])
        self.assertEqual(render_to_response_args[1]['playback_section_names'], ['SECTIONS'])

    def test_index_views_status_none(self):
        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/playback.html')

        self._assert_record_count(render_to_response_args[1]['update_datetime'], '')
        self.assertEqual(render_to_response_args[1]['update_status'], '')
        self._assert_column_data(render_to_response_args[1]['playback_columns'])
        self._assert_record_data(render_to_response_args[1]['playback_records'])
        self._assert_status_list(render_to_response_args[1]['status_list'])
        self._assert_member_org_item_list(render_to_response_args[1]['member_org_item_list'])
        self.assertEqual(render_to_response_args[1]['group_list'], [])
        self._assert_student_status(render_to_response_args[1]['student_status'])
        self.assertEqual(render_to_response_args[1]['playback_section_names'], ['SECTIONS'])

    def test_index_views_member(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/playback.html')

        self._assert_record_count(render_to_response_args[1]['update_datetime'],
                                  datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['playback_columns'])
        self._assert_status_list(render_to_response_args[1]['status_list'])
        self._assert_record_data_member(render_to_response_args[1]['playback_records'])
        self._assert_member_org_item_list(render_to_response_args[1]['member_org_item_list'])
        self.assertEqual(render_to_response_args[1]['group_list'], [
            (u'G01', 9, u'G1'), (u'G01-01', 3, u'G1-1'), (u'G01-01-01', 8, u'G1-1-1'), (u'G01-01-02', 7, u'G1-1-2'),
            (u'G01-02', 4, u'G1-2'), (u'G02', 10, u'G2'), (u'G02-01', 5, u'G2-1'), (u'G02-01-01', 1, u'G2-1-1'),
            (u'G02-01-02', 2, u'G2-1-2'), (u'G02-02', 6, u'G2-2')])
        self._assert_student_status(render_to_response_args[1]['student_status'])
        self.assertEqual(render_to_response_args[1]['playback_section_names'], ['SECTIONS'])

    def test_index_views_member_manager(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager_manager = self._create_manager(
            org=self.org_a, user=self.user, created=self.contract, permissions=[self.manager_permission])
        groups = Group.objects.filter(org=self.org_a, group_code='G01-01').first()
        RightFactory.create(org=self.org_a, group=groups, user=manager_manager.user, created_by=self.user,
                            creator_org=self.org_a)

        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager_manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/playback.html')

        self._assert_record_count(render_to_response_args[1]['update_datetime'],
                                  datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['playback_columns'])
        self._assert_status_list(render_to_response_args[1]['status_list'])
        self._assert_member_org_item_list(render_to_response_args[1]['member_org_item_list'])
        self.assertEqual(render_to_response_args[1]['group_list'],
                         [(u'G01-01', 3, u'G1-1'), (u'G01-01-01', 8, u'G1-1-1'), (u'G01-01-02', 7, u'G1-1-2')])
        self._assert_student_status(render_to_response_args[1]['student_status'])
        self.assertEqual(render_to_response_args[1]['playback_section_names'], ['SECTIONS'])

    def test_search_ajax(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['detail_condition_playback_name_1'] = ''
            post_value['detail_condition_playback_from_1'] = ''
            post_value['detail_condition_playback_to_1'] = ''
            post_value['detail_condition_playback_no_1'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_mismatch(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = '0'
            post_value['total_playback_time_to'] = '0'
            post_value['detail_condition_playback_name_1'] = 'SECTION_1'
            post_value['detail_condition_playback_from_1'] = '0'
            post_value['detail_condition_playback_to_1'] = '0'
            post_value['detail_condition_playback_no_1'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_student_status(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ScoreStore.FIELD_STUDENT_STATUS__ENROLLED
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['detail_condition_playback_name_1'] = ''
            post_value['detail_condition_playback_from_1'] = ''
            post_value['detail_condition_playback_to_1'] = ''
            post_value['detail_condition_playback_no_1'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_total_no(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['total_playback_time_no'] = 'True'
            post_value['detail_condition_playback_name_1'] = ''
            post_value['detail_condition_playback_from_1'] = ''
            post_value['detail_condition_playback_to_1'] = ''
            post_value['detail_condition_playback_no_1'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_detail_condition(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ScoreStore.FIELD_STUDENT_STATUS__ENROLLED
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['detail_condition_playback_name_1'] = 'SECTION_1'
            post_value['detail_condition_playback_from_1'] = '0'
            post_value['detail_condition_playback_to_1'] = '0'
            post_value['detail_condition_playback_no_1'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_manager(self):
        status = 'Finished'

        self._setup()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.manager_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['detail_condition_playback_name_1'] = ''
            post_value['detail_condition_playback_from_1'] = ''
            post_value['detail_condition_playback_to_1'] = ''
            post_value['detail_condition_playback_no_1'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_intentional_exception(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = '0'
            post_value['total_playback_time_to'] = '0'
            post_value['detail_condition_playback_name_1'] = 'SECTION_1'
            post_value['detail_condition_playback_from_1'] = '0'
            post_value['detail_condition_playback_to_1'] = '0'
            post_value['detail_condition_playback_no_1'] = ''
            post_value['offset'] = '0.1'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(400, response.status_code)

    def test_search_ajax_not_list_detail_member(self):
        status = 'Finished'

        self._setup()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['detail_condition_playback_name_1'] = ''
            post_value['detail_condition_playback_from_1'] = ''
            post_value['detail_condition_playback_to_1'] = ''
            post_value['detail_condition_playback_no_1'] = ''
            post_value['detail_condition_member_name_1'] = ''
            post_value['detail_condition_member_name_2'] = 'org1'
            post_value['detail_condition_member_1'] = ''
            post_value['detail_condition_member_2'] = 'org1'
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_not_list_group_code(self):
        status = 'Finished'

        self._setup()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['detail_condition_playback_name_1'] = ''
            post_value['detail_condition_playback_from_1'] = ''
            post_value['detail_condition_playback_to_1'] = ''
            post_value['detail_condition_playback_no_1'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = '1234'
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_member_not_value(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['detail_condition_member_name_1'] = 'org1'
            post_value['detail_condition_member_1'] = 'abc'
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_member_group_none(self):
        status = 'Finished'

        self._setup_and_user_create_not_group()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = '1234'
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_member_group_mismatch(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = '1234'
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_member_manager(self):
        status = 'Finished'

        self._setup_and_user_create()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.manager_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['detail_condition_member_name_1'] = 'org1'
            post_value['detail_condition_member_1'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_search_ajax_member_success(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            post_value = dict()
            post_value['student_status'] = ''
            post_value['total_playback_time_from'] = ''
            post_value['total_playback_time_to'] = ''
            post_value['offset'] = '0'
            post_value['group_code'] = ''
            response = self.client.post(self._ajax_view(), post_value)

        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual('success', response_data['status'])

    def test_download_csv(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))

    def test_download_csv_batch_status_none(self):
        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name('no-timestamp')
        ))

    def test_download_csv_manager(self):
        status = 'Finished'

        self._setup()
        GroupUtil(org=self.org_a, user=self.user).import_data()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.manager_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))

    def test_download_csv_member(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))

    def test_download_csv_member_manager(self):
        status = 'Finished'

        self._setup_and_user_create()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.manager_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))

    def test_download_csv_field_types(self):
        status = 'Finished'

        self._setup(is_achievement_data_empty=True)
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        self.dict_column_data = {
            PlaybackStore.FIELD_CONTRACT_ID: self.contract.id,
            PlaybackStore.FIELD_COURSE_ID: unicode(self.course.id),
            PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN,
            PlaybackStore.FIELD_FULL_NAME: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_USERNAME: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_EMAIL: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_STUDENT_STATUS: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: PlaybackStore.COLUMN_TYPE__TIME,
            'SECTIONS_1': ScoreStore.COLUMN_TYPE__TEXT,
            'SECTIONS_2': ScoreStore.COLUMN_TYPE__TEXT,
            'SECTIONS_3': ScoreStore.COLUMN_TYPE__DATE,
            'SECTIONS_4': ScoreStore.COLUMN_TYPE__DATE,
            'SECTIONS_5': ScoreStore.COLUMN_TYPE__TIME,
            'SECTIONS_6': ScoreStore.COLUMN_TYPE__TIME,
            'SECTIONS_7': ScoreStore.COLUMN_TYPE__PERCENT,
            'SECTIONS_8': ScoreStore.COLUMN_TYPE__PERCENT,
            'SECTIONS_9': ScoreStore.COLUMN_TYPE__PERCENT,
            'SECTIONS_10': 'UnknownType',
        }
        PlaybackFactory.create(**self.dict_column_data)
        suffix = 1
        self.dict_record_data = {
            PlaybackStore.FIELD_CONTRACT_ID: self.contract.id,
            PlaybackStore.FIELD_COURSE_ID: unicode(self.course.id),
            PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD,
            PlaybackStore.FIELD_FULL_NAME: 'TEST TEST{}'.format(suffix),
            PlaybackStore.FIELD_USERNAME: 'TEST{}'.format(suffix),
            PlaybackStore.FIELD_EMAIL: 'test{}@example.com'.format(suffix),
            PlaybackStore.FIELD_STUDENT_STATUS: PlaybackStore.FIELD_STUDENT_STATUS__UNENROLLED,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: 999,
            'SECTIONS_1': 'SECTION_{}'.format(suffix),
            'SECTIONS_2': suffix,
            'SECTIONS_3': datetime(2016, 3, 10, 16, 58, 30, 0, tzinfo=pytz.utc),
            'SECTIONS_4': '',
            'SECTIONS_5': '1',
            'SECTIONS_6': '',
            'SECTIONS_7': PlaybackStore.VALUE__NOT_ATTEMPTED,
            'SECTIONS_8': 0.5,
            'SECTIONS_9': '',
            'SECTIONS_10': None,
        }
        self.expect_record_list.append(self.dict_record_data.copy())
        PlaybackFactory.create(**self.dict_record_data)

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename*=UTF-8\'\'{}'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))

    def test_download_searched_csv(self):
        status = 'Finished'

        self._setup()
        manager = self._create_manager(org=self.org_a, user=self.user, created=self.gacco_organization,
                                       permissions=[self.director_permission])
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_manager=manager, current_organization=self.org_a,
                                              current_contract=self.contract, current_course=self.course):

            param = self._create_param_search_ajax()
            param["search-download"] = "search-download"
            response = self.client.post(self._download_csv_view(), param)

        self.assertEqual(200, response.status_code)

"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from datetime import datetime
from ddt import data, ddt, unpack
import json
from mock import patch
import pytz

from django.core.urlresolvers import reverse
from django.http import HttpResponse

from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore, ScoreStore
from biz.djangoapps.ga_achievement.tests.factories import PlaybackFactory, ScoreFactory, PlaybackBatchStatusFactory, ScoreBatchStatusFactory
from biz.djangoapps.ga_contract.tests.factories import ContractFactory
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.mongo_utils import DEFAULT_DATETIME
from biz.djangoapps.util.tests.testcase import BizStoreTestBase, BizViewTestBase
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from util.file import course_filename_prefix_generator
from util.json_request import JsonResponse, JsonResponseBadRequest


@ddt
class ScoreViewTest(BizStoreTestBase, BizViewTestBase, ModuleStoreTestCase):

    def _index_view(self):
        return reverse('biz:achievement:score')

    def _ajax_view(self):
        return reverse('biz:achievement:score_ajax')

    def _download_csv_view(self):
        return reverse('biz:achievement:score_download_csv')

    def _setup(self, is_achievement_data_empty=False, is_default_date=False, record_count=1):
        self.expect_record_list = []
        self._set_date()
        self.setup_user()
        self._create_course_data()
        self._create_org_data()
        self._create_contract_data()
        if not is_achievement_data_empty:
            for i in range(record_count):
                self._create_achievement_data(is_default_date=is_default_date, suffix=str(i))

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

    def _create_achievement_data(self, is_default_date=False, suffix=''):
        self.dict_data = {
            ScoreStore.FIELD_CONTRACT_ID: self.contract.id,
            ScoreStore.FIELD_COURSE_ID: unicode(self.course.id),
            ScoreStore.FIELD_FULL_NAME: 'TEST TEST{}'.format(suffix),
            ScoreStore.FIELD_USERNAME: 'TEST{}'.format(suffix),
            ScoreStore.FIELD_EMAIL: 'test{}@example.com'.format(suffix),
            ScoreStore.FIELD_STUDENT_STATUS: ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED,
            ScoreStore.FIELD_CERTIFICATE_STATUS: ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE,
            ScoreStore.FIELD_TOTAL_SCORE: 0.9
        }
        if is_default_date:
            self.dict_data.update({ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: DEFAULT_DATETIME})
        else:
            self.dict_data.update({ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: self.utc_datetime})

        self.expect_record_list.append(self.dict_data.copy())

        ScoreFactory.create(**self.dict_data)

    def _create_batch_status(self, status):
        self.batch_status = ScoreBatchStatusFactory.create(contract=self.contract,
                                                           course_id=unicode(self.course.id),
                                                           status=status,
                                                           student_count=4)

    def _get_csv_file_name(self, str_datetime):
        return u'{course_prefix}_{csv_name}_{timestamp_str}.csv'.format(
            course_prefix=course_filename_prefix_generator(self.course.id),
            csv_name='score_status',
            timestamp_str=str_datetime
        )

    def _assert_column_data(self, columns):
        self.assertDictEqual(dict(json.loads(columns)), {
            ScoreStore.FIELD_FULL_NAME: 'text',
            ScoreStore.FIELD_USERNAME: 'text',
            ScoreStore.FIELD_EMAIL: 'text',
            ScoreStore.FIELD_STUDENT_STATUS: 'text',
            ScoreStore.FIELD_CERTIFICATE_STATUS: 'text',
            ScoreStore.FIELD_TOTAL_SCORE: 'percent',
            ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: 'date',
        })

    def _assert_record_data(self, records, is_default_date=False, is_ajax=False):
        expected = {
            unicode(ScoreStore.FIELD_FULL_NAME): unicode(self.dict_data[ScoreStore.FIELD_FULL_NAME]),
            unicode(ScoreStore.FIELD_USERNAME): unicode(self.dict_data[ScoreStore.FIELD_USERNAME]),
            unicode(ScoreStore.FIELD_EMAIL): unicode(self.dict_data[ScoreStore.FIELD_EMAIL]),
            unicode(ScoreStore.FIELD_STUDENT_STATUS): unicode(self.dict_data[ScoreStore.FIELD_STUDENT_STATUS]),
            unicode(ScoreStore.FIELD_CERTIFICATE_STATUS): unicode(self.dict_data[ScoreStore.FIELD_CERTIFICATE_STATUS]),
            unicode(ScoreStore.FIELD_TOTAL_SCORE): self.dict_data[ScoreStore.FIELD_TOTAL_SCORE],
            u'recid': 1,
        }
        if is_default_date:
            expected.update({ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: None})
        else:
            expected.update({
                ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: unicode(datetime_utils.format_for_w2ui(self.dict_data[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE]))
            })
        if is_ajax:
            self.assertDictEqual(records[0], expected)
        else:
            self.assertDictEqual(json.loads(records)[0], expected)

    def _assert_record_data_for_ajax(self, records, recid, expect_record):
        expected = {
            unicode(ScoreStore.FIELD_FULL_NAME): unicode(expect_record[ScoreStore.FIELD_FULL_NAME]),
            unicode(ScoreStore.FIELD_USERNAME): unicode(expect_record[ScoreStore.FIELD_USERNAME]),
            unicode(ScoreStore.FIELD_EMAIL): unicode(expect_record[ScoreStore.FIELD_EMAIL]),
            unicode(ScoreStore.FIELD_STUDENT_STATUS): unicode(expect_record[ScoreStore.FIELD_STUDENT_STATUS]),
            unicode(ScoreStore.FIELD_CERTIFICATE_STATUS): unicode(expect_record[ScoreStore.FIELD_CERTIFICATE_STATUS]),
            unicode(ScoreStore.FIELD_TOTAL_SCORE): expect_record[ScoreStore.FIELD_TOTAL_SCORE],
            unicode(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE): unicode(datetime_utils.format_for_w2ui(expect_record[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE])),
            u'recid': recid,
        }
        self.assertDictEqual(records, expected)

    def _assert_record_count(self, records_count, expect_records_count):
        self.assertEqual(records_count, expect_records_count)

    def _assert_column_data_for_csv(self, columns):
        self.assertSetEqual(set(columns.split(',')), {
            ScoreStore.FIELD_FULL_NAME,
            ScoreStore.FIELD_USERNAME,
            ScoreStore.FIELD_EMAIL,
            ScoreStore.FIELD_STUDENT_STATUS,
            ScoreStore.FIELD_CERTIFICATE_STATUS,
            ScoreStore.FIELD_TOTAL_SCORE,
            ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE,
        })

    def _assert_record_data_for_csv(self, records, is_default_date=False):
        expected = [
            self.dict_data[ScoreStore.FIELD_FULL_NAME],
            self.dict_data[ScoreStore.FIELD_USERNAME],
            self.dict_data[ScoreStore.FIELD_EMAIL],
            self.dict_data[ScoreStore.FIELD_STUDENT_STATUS],
            self.dict_data[ScoreStore.FIELD_CERTIFICATE_STATUS],
            '{:.01%}'.format(self.dict_data[ScoreStore.FIELD_TOTAL_SCORE]),
        ]
        if is_default_date:
            expected.append('')
        else:
            expected.append(datetime_utils.to_jst(self.dict_data[ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE]).strftime('%Y/%m/%d'))
        self.assertSetEqual(set(records.split(',')), set(expected))

    def test_index(self):
        status = 'Finished'

        self._setup()
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response', return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/score.html')
        self.assertEqual(render_to_response_args[1]['update_datetime'], datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['score_columns'])
        self._assert_record_data(render_to_response_args[1]['score_records'])
        self._assert_record_count(render_to_response_args[1]['total_records'], 1)

    def test_index_if_batch_status_does_not_exist(self):
        self._setup()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response', return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/score.html')
        self.assertEqual(render_to_response_args[1]['update_datetime'], '')
        self.assertEqual(render_to_response_args[1]['update_status'], '')
        self._assert_column_data(render_to_response_args[1]['score_columns'])
        self._assert_record_data(render_to_response_args[1]['score_records'])
        self._assert_record_count(render_to_response_args[1]['total_records'], 1)

    def test_index_if_achievement_data_is_empty(self):
        status = 'Finished'

        self._setup(is_achievement_data_empty=True)
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response', return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/score.html')
        self.assertEqual(render_to_response_args[1]['update_datetime'], datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self.assertEqual(render_to_response_args[1]['score_columns'], '[]')
        self.assertEqual(render_to_response_args[1]['score_records'], '[]')
        self._assert_record_count(render_to_response_args[1]['total_records'], 0)

    def test_index_if_achievement_data_includes_default_datetime(self):
        status = 'Finished'

        self._setup(is_default_date=True)
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response', return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/score.html')
        self.assertEqual(render_to_response_args[1]['update_datetime'], datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['score_columns'])
        self._assert_record_data(render_to_response_args[1]['score_records'], is_default_date=True)
        self._assert_record_count(render_to_response_args[1]['total_records'], 1)

    @data(
        (0, 0),
        (0, 1),
        (2, 5),
        (5, 5),
    )
    @unpack
    def test_ajax(self, offset, total_records):
        status = 'Finished'

        self._setup(record_count=total_records)
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.JsonResponse', return_value=JsonResponse()) as mock_json_response:
                self.client.post(self._ajax_view(), data={'offset': offset})

        json_response_args = mock_json_response.call_args[0]
        score_records = json_response_args[0]['score_records']
        for i, expect_index in enumerate(range(offset, total_records)):
            self._assert_record_data_for_ajax(score_records[i], recid=i+1, expect_record=self.expect_record_list[expect_index])
        self._assert_record_count(len(json_response_args[0]['score_records']), total_records - offset)
        self._assert_record_count(json_response_args[0]['total_records'], total_records)

    def test_download_csv(self):
        status = 'Finished'

        self._setup()
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename="{}"'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))
        columns = response.content.split('\r\n')[0]
        records = response.content.split('\r\n')[1]
        self._assert_column_data_for_csv(columns)
        self._assert_record_data_for_csv(records)

    def test_download_csv_if_batch_status_does_not_exist(self):
        self._setup()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename="{}"'.format(
            self._get_csv_file_name('no-timestamp')
        ))
        columns = response.content.split('\r\n')[0]
        records = response.content.split('\r\n')[1]
        self._assert_column_data_for_csv(columns)
        self._assert_record_data_for_csv(records)

    def test_download_csv_if_achievement_data_is_empty(self):
        status = 'Finished'

        self._setup(is_achievement_data_empty=True)
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename="{}"'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))
        self.assertEqual(response.content, '')

    def test_download_csv_if_achievement_data_includes_default_datetime(self):
        status = 'Finished'

        self._setup(is_default_date=True)
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename="{}"'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))
        columns = response.content.split('\r\n')[0]
        records = response.content.split('\r\n')[1]
        self._assert_column_data_for_csv(columns)
        self._assert_record_data_for_csv(records, is_default_date=True)

    def test_download_csv_not_allowed_method(self):
        self._setup()
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.get(self._download_csv_view())
        self.assertEqual(405, response.status_code)


@ddt
class PlaybackViewTest(BizStoreTestBase, BizViewTestBase, ModuleStoreTestCase):

    def _index_view(self):
        return reverse('biz:achievement:playback')

    def _ajax_view(self):
        return reverse('biz:achievement:playback_ajax')

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
        }

        self.expect_record_list.append(self.dict_record_data.copy())

        PlaybackFactory.create(**self.dict_record_data)

    def _create_batch_status(self, status):
        self.batch_status = PlaybackBatchStatusFactory.create(contract=self.contract,
                                                              course_id=unicode(self.course.id),
                                                              status=status,
                                                              student_count=4)

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
        })

    def _assert_record_data(self, records, is_ajax=False):
        expect = {
            unicode(PlaybackStore.FIELD_FULL_NAME): unicode(self.dict_record_data[PlaybackStore.FIELD_FULL_NAME]),
            unicode(PlaybackStore.FIELD_USERNAME): unicode(self.dict_record_data[PlaybackStore.FIELD_USERNAME]),
            unicode(PlaybackStore.FIELD_EMAIL): unicode(self.dict_record_data[PlaybackStore.FIELD_EMAIL]),
            unicode(PlaybackStore.FIELD_STUDENT_STATUS): unicode(self.dict_record_data[PlaybackStore.FIELD_STUDENT_STATUS]),
            unicode(PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME): self.dict_record_data[PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME],
            u'recid': 1,
        }

        if is_ajax:
            self.assertDictEqual(records[0], expect)
        else:
            self.assertDictEqual(json.loads(records)[0], expect)

    def _assert_record_data_for_ajax(self, records, recid, expect_record):
        expected = {
            unicode(PlaybackStore.FIELD_FULL_NAME): unicode(expect_record[PlaybackStore.FIELD_FULL_NAME]),
            unicode(PlaybackStore.FIELD_USERNAME): unicode(expect_record[PlaybackStore.FIELD_USERNAME]),
            unicode(PlaybackStore.FIELD_EMAIL): unicode(expect_record[PlaybackStore.FIELD_EMAIL]),
            unicode(PlaybackStore.FIELD_STUDENT_STATUS): unicode(expect_record[PlaybackStore.FIELD_STUDENT_STATUS]),
            unicode(PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME): expect_record[PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME],
            u'recid': recid,
        }
        self.assertDictEqual(records, expected)

    def _assert_record_count(self, records_count, expect_records_count):
        self.assertEqual(records_count, expect_records_count)

    def _assert_column_data_for_csv(self, columns):
        self.assertSetEqual(set(columns.split(',')), {
            PlaybackStore.FIELD_FULL_NAME,
            PlaybackStore.FIELD_USERNAME,
            PlaybackStore.FIELD_EMAIL,
            PlaybackStore.FIELD_STUDENT_STATUS,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME,
        })

    def _assert_record_data_for_csv(self, records):
        self.assertSetEqual(set(records.split(',')), {
            self.dict_record_data[PlaybackStore.FIELD_FULL_NAME],
            self.dict_record_data[PlaybackStore.FIELD_USERNAME],
            self.dict_record_data[PlaybackStore.FIELD_EMAIL],
            self.dict_record_data[PlaybackStore.FIELD_STUDENT_STATUS],
            datetime_utils.seconds_to_time_format(self.dict_record_data[PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME]),
        })

    def test_index(self):
        status = 'Finished'

        self._setup()
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response', return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/playback.html')
        self.assertEqual(render_to_response_args[1]['update_datetime'], datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self._assert_column_data(render_to_response_args[1]['playback_columns'])
        self._assert_record_data(render_to_response_args[1]['playback_records'])
        self._assert_record_count(render_to_response_args[1]['total_records'], 1)

    def test_index_if_batch_status_does_not_exist(self):
        self._setup()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response', return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/playback.html')
        self.assertEqual(render_to_response_args[1]['update_datetime'], '')
        self.assertEqual(render_to_response_args[1]['update_status'], '')
        self._assert_column_data(render_to_response_args[1]['playback_columns'])
        self._assert_record_data(render_to_response_args[1]['playback_records'])
        self._assert_record_count(render_to_response_args[1]['total_records'], 1)

    def test_index_if_achievement_data_is_empty(self):
        status = 'Finished'

        self._setup(is_achievement_data_empty=True)
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.render_to_response', return_value=HttpResponse()) as mock_render_to_response:
                self.client.get(self._index_view())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_achievement/playback.html')
        self.assertEqual(render_to_response_args[1]['update_datetime'], datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertEqual(render_to_response_args[1]['update_status'], status)
        self.assertEqual(render_to_response_args[1]['playback_columns'], '[]')
        self.assertEqual(render_to_response_args[1]['playback_records'], '[]')
        self._assert_record_count(render_to_response_args[1]['total_records'], 0)

    @data(
        (0, 0),
        (0, 1),
        (2, 5),
        (5, 5),
    )
    @unpack
    def test_ajax(self, offset, total_records):
        status = 'Finished'

        self._setup(record_count=total_records)
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            with patch('biz.djangoapps.ga_achievement.views.JsonResponse', return_value=JsonResponse()) as mock_json_response:
                self.client.post(self._ajax_view(), data={'offset': offset})

        json_response_args = mock_json_response.call_args[0]
        playback_records = json_response_args[0]['playback_records']
        for i, expect_index in enumerate(range(offset, total_records)):
            self._assert_record_data_for_ajax(playback_records[i], recid=i+1, expect_record=self.expect_record_list[expect_index])
        self._assert_record_count(len(json_response_args[0]['playback_records']), total_records - offset)
        self._assert_record_count(json_response_args[0]['total_records'], total_records)

    def test_download_csv(self):
        status = 'Finished'

        self._setup()
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename="{}"'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))
        columns = response.content.split('\r\n')[0]
        records = response.content.split('\r\n')[1]
        self._assert_column_data_for_csv(columns)
        self._assert_record_data_for_csv(records)

    def test_download_csv_if_batch_status_does_not_exist(self):
        self._setup()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename="{}"'.format(
            self._get_csv_file_name('no-timestamp')
        ))
        columns = response.content.split('\r\n')[0]
        records = response.content.split('\r\n')[1]
        self._assert_column_data_for_csv(columns)
        self._assert_record_data_for_csv(records)

    def test_download_csv_if_achievement_data_is_empty(self):
        status = 'Finished'

        self._setup(is_achievement_data_empty=True)
        self._create_batch_status(status)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._download_csv_view())

        self.assertEqual(200, response.status_code)
        self.assertEqual(response['content-disposition'], 'attachment; filename="{}"'.format(
            self._get_csv_file_name(datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y-%m-%d-%H%M'))
        ))
        self.assertEqual(response.content, '')

    def test_download_csv_not_allowed_method(self):
        self._setup()
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.get(self._download_csv_view())
        self.assertEqual(405, response.status_code)

"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from datetime import datetime
import pytz

from django.core.urlresolvers import reverse

from biz.djangoapps.ga_achievement.achievement_store import ScoreStore
from biz.djangoapps.ga_achievement.tests.factories import ScoreFactory, ScoreBatchStatusFactory
from biz.djangoapps.ga_contract.tests.factories import ContractFactory
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.mongo_utils import DEFAULT_DATETIME
from biz.djangoapps.util.tests.testcase import BizStoreTestBase, BizViewTestBase
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from util.file import course_filename_prefix_generator


class AchievementViewTest(BizStoreTestBase, BizViewTestBase, ModuleStoreTestCase):

    def _score_view(self):
        return reverse('biz:achievement:score')

    def _score_download_csv_view(self):
        return reverse('biz:achievement:score_download_csv')

    def _create_contract(self, name, contractor, owner, created_by, invitation_code):
        return ContractFactory.create(contract_name=name, contractor_organization=contractor, owner_organization=owner,
                                      created_by=created_by, invitation_code=invitation_code)

    def _create_course_data(self):
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')

    def _create_contract_data(self):
        self.contract = self._create_contract('contract_a', self.org_a, self.gacco_organization,
                                              self.user, 'invitation_code_a')

    def _create_org_data(self):
        self.org_a = self._create_organization(org_name='a', org_code='a', creator_org=self.gacco_organization)

    def _create_score_data(self, is_default_date=False):
        dict_data = {
            ScoreStore.FIELD_CONTRACT_ID: self.contract.id,
            ScoreStore.FIELD_COURSE_ID: unicode(self.course.id),
            ScoreStore.FIELD_FULL_NAME: 'TEST TEST',
            ScoreStore.FIELD_USERNAME: 'TEST',
            ScoreStore.FIELD_EMAIL: 'test@example.com',
            ScoreStore.FIELD_STUDENT_STATUS: ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED,
            ScoreStore.FIELD_CERTIFICATE_STATUS: ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE,
            ScoreStore.FIELD_TOTAL_SCORE: 0.9
        }
        if is_default_date:
            dict_data.update({ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: DEFAULT_DATETIME})
        else:
            dict_data.update({ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: self.utc_datetime})
        self.score_factory = ScoreFactory.create(**dict_data)

    def _create_score_batch_status(self, status):
        self.score_batch_status = ScoreBatchStatusFactory.create(contract=self.contract,
                                                                 course_id=unicode(self.course.id),
                                                                 status=status,
                                                                 student_count=4)

    def _set_csv_file_name(self, str_datetime):
        self.csv_filename = u'{course_prefix}_{csv_name}_{timestamp_str}.csv'.format(
            course_prefix=course_filename_prefix_generator(self.course.id),
            csv_name='score_status',
            timestamp_str=str_datetime
        )

    def _set_date(self):
        self.utc_datetime = datetime(2016, 3, 1, 16, 58, 30, 0, tzinfo=pytz.utc)
        self.str_utc_datetime = datetime(2016, 3, 1, 16, 58, 30, 0, tzinfo=pytz.utc).strftime('%Y-%m-%d %H:%M:%S')
        self.str_jst_date = self.str_jst_date_csv = datetime_utils.to_jst(self.utc_datetime).strftime('%Y/%m/%d')

        self.utc_datetime_score_update = datetime(2016, 3, 10, 16, 58, 30, 0, tzinfo=pytz.utc)
        self.str_jst_datetime_score_update = \
            datetime_utils.to_jst(self.utc_datetime_score_update).strftime('%Y/%m/%d %H:%M')

    def _setup(self, is_default_date=False):
        self._set_date()
        self.setup_user()
        self._create_course_data()
        self._create_org_data()
        self._create_contract_data()
        self._create_score_data(is_default_date)

    def test_index_no_score_batch_status(self):
        self._setup()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.get(self._score_view())

        self.assertEqual(200, response.status_code)
        self.assertIn(ScoreStore.FIELD_FULL_NAME, response.content)
        self.assertIn(ScoreStore.FIELD_USERNAME, response.content)
        self.assertIn(ScoreStore.FIELD_EMAIL, response.content)
        self.assertIn(ScoreStore.FIELD_STUDENT_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, response.content)
        self.assertIn(ScoreStore.FIELD_TOTAL_SCORE, response.content)

    def test_index_is_score_batch_status(self):
        status = 'Finished'

        self._setup()
        self._create_score_batch_status(status)
        self.score_batch_status.created = self.utc_datetime_score_update
        self.score_batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.get(self._score_view())

        self.assertEqual(200, response.status_code)
        self.assertIn(ScoreStore.FIELD_FULL_NAME, response.content)
        self.assertIn(ScoreStore.FIELD_USERNAME, response.content)
        self.assertIn(ScoreStore.FIELD_EMAIL, response.content)
        self.assertIn(ScoreStore.FIELD_STUDENT_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, response.content)
        self.assertIn(ScoreStore.FIELD_TOTAL_SCORE, response.content)
        self.assertIn('Record Update Datetime', response.content)
        self.assertIn(self.str_jst_datetime_score_update, response.content)
        self.assertIn(self.str_jst_date, response.content)
        self.assertIn(status, response.content)

    def test_index_default_datetime_batch_status(self):
        status = 'Finished'

        self._setup(True)
        self._create_score_batch_status(status)
        self.score_batch_status.created = self.utc_datetime_score_update
        self.score_batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.get(self._score_view())

        self.assertEqual(200, response.status_code)
        self.assertIn(ScoreStore.FIELD_FULL_NAME, response.content)
        self.assertIn(ScoreStore.FIELD_USERNAME, response.content)
        self.assertIn(ScoreStore.FIELD_EMAIL, response.content)
        self.assertIn(ScoreStore.FIELD_STUDENT_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, response.content)
        self.assertIn(ScoreStore.FIELD_TOTAL_SCORE, response.content)
        self.assertIn('Record Update Datetime', response.content)
        self.assertIn(self.str_jst_datetime_score_update, response.content)
        self.assertNotIn(self.str_jst_date, response.content)
        self.assertNotIn(datetime_utils.to_jst(DEFAULT_DATETIME).strftime('%Y/%m/%d %H:%M'), response.content)
        self.assertIn(status, response.content)

    def test_download_csv_no_score_batch_status(self):
        self._setup()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._score_download_csv_view())

        self._set_csv_file_name('no-timestamp')

        self.assertEqual(200, response.status_code)
        self.assertIn(ScoreStore.FIELD_FULL_NAME, response.content)
        self.assertIn(ScoreStore.FIELD_USERNAME, response.content)
        self.assertIn(ScoreStore.FIELD_EMAIL, response.content)
        self.assertIn(ScoreStore.FIELD_STUDENT_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, response.content)
        self.assertIn(ScoreStore.FIELD_TOTAL_SCORE, response.content)
        self.assertIn(self.str_jst_date_csv, response.content)

    def test_download_csv_is_score_batch_status(self):
        status = 'Finished'

        self._setup()
        self._create_score_batch_status(status)
        self.score_batch_status.created = self.utc_datetime_score_update
        self.score_batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._score_download_csv_view())

        self._set_csv_file_name(self.str_jst_datetime_score_update)

        self.assertEqual(200, response.status_code)
        self.assertIn(ScoreStore.FIELD_FULL_NAME, response.content)
        self.assertIn(ScoreStore.FIELD_USERNAME, response.content)
        self.assertIn(ScoreStore.FIELD_EMAIL, response.content)
        self.assertIn(ScoreStore.FIELD_STUDENT_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, response.content)
        self.assertIn(ScoreStore.FIELD_TOTAL_SCORE, response.content)
        self.assertIn(self.str_jst_date_csv, response.content)

    def test_download_csv_default_datetime_is_score_batch_status(self):
        status = 'Finished'

        self._setup(True)
        self._create_score_batch_status(status)
        self.score_batch_status.created = self.utc_datetime_score_update
        self.score_batch_status.save()

        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.post(self._score_download_csv_view())

        self._set_csv_file_name(self.str_jst_datetime_score_update)

        self.assertEqual(200, response.status_code)
        self.assertIn(ScoreStore.FIELD_FULL_NAME, response.content)
        self.assertIn(ScoreStore.FIELD_USERNAME, response.content)
        self.assertIn(ScoreStore.FIELD_EMAIL, response.content)
        self.assertIn(ScoreStore.FIELD_STUDENT_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_STATUS, response.content)
        self.assertIn(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE, response.content)
        self.assertIn(ScoreStore.FIELD_TOTAL_SCORE, response.content)
        self.assertNotIn(self.str_jst_datetime_score_update, response.content)
        self.assertNotIn(datetime_utils.to_jst(DEFAULT_DATETIME).strftime('%Y/%m/%d %H:%M'), response.content)

    def test_download_csv__not_allowed_method(self):
        self._setup(True)
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.get(self._score_download_csv_view())
        self.assertEqual(405, response.status_code)

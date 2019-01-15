import codecs
import ddt

from django.core.urlresolvers import reverse

from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_org_group.tests.factories import GroupUtil, RightFactory

from ga_survey.tests.factories import SurveySubmissionFactory
from student.models import CourseEnrollment, UserStanding
from student.tests.factories import UserFactory, CourseModeFactory, AdminFactory, UserProfileFactory, UserStandingFactory
from openedx.core.lib.ga_datetime_utils import format_for_csv


class CourseOperationViewsTest(BizContractTestBase):

    def setUp(self):
        super(CourseOperationViewsTest, self).setUp()
        self.setup_user()

        self._director = self._create_manager(
            org=self.gacco_organization,
            user=self.user,
            created=self.gacco_organization,
            permissions=[self.director_permission]
        )

    def test_survey(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_organization=self.gacco_organization,
                                              current_course=self.course_spoc1, current_manager=self._director):
            self.assert_request_status_code(200, reverse('biz:course_operation:survey'))


class CourseOperationSurveyDownloadTestMixin(BizContractTestBase):
    @property
    def _director_manager(self):
        return self._create_manager(
            org=self.contract_org, user=self.user, created=self.contract_org, permissions=[self.director_permission])

    @property
    def _manager_manager(self):
        return self._create_manager(
            org=self.contract_org, user=self.user, created=self.contract_org, permissions=[self.manager_permission])

    def validate_bom_utf16(self, content):
        # UTF16LE with BOM
        return content.startswith(codecs.BOM_UTF16_LE)

    def validate_bom_utf8(self, content):
        # UTF8 no BOM
        return not content.startswith(codecs.BOM_UTF8)

    def get_survey_csv_rows_unicode_from_utf16(self, content):
        content_none_bom = content[len(codecs.BOM_UTF16_LE):]
        content_decoded = content_none_bom.decode('utf-16-le')
        return self._get_servey_csv_rows(content_decoded)

    def get_survey_csv_rows_unicode_from_utf8(self, content):
        return self._get_servey_csv_rows(content)

    def _get_servey_csv_rows(self, content):
        body = content.rstrip('\n').replace('\r', '')
        return body.split('\n')

    def get_url(self):
        raise NotImplementedError()

    def validate_bom(self, content):
        raise NotImplementedError()

    def get_survey_csv_rows_unicode(self, content):
        raise NotImplementedError()

    def _create_submission_user(self, account_status=UserStanding.ACCOUNT_ENABLED):
        _user = UserFactory.create()
        UserStandingFactory.create(
            user=_user,
            account_status=account_status,
            changed_by=_user,
        )
        return _user

    def _create_member(self, org, group, user, code):
        return MemberFactory.create(
            org=org,
            group=group,
            user=user,
            code=code,
            created_by=self.user,
            creator_org=org,
            updated_by=self.user,
            updated_org=org,
            is_active=True,
            is_delete=False
        )


@ddt.ddt
class CourseOperationSurveyDownloadTest(CourseOperationSurveyDownloadTestMixin):

    def get_url(self):
        return reverse('biz:course_operation:survey_download')

    def validate_bom(self, content):
        return self.validate_bom_utf16(content)

    def get_survey_csv_rows_unicode(self, content):
        return self.get_survey_csv_rows_unicode_from_utf16(content)

    def test_survey_download_director(self):
        self.setup_user()
        _manager = self._director_manager

        # has contract register
        user1 = self._create_submission_user()
        self.create_contract_register(user1, self.contract)
        submission1 = SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': user1,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission #1"}',
        })
        # has not contract register
        user2 = self._create_submission_user()
        CourseEnrollment.enroll(user2, self.course_spoc1.id)
        self.submission2 = SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': user2,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": "2", "Q3": "submission #2"}',
        })

        with self.skip_check_course_selection(current_contract=self.contract, current_organization=self.contract_org,
                                              current_course=self.course_spoc1, current_manager=_manager):
            response = self.client.post(self.get_url(), {})

        self.assertEqual(200, response.status_code)
        content = response.content
        self.assertTrue(self.validate_bom(content))
        rows = self.get_survey_csv_rows_unicode(content)
        self.assertEqual(2, len(rows))
        self.assertEqual(rows[0], u'"Unit ID"\t"Survey Name"\t"Created"\t"User Name"\t"Full Name"\t"Email"\t"Resigned"\t"Unenrolled"\t"Q1"\t"Q2"\t"Q3"')
        self.assertEqual(
            rows[1],
            u'"11111111111111111111111111111111"\t"survey #1"\t"%s"\t"%s"\t"%s"\t"%s"\t""\t""\t"1"\t"1,2"\t"submission #1"'
            % (format_for_csv(submission1.created), submission1.user.username, submission1.user.profile.name, submission1.user.email)
        )

    @ddt.data(None, 'G01', 'G02', 'G02-01-02')
    def test_survey_download_manager_when_group_exist(self, test_right_group_code):
        self.setup_user()
        _manager = self._manager_manager
        group_util = GroupUtil(org=self.contract_org, user=self.user)
        group_util.import_data()

        if test_right_group_code is not None:
            RightFactory.create(
                org=self.contract_org, group=Group.objects.get(group_code=test_right_group_code),
                user=_manager.user, created_by=self.user, creator_org=self.contract_org)

        # search target user
        submission_user1 = self._create_submission_user()
        self.create_contract_register(submission_user1, self.contract)
        submission1 = SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': submission_user1,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission #1"}',
        })
        self._create_member(
            org=self.contract_org,
            group=Group.objects.get(group_code='G01-01'),
            user=submission_user1,
            code='submission_user1'
        )

        # another group user
        submission_user2 = self._create_submission_user()
        self.create_contract_register(submission_user2, self.contract)
        submission2 = SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': submission_user2,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission #2"}',
        })
        self._create_member(
            org=self.contract_org,
            group=Group.objects.get(group_code='G02-01'),
            user=submission_user2,
            code='submission_user2'
        )

        # has no group user
        submission_user3 = self._create_submission_user()
        self.create_contract_register(submission_user3, self.contract)
        SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': submission_user3,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission #3"}',
        })

        with self.skip_check_course_selection(current_contract=self.contract, current_organization=self.contract_org,
                                              current_course=self.course_spoc1, current_manager=_manager):
            response = self.client.post(self.get_url(), {})

        self.assertEqual(200, response.status_code)
        content = response.content
        self.assertTrue(self.validate_bom(content))
        rows = self.get_survey_csv_rows_unicode(content)
        if test_right_group_code is None or test_right_group_code is 'G02-01-02':
            self.assertEqual(1, len(rows))
            self.assertEqual(rows[0], u'"Unit ID"\t"Survey Name"\t"Created"\t"User Name"\t"Full Name"\t"Email"\t"Resigned"\t"Unenrolled"')

        elif test_right_group_code is 'G01':
            self.assertEqual(2, len(rows))
            self.assertEqual(rows[0], u'"Unit ID"\t"Survey Name"\t"Created"\t"User Name"\t"Full Name"\t"Email"\t"Resigned"\t"Unenrolled"\t"Q1"\t"Q2"\t"Q3"')
            self.assertEqual(
                rows[1],
                u'"11111111111111111111111111111111"\t"survey #1"\t"%s"\t"%s"\t"%s"\t"%s"\t""\t""\t"1"\t"1,2"\t"submission #1"'
                % (format_for_csv(submission1.created), submission1.user.username, submission1.user.profile.name, submission1.user.email)
            )

        elif test_right_group_code is 'G02':
            self.assertEqual(2, len(rows))
            self.assertEqual(rows[0], u'"Unit ID"\t"Survey Name"\t"Created"\t"User Name"\t"Full Name"\t"Email"\t"Resigned"\t"Unenrolled"\t"Q1"\t"Q2"\t"Q3"')
            self.assertEqual(
                rows[1],
                u'"11111111111111111111111111111111"\t"survey #1"\t"%s"\t"%s"\t"%s"\t"%s"\t""\t""\t"1"\t"1,2"\t"submission #2"'
                % (format_for_csv(submission2.created), submission2.user.username, submission2.user.profile.name, submission2.user.email)
            )

    def test_survey_download_when_group_not_exist(self):
        self.setup_user()
        _manager = self._director_manager

        # search target user
        submission_user1 = self._create_submission_user()
        self.create_contract_register(submission_user1, self.contract)
        submission1 = SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': submission_user1,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission #1"}',
        })
        self._create_member(org=self.contract_org, group=None, user=submission_user1, code='submission_user1')

        # another group user
        submission_user2 = self._create_submission_user()
        self.create_contract_register(submission_user2, self.contract)
        submission2 = SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': submission_user2,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission #2"}',
        })
        self._create_member(org=self.contract_org, group=None, user=submission_user2, code='submission_user2')

        # has no group user
        submission_user3 = self._create_submission_user()
        self.create_contract_register(submission_user3, self.contract)
        submission3 = SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': submission_user3,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission #3"}',
        })
        with self.skip_check_course_selection(current_contract=self.contract, current_organization=self.contract_org,
                                              current_course=self.course_spoc1, current_manager=_manager):
            response = self.client.post(self.get_url(), {})

        self.assertEqual(200, response.status_code)
        content = response.content
        self.assertTrue(self.validate_bom(content))
        rows = self.get_survey_csv_rows_unicode(content)
        self.assertEqual(4, len(rows))
        self.assertEqual(rows[0], u'"Unit ID"\t"Survey Name"\t"Created"\t"User Name"\t"Full Name"\t"Email"\t"Resigned"\t"Unenrolled"\t"Q1"\t"Q2"\t"Q3"')
        self.assertEqual(
            rows[1],
            u'"11111111111111111111111111111111"\t"survey #1"\t"%s"\t"%s"\t"%s"\t"%s"\t""\t""\t"1"\t"1,2"\t"submission #1"'
            % (format_for_csv(submission1.created), submission1.user.username, submission1.user.profile.name, submission1.user.email)
        )
        self.assertEqual(
            rows[2],
            u'"11111111111111111111111111111111"\t"survey #1"\t"%s"\t"%s"\t"%s"\t"%s"\t""\t""\t"1"\t"1,2"\t"submission #2"'
            % (format_for_csv(submission2.created), submission2.user.username, submission2.user.profile.name, submission2.user.email)
        )
        self.assertEqual(
            rows[3],
            u'"11111111111111111111111111111111"\t"survey #1"\t"%s"\t"%s"\t"%s"\t"%s"\t""\t""\t"1"\t"1,2"\t"submission #3"'
            % (format_for_csv(submission3.created), submission3.user.username, submission3.user.profile.name, submission3.user.email)
        )

    def test_survey_download_when_one_course_is_tied_to_multiple_organizations(self):
        self.setup_user()
        _manager = self._director_manager

        # search target user
        submission_user1 = self._create_submission_user()
        self.create_contract_register(submission_user1, self.contract)
        submission1 = SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': submission_user1,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission #1"}',
        })

        # create another org and contract
        another_org = self._create_organization(org_name='another_org_name', org_code='another_org_code')
        another_contract = self._create_contract(
            contractor_organization=another_org,
            detail_courses=[self.course_spoc1.id, self.course_spoc2.id],
            additional_display_names=['country', 'dept'])
        # create another contract's register
        submission_user4 = self._create_submission_user()
        self.create_contract_register(submission_user4, another_contract)
        # create same course submission
        SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': submission_user4,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission #2"}',
        })

        with self.skip_check_course_selection(current_contract=self.contract, current_organization=self.contract_org,
                                              current_course=self.course_spoc1, current_manager=_manager):
            response = self.client.post(self.get_url(), {})

        self.assertEqual(200, response.status_code)
        content = response.content
        self.assertTrue(self.validate_bom(content))
        rows = self.get_survey_csv_rows_unicode(content)
        self.assertEqual(2, len(rows))
        self.assertEqual(rows[0], u'"Unit ID"\t"Survey Name"\t"Created"\t"User Name"\t"Full Name"\t"Email"\t"Resigned"\t"Unenrolled"\t"Q1"\t"Q2"\t"Q3"')
        self.assertEqual(
            rows[1],
            u'"11111111111111111111111111111111"\t"survey #1"\t"%s"\t"%s"\t"%s"\t"%s"\t""\t""\t"1"\t"1,2"\t"submission #1"'
            % (format_for_csv(submission1.created), submission1.user.username, submission1.user.profile.name, submission1.user.email)
        )


class CourseOperationSurveyDownloadUtf8Test(CourseOperationSurveyDownloadTestMixin):

    def get_url(self):
        return reverse('biz:course_operation:survey_download_utf8')

    def validate_bom(self, content):
        return self.validate_bom_utf8(content)

    def get_survey_csv_rows_unicode(self, content):
        return self.get_survey_csv_rows_unicode_from_utf8(content)

    def test_survey_download_director(self):
        self.setup_user()
        _manager = self._director_manager

        # has contract register
        user1 = self._create_submission_user()
        self.create_contract_register(user1, self.contract)
        submission1 = SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': user1,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission #1"}',
        })
        # has not contract register
        user2 = self._create_submission_user()
        CourseEnrollment.enroll(user2, self.course_spoc1.id)
        self.submission2 = SurveySubmissionFactory.create(**{
            'course_id': self.course_spoc1.id,
            'unit_id': '11111111111111111111111111111111',
            'user': user2,
            'survey_name': 'survey #1',
            'survey_answer': '{"Q1": "1", "Q2": "2", "Q3": "submission #2"}',
        })

        with self.skip_check_course_selection(current_contract=self.contract, current_organization=self.contract_org,
                                              current_course=self.course_spoc1, current_manager=_manager):
            response = self.client.post(self.get_url(), {})

        self.assertEqual(200, response.status_code)
        content = response.content
        self.assertTrue(self.validate_bom(content))
        rows = self.get_survey_csv_rows_unicode(content)
        self.assertEqual(2, len(rows))
        self.assertEqual(rows[0], u'"Unit ID"\t"Survey Name"\t"Created"\t"User Name"\t"Full Name"\t"Email"\t"Resigned"\t"Unenrolled"\t"Q1"\t"Q2"\t"Q3"')
        self.assertEqual(
            rows[1],
            u'"11111111111111111111111111111111"\t"survey #1"\t"%s"\t"%s"\t"%s"\t"%s"\t""\t""\t"1"\t"1,2"\t"submission #1"'
            % (format_for_csv(submission1.created), submission1.user.username, submission1.user.profile.name, submission1.user.email)
        )

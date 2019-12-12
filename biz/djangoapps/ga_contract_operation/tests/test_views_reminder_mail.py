# -*- coding: utf-8 -*-
"""
Test for contract_operation reminder_mail feature
"""
from collections import OrderedDict
from copy import copy
from datetime import datetime
from dateutil.tz import tzutc
import ddt
import json
from mock import patch
import pytz

from django.core.urlresolvers import reverse
from django.http import HttpResponse

from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore, ScoreStore
from biz.djangoapps.ga_achievement.tests.factories import PlaybackFactory, ScoreFactory, PlaybackBatchStatusFactory, \
    ScoreBatchStatusFactory
from biz.djangoapps.ga_achievement.management.commands.update_biz_score_status import get_grouped_target_sections
from biz.djangoapps.ga_contract_operation.models import ContractReminderMail
from biz.djangoapps.ga_contract.tests.factories import ContractDetailFactory
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.ga_login.tests.factories import BizUserFactory
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.gx_org_group.tests.factories import GroupUtil, RightFactory
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.tests.testcase import BizStoreTestBase

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from student.models import UserStanding, UserProfile
from student.tests.factories import UserFactory, UserStandingFactory, CourseEnrollmentFactory,\
    CourseEnrollmentAttributeFactory

from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory

from freezegun import freeze_time


@ddt.ddt
class ContractOperationReminderMailViewTest(BizContractTestBase, BizStoreTestBase):

    def setUp(self):
        super(ContractOperationReminderMailViewTest, self).setUp()

        self._create_contract_reminder_mail_default()

        self.course_self_paced1 = CourseFactory.create(
            org=self.contract_org.org_code, number='self_paced_course', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            individual_end_days=10,
            deadline_start=datetime(2016, 1, 5, 0, 0, 0, tzinfo=tzutc())
        )

        self.contract_submission_reminder = self._create_contract(
            contract_name='test reminder mail',
            contractor_organization=self.contract_org,
            detail_courses=[self.course_spoc1.id, self.course_spoc2.id, self.course_self_paced1.id],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        # Update sections and components to fit the conditions for submission reminder
        chapter_x = ItemFactory.create(parent=self.course_spoc1, category='chapter', display_name='chapter_x')
        section_x1 = ItemFactory.create(parent=chapter_x, category='sequential', display_name='sequential_x1',
                                        metadata={'graded': True, 'format': 'format_x1'})
        vertical_x1a = ItemFactory.create(parent=section_x1, category='vertical', display_name='vertical_x1a')
        component_x1a_1 = ItemFactory.create(parent=vertical_x1a, category='problem',
                                             display_name='component_x1a_1')
        self.store.update_item(chapter_x, self.user.id)

        self._set_date()
        self._expect_score_record_list = []
        self._expect_playback_record_list = []
        self._score_section_name1 = "Section1:Sample__Section1 Confirm Test"
        self._score_section_name2 = "Section2:Sample__Section2 Confirm Test"
        self._playback_section_name1 = "Section1:Sample__Section1 Time"
        self._playback_section_name2 = "Section2:Sample__Section2 Time"

    @property
    def _director_manager(self):
        return self._create_manager(
            org=self.contract_org, user=self.user, created=self.contract_org, permissions=[self.director_permission])

    @property
    def _manager_manager(self):
        return self._create_manager(
            org=self.contract_org, user=self.user, created=self.contract_org, permissions=[self.manager_permission])

    # ------------------------------------------------------------
    # Delete Reminder Mail
    # ------------------------------------------------------------
    def _url_delete_mail_ajax(self):
        return reverse('biz:contract_operation:reminder_mail_delete_ajax')

    def _create_other_contract(self):
        contract_org = self._create_organization(org_code='contractor')

    def _delete_only_use_create_contract(self, deadline):
        course_delete_use = CourseFactory.create(
            org=self.contract_org.org_code, number='delete_mail', run='run',
            start=datetime(2016, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            deadline_start=deadline,
            individual_end_days=10,
        )
        contract_submission_reminder = self._create_contract(
            contract_name='test reminder mail',
            contractor_organization=self.contract_org,
            detail_courses=[course_delete_use],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=True,
        )
        return contract_submission_reminder

    def _delete_only_use_create_another_contract(self, deadline):
        course_delete_use = CourseFactory.create(
            org=self.contract_org.org_code, number='another_delete_mail', run='run',
            start=datetime(2017, 1, 1, 0, 0, 0, tzinfo=tzutc()),  # must be the past date
            self_paced=True,
            deadline_start=deadline,
            individual_end_days=10,
        )
        another_contract_submission_reminder = self._create_contract(
            contract_name='test another reminder mail',
            contractor_organization=self.contract_org,
            detail_courses=[course_delete_use],
            additional_display_names=['country', 'dept'],
            send_submission_reminder=False,
        )
        return another_contract_submission_reminder

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_delete_mail_success(self, mail_type):
        self.setup_user()
        deadline = datetime(2019, 1, 1, 0, 0, 0, tzinfo=tzutc())
        contract = self._delete_only_use_create_contract(deadline)
        # Create contract_remainder_mail
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 5,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Successfully to save the template e-mail.")

        contract_mail = ContractReminderMail.objects.get(contract=contract, mail_type=mail_type)
        self.assertEquals(contract_mail.reminder_email_days, 5)
        self.assertEquals(contract_mail.mail_subject, 'Test Subject')
        self.assertEquals(contract_mail.mail_body, 'Test Body')
        self.assertEquals(contract_mail.mail_body2, 'Test Body2')

        # Delete contract_reminder_mail
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_delete_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
            })
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Reminder mail deleted.")
        self.assertEqual(0,len(ContractReminderMail.objects.filter(contract=contract, mail_type=mail_type)))

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_delete_mail_same_error(self, mail_type):
        self.setup_user()
        deadline = datetime(2019, 1, 1, 0, 0, 0, tzinfo=tzutc())
        contract = self._delete_only_use_create_contract(deadline)
        another_contract_reminder_false = self._delete_only_use_create_another_contract(deadline)
        # Create contract_remainder_mail
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 5,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Successfully to save the template e-mail.")

        # Can not create and delete reminder mail
        with self.skip_check_course_selection(current_contract=another_contract_reminder_false):
            response = self.client.post(self._url_delete_mail_ajax(), {
                'contract_id': another_contract_reminder_false.id,
                'mail_type': mail_type,
            })
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Unauthorized access.")

        # Delete reminder mail request another contract
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_delete_mail_ajax(), {
                'contract_id': self.contract.id,
                'mail_type': mail_type,
            })
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Current contract is changed. Please reload this page.")

        # mail_type is None type
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_delete_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': 'Nonetype',
            })
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Unauthorized access.")

        # No record
        with self.skip_check_course_selection(current_contract=self.contract_submission_reminder):
            response = self.client.post(self._url_delete_mail_ajax(), {
                'contract_id': self.contract_submission_reminder.id,
                'mail_type': mail_type,
            })
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Input Invitation")
        self.assertEqual(0,len(ContractReminderMail.objects.filter(contract=self.contract_submission_reminder, mail_type=mail_type)))

        #
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.ContractReminderMail.objects.filter',
                side_effect=Exception('test')):
            response = self.client.post(self._url_delete_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Failed to deleted item.")

    # ------------------------------------------------------------
    # Show Reminder Mail
    # ------------------------------------------------------------
    def _url_mail(self):
        return reverse('biz:contract_operation:reminder_mail')

    def test_mail_404(self):
        self.setup_user()
        with self.skip_check_course_selection(
                current_manager=self._director_manager, current_organization=self.contract_org,
                current_contract=self.contract, current_course=self.course_spoc1):
            self.assert_request_status_code(404, self._url_mail())

    def test_mail(self):
        self.setup_user()

        self._create_score_batch_status()
        self._create_achievement_score_column()
        self._create_playback_batch_status()
        self._create_achievement_playback_column()

        with self.skip_check_course_selection(
                current_manager=self._director_manager, current_organization=self.contract_org,
                current_contract=self.contract_submission_reminder, current_course=self.course_spoc1), patch(
            'biz.djangoapps.ga_contract_operation.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.assert_request_status_code(200, self._url_mail())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_contract_operation/reminder_mail.html')

        mail_info = render_to_response_args[1]['mail_info']
        self.assertEqual(ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER, mail_info.mail_type)
        self.assertEqual('Test Subject for Submission Reminder', mail_info.mail_subject)
        self.assertEqual('Test Body for Submission Reminder {username} and {fullname}', mail_info.mail_body)
        self.assertEqual('Test Body2 for Submission Reminder', mail_info.mail_body2)

        search_mail_info = render_to_response_args[1]['search_mail_info']
        self.assertEqual([
            'Not Enrolled',
            'Enrolled',
            'Finish Enrolled',
        ], search_mail_info['student_status_list'])
        self.assertEqual([
            ContractReminderMail.MAIL_PARAM_USERNAME,
            ContractReminderMail.MAIL_PARAM_EMAIL_ADDRESS,
            ContractReminderMail.MAIL_PARAM_COURSE_NAME,
            ContractReminderMail.MAIL_PARAM_FULLNAME,
            ContractReminderMail.MAIL_PARAM_EXPIRE_DATE,
        ], search_mail_info['search_mail_params'])
        expect_search_detail_other_list = OrderedDict()
        expect_search_detail_other_list['login_code'] = "Login Code"
        expect_search_detail_other_list['full_name'] = "Full Name"
        expect_search_detail_other_list['username'] = "Username"
        expect_search_detail_other_list['email'] = "Email Address"
        for i in range(1, 11):
            expect_search_detail_other_list['org' + str(i)] = "Organization" + str(i)
        for i in range(1, 11):
            expect_search_detail_other_list['item' + str(i)] = "Item" + str(i)
        self.assertEqual(expect_search_detail_other_list, search_mail_info['search_detail_other_list'])
        self.assertEqual([
            [self._score_section_name1, ScoreStore.COLUMN_TYPE__PERCENT],
            [self._score_section_name2, ScoreStore.COLUMN_TYPE__PERCENT]
        ], json.loads(search_mail_info['hidden_score_columns']))
        self.assertEqual(
            [self._score_section_name1, self._score_section_name2], search_mail_info['score_section_names'])
        self.assertEqual([
            [self._playback_section_name1, PlaybackStore.COLUMN_TYPE__TIME],
            [self._playback_section_name2, PlaybackStore.COLUMN_TYPE__TIME]
        ], json.loads(search_mail_info['hidden_playback_columns']))
        self.assertEqual(
            [self._playback_section_name1, self._playback_section_name2], search_mail_info['playback_section_names'])

    def test_mail_no_store_batch(self):
        self.setup_user()

        with self.skip_check_course_selection(
                current_manager=self._director_manager, current_organization=self.contract_org,
                current_contract=self.contract_submission_reminder, current_course=self.course_spoc1):
            with patch('biz.djangoapps.ga_contract_operation.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.assert_request_status_code(200, self._url_mail())

        render_to_response_args = mock_render_to_response.call_args[0]
        search_mail_info = render_to_response_args[1]['search_mail_info']
        self.assertDictEqual({}, search_mail_info['hidden_score_columns'])
        self.assertEqual([], search_mail_info['score_section_names'])
        self.assertDictEqual({}, search_mail_info['hidden_playback_columns'])
        self.assertEqual([], search_mail_info['playback_section_names'])

    def test_mail_is_status_managed_true(self):
        self.setup_user()
        director_manager = self._director_manager
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')
        self.overview = CourseOverview.get_from_id(self.course.id)
        self.overview.extra.is_status_managed = True
        self.overview.extra.save()

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course, current_manager=director_manager):
            with patch('biz.djangoapps.ga_contract_operation.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.assert_request_status_code(200, self._url_mail())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_contract_operation/reminder_mail.html')
        is_status_managed = render_to_response_args[1]['is_status_managed']
        self.assertEqual(True, is_status_managed)

    def test_mail_is_status_managed_false(self):
        self.setup_user()
        director_manager = self._director_manager
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')
        self.overview = CourseOverview.get_from_id(self.course.id)
        self.overview.extra.is_status_managed = False
        self.overview.extra.save()

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course, current_manager=director_manager):
            with patch('biz.djangoapps.ga_contract_operation.views.render_to_response',
                       return_value=HttpResponse()) as mock_render_to_response:
                self.assert_request_status_code(200, self._url_mail())

        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'ga_contract_operation/reminder_mail.html')
        is_status_managed = render_to_response_args[1]['is_status_managed']
        self.assertEqual(False, is_status_managed)

    # ------------------------------------------------------------
    # Save Reminder Mail
    # ------------------------------------------------------------
    def _url_save_mail_ajax(self):
        return reverse('biz:contract_operation:reminder_mail_save_ajax')

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_can_not_send_submission_reminder(self, mail_type):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': self.contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Unauthorized access.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_contract_unmatch(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': self.contract.id,  # unmatch
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Current contract is changed. Please reload this page.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_no_contract_id(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Current contract is changed. Please reload this page.")

    def test_save_mail_illegal_mail_type(self):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': 'NoneType',
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        warning_log.assert_called_with("Illegal mail-type: NoneType")

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Unauthorized access.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_empty_reminder_email_days(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': '',
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please use the pull-down menu to choose the reminder e-mail days.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_reminder_email_days_is_not_number(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': '@',
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please use the pull-down menu to choose the reminder e-mail days.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_reminder_email_days_is_out_of_range(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': '-9999',
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please use the pull-down menu to choose the reminder e-mail days.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_empty_mail_subject(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': '',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please enter the subject of an e-mail.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_illegal_mail_subject(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'a' * 129,
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Subject within 128 characters.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_empty_mail_body(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': '',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please enter the body of an e-mail.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_empty_mail_body2(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': '',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Please enter the body of an e-mail.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_success(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Successfully to save the template e-mail.")

        contract_mail = ContractReminderMail.objects.get(contract=contract, mail_type=mail_type)
        self.assertEquals(contract_mail.reminder_email_days, 3)
        self.assertEquals(contract_mail.mail_subject, 'Test Subject')
        self.assertEquals(contract_mail.mail_body, 'Test Body')
        self.assertEquals(contract_mail.mail_body2, 'Test Body2')

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_save_mail_error(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.ContractReminderMail.objects.get_or_create',
                side_effect=Exception('test')):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Failed to save the template e-mail.")

    # ------------------------------------------------------------
    # Send Reminder Mail
    # ------------------------------------------------------------
    def _url_send_mail_ajax(self):
        return reverse('biz:contract_operation:reminder_mail_send_ajax')

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_can_not_send_submission_reminder(self, mail_type):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract):
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': self.contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], 'Unauthorized access.')

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_contract_unmatch(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': self.contract.id,  # unmatch
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Current contract is changed. Please reload this page.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_no_contract_id(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_send_mail_ajax(), {
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Current contract is changed. Please reload this page.")

    def test_send_mail_illegal_mail_type(self):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.log.warning') as warning_log:
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': 'NoneType',
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        warning_log.assert_called_with("Illegal mail-type: NoneType")

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Unauthorized access.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_pre_update(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Please save the template e-mail before sending.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_success(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder

        # Save
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Successfully to save the template e-mail.")

        contract_mail = ContractReminderMail.objects.get(contract=contract, mail_type=mail_type)
        self.assertEquals(contract_mail.mail_subject, 'Test Subject')
        self.assertEquals(contract_mail.mail_body, 'Test Body')

        # Send
        now = datetime_utils.timezone_now()
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.send_mail') as send_mail:
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        mail_param = {'username': self.user.username,
                      'fullname': self.user.profile.name.encode('utf-8')}
        target_courses = [get_grouped_target_sections(self.course_spoc1)]
        mail_body = contract_mail.compose_mail_body(target_courses)
        send_mail.assert_called_with(self.user, 'Test Subject', mail_body.encode('utf-8'), mail_param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Successfully to send the test e-mail.")

    @ddt.data(
        ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
    )
    def test_send_mail_error(self, mail_type):
        self.setup_user()
        contract = self.contract_submission_reminder

        # Save
        with self.skip_check_course_selection(current_contract=contract):
            response = self.client.post(self._url_save_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], "Successfully to save the template e-mail.")

        contract_mail = ContractReminderMail.objects.get(contract=contract, mail_type=mail_type)
        self.assertEquals(contract_mail.mail_subject, 'Test Subject')
        self.assertEquals(contract_mail.mail_body, 'Test Body')

        # Send
        with self.skip_check_course_selection(current_contract=contract), patch(
                'biz.djangoapps.ga_contract_operation.views.send_mail', side_effect=Exception('test')) as send_mail:
            response = self.client.post(self._url_send_mail_ajax(), {
                'contract_id': contract.id,
                'mail_type': mail_type,
                'reminder_email_days': 3,
                'mail_subject': 'Test Subject',
                'mail_body': 'Test Body',
                'mail_body2': 'Test Body2',
            })

        send_mail.assert_called()

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEquals(data['error'], "Failed to send the test e-mail.")

    # ------------------------------------------------------------
    # Search Reminder Mail
    # ------------------------------------------------------------
    @property
    def _url_search_ajax(self):
        return reverse('biz:contract_operation:reminder_search_ajax')

    def _set_date(self):
        self.utc_datetime = datetime(2016, 3, 1, 16, 58, 30, 0, tzinfo=pytz.utc)
        self.utc_datetime_update = datetime(2016, 3, 10, 16, 58, 30, 0, tzinfo=pytz.utc)

    def _create_reminder_search_param(
            self, contract_id=None, student_status='', total_score_from='', total_score_to='', total_playback_from='',
            total_playback_to='', total_playback_no=False, is_status_managed=False, survey_name_unit_id='', **kwargs):
        param = {
            'contract_id': contract_id or self.contract_submission_reminder.id,
            'total_score_from': total_score_from,
            'total_score_to': total_score_to,
            'total_playback_from': total_playback_from,
            'total_playback_to': total_playback_to,
            'survey_name_unit_id': survey_name_unit_id,
        }
        if is_status_managed:
            param['student_status'] = student_status
        if total_playback_no:
            param['total_playback_no'] = 1

        for i in range(1, 6):
            param['detail_condition_score_name_' + str(i)] = ''
            param['detail_condition_score_from_' + str(i)] = ''
            param['detail_condition_score_to_' + str(i)] = ''
            param['detail_condition_playback_name_' + str(i)] = ''
            param['detail_condition_playback_from_' + str(i)] = ''
            param['detail_condition_playback_to_' + str(i)] = ''
            param['detail_condition_other_name_' + str(i)] = ''
            param['detail_condition_other_' + str(i)] = ''

        param.update(**kwargs)
        return param

    def _create_member(self, org, group, user, code, is_active=True, is_delete=False, **kwargs):
        return MemberFactory.create(
            org=org,
            group=group,
            user=user,
            code=code,
            created_by=self.user,
            creator_org=org,
            updated_by=self.user,
            updated_org=org,
            is_active=is_active,
            is_delete=is_delete,
            **kwargs
        )

    def _create_score_batch_status(self, contract=None, course=None, status=None):
        self.batch_status = ScoreBatchStatusFactory.create(
            contract=contract or self.contract_submission_reminder,
            course_id=unicode(course.id) if course else unicode(self.course_spoc1.id),
            status=status or 'Finished',
            student_count=4
        )

    def _create_playback_batch_status(self, contract=None, course=None, status=None):
        self.batch_status = PlaybackBatchStatusFactory.create(
            contract=contract or self.contract_submission_reminder,
            course_id=unicode(course.id) if course else unicode(self.course_spoc1.id),
            status=status or 'Finished',
            student_count=4
        )

    def _create_achievement_score_column(self, contract=None, course=None):
        self._dict_score_column_data = {
            ScoreStore.FIELD_CONTRACT_ID: contract.id if contract else self.contract_submission_reminder.id,
            ScoreStore.FIELD_COURSE_ID: unicode(course.id) if course else unicode(self.course_spoc1.id),
            ScoreStore.FIELD_DOCUMENT_TYPE: ScoreStore.FIELD_DOCUMENT_TYPE__COLUMN,
            ScoreStore.FIELD_FULL_NAME: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_USERNAME: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_EMAIL: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_STUDENT_STATUS: ScoreStore.COLUMN_TYPE__TEXT,
            ScoreStore.FIELD_CERTIFICATE_STATUS: ScoreStore.COLUMN_TYPE__TIME,
            ScoreStore.FIELD_TOTAL_SCORE: ScoreStore.COLUMN_TYPE__PERCENT,
            self._score_section_name1: ScoreStore.COLUMN_TYPE__PERCENT,
            self._score_section_name2: ScoreStore.COLUMN_TYPE__PERCENT,
        }
        ScoreFactory.create(**self._dict_score_column_data)

    def _create_achievement_score_data(self, username, email, contract=None, course=None, full_name=None, status=None,
                                       certificate_status=None, total_score=0.9, section1_score=0.3,
                                       section2_score=0.5):
        score_data = {
            ScoreStore.FIELD_CONTRACT_ID: contract.id if contract else self.contract_submission_reminder.id,
            ScoreStore.FIELD_COURSE_ID: unicode(course.id) if course else unicode(self.course_spoc1.id),
            ScoreStore.FIELD_DOCUMENT_TYPE: ScoreStore.FIELD_DOCUMENT_TYPE__RECORD,
            ScoreStore.FIELD_FULL_NAME: full_name or 'TEST TEST',
            ScoreStore.FIELD_USERNAME: username,
            ScoreStore.FIELD_EMAIL: email,
            ScoreStore.FIELD_STUDENT_STATUS: status or ScoreStore.FIELD_STUDENT_STATUS__ENROLLED,
            ScoreStore.FIELD_CERTIFICATE_STATUS: certificate_status or ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE,
            ScoreStore.FIELD_TOTAL_SCORE: total_score,
            ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE: self.utc_datetime,
            self._score_section_name1: section1_score,
            self._score_section_name2: section2_score,
        }
        self._expect_score_record_list.append(score_data)
        ScoreFactory.create(**score_data)

    def _create_achievement_playback_column(self, contract=None, course=None):
        self._dict_playback_column_data = {
            PlaybackStore.FIELD_CONTRACT_ID: contract.id if contract else self.contract_submission_reminder.id,
            PlaybackStore.FIELD_COURSE_ID: unicode(course.id) if course else unicode(self.course_spoc1.id),
            PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN,
            PlaybackStore.FIELD_FULL_NAME: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_USERNAME: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_EMAIL: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_STUDENT_STATUS: PlaybackStore.COLUMN_TYPE__TEXT,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: PlaybackStore.COLUMN_TYPE__TIME,
            self._playback_section_name1: PlaybackStore.COLUMN_TYPE__TIME,
            self._playback_section_name2: PlaybackStore.COLUMN_TYPE__TIME,
        }
        PlaybackFactory.create(**self._dict_playback_column_data)

    def _create_achievement_playback_data(
            self, username, email, contract=None, course=None, full_name=None, status=None, total_time=10080,
            section1_time=6000, section2_time=4080):
        playback_data = {
            PlaybackStore.FIELD_CONTRACT_ID: contract.id if contract else self.contract_submission_reminder.id,
            PlaybackStore.FIELD_COURSE_ID: unicode(course.id) if course else unicode(self.course_spoc1.id),
            PlaybackStore.FIELD_DOCUMENT_TYPE: PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD,
            PlaybackStore.FIELD_FULL_NAME: full_name or 'TEST TEST',
            PlaybackStore.FIELD_USERNAME: username,
            PlaybackStore.FIELD_EMAIL: email,
            PlaybackStore.FIELD_STUDENT_STATUS: status or PlaybackStore.FIELD_STUDENT_STATUS__ENROLLED,
            PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME: total_time,
            self._playback_section_name1: section1_time,
            self._playback_section_name2: section2_time,
        }
        self._expect_playback_record_list.append(playback_data)
        PlaybackFactory.create(**playback_data)

    def _assert_search_ajax_successful(self, data, show_list):
        self.assertEquals(data['info'], 'Successfully to search.')
        self.assertEqual(len(json.loads(data['show_list'])), show_list)

    def _assert_search_result_base(self, result, recid, user, profile, status='During registration',
                                   student_status='Enrolled', total_score='0.9', score_section1='0.3',
                                   score_section2='0.5', total_time='10080', playback_section1='6000',
                                   playback_section2='4080', is_score=True, is_playback=True, is_status_managed=False):
        self.assertEqual(result['recid'], recid)
        self.assertEqual(result['user_id'], user.id)
        self.assertEqual(result['user_name'], user.username)
        self.assertEqual(result['user_email'], user.email)
        self.assertEqual(result['full_name'], profile.name)
        self.assertEqual(result['register_status'], status)
        if is_status_managed:
            self.assertEqual(result['student_status'], student_status)
        _none = 'None'
        if is_score:
            self.assertEqual(result['total_score'], float(total_score) if total_score is not _none else _none)
            self.assertEqual(result[self._score_section_name1],
                             float(score_section1) if score_section1 is not _none else _none)
            self.assertEqual(result[self._score_section_name2],
                             float(score_section2) if score_section2 is not _none else _none)
        if is_playback:
            self.assertEqual(result['total_playback'], float(total_time) if total_time is not _none else _none)
            self.assertEqual(result[self._playback_section_name1],
                             float(playback_section1) if playback_section1 is not _none else _none)
            self.assertEqual(result[self._playback_section_name2],
                             float(playback_section2) if playback_section2 is not _none else _none)

    def test_reminder_search_ajax(self):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_reminder_search_param()

        user = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course_spoc1.id)
        CourseEnrollmentFactory.create(user=user, course_id=self.course_spoc1.id)
        ContractRegisterFactory.create(user=user, contract=self.contract_submission_reminder, status='Register')
        bizuser = BizUserFactory.create(user=user, login_code='login_code')
        member_kwargs = {}
        for i in range(1, 11):
            member_kwargs['org' + str(i)] = 'org' + str(i)
            member_kwargs['item' + str(i)] = 'item' + str(i)
        member = self._create_member(org=self.contract_org, group=None, user=user, code='code', **dict(member_kwargs))

        self._create_score_batch_status()
        self._create_achievement_score_column()
        self._create_achievement_score_data(username=user.username, email=user.email)
        self._create_playback_batch_status()
        self._create_achievement_playback_column()
        self._create_achievement_playback_data(username=user.username, email=user.email)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 1)
        show_list = json.loads(data['show_list'])
        self._assert_search_result_base(result=show_list[0], recid=1, user=user, profile=user.profile)
        self.assertEqual(show_list[0]['login_code'], bizuser.login_code)
        for i in range(1, 11):
            self.assertEqual(show_list[0]['org' + str(i)], getattr(member, 'org' + str(i)))
            self.assertEqual(show_list[0]['item' + str(i)], getattr(member, 'item' + str(i)))

    def test_reminder_search_ajax_authorized_error(self):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_reminder_search_param()
        param.pop('contract_id')

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_reminder_search_ajax_unmatch_contract(self):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_reminder_search_param(contract_id=999)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Current contract is changed. Please reload this page.")

    @ddt.data(
        'email', 'username', 'full_name', 'login_code', 'org1', 'org2', 'org3', 'org4', 'org5', 'org6', 'org7', 'org8',
        'org9', 'org10', 'item1', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7', 'item8', 'item9', 'item10'
    )
    def test_reminder_search_ajax_detail_other(self, param_key):
        self.setup_user()
        director_manager = self._director_manager
        search_keyword = 'search_param_sample_char'
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course_spoc1.id)

        bizuser = None
        member = None
        if param_key in ['email', 'username']:
            user = UserFactory.create(**dict({param_key: search_keyword}))
            CourseEnrollmentFactory.create(user=user, course_id=self.course_spoc1.id)
            ContractRegisterFactory.create(user=user, contract=self.contract_submission_reminder, status='Register')
        elif param_key in ['full_name']:
            user = UserFactory.create(first_name=search_keyword)
            CourseEnrollmentFactory.create(user=user, course_id=self.course_spoc1.id)
            ContractRegisterFactory.create(user=user, contract=self.contract_submission_reminder, status='Register')
        elif param_key in ['login_code']:
            user = UserFactory.create()
            CourseEnrollmentFactory.create(user=user, course_id=self.course_spoc1.id)
            ContractRegisterFactory.create(user=user, contract=self.contract_submission_reminder, status='Register')
            bizuser = BizUserFactory.create(user=user, login_code=search_keyword)
        else:
            user = UserFactory.create()
            CourseEnrollmentFactory.create(user=user, course_id=self.course_spoc1.id)
            ContractRegisterFactory.create(user=user, contract=self.contract_submission_reminder, status='Register')
            member = self._create_member(
                org=self.contract_org, group=None, user=user, code='code', **dict({param_key: search_keyword}))

        for i in range(1, 6):
            param = self._create_reminder_search_param(**dict({
                'detail_condition_other_name_' + str(i): param_key,
                'detail_condition_other_' + str(i): search_keyword
            }))

            with self.skip_check_course_selection(current_organization=self.contract_org,
                                                  current_contract=self.contract_submission_reminder,
                                                  current_course=self.course_spoc1, current_manager=director_manager):
                response = self.client.post(self._url_search_ajax, param)

            self.assertEqual(200, response.status_code)
            data = json.loads(response.content)
            self._assert_search_ajax_successful(data, 1)
            show_list = json.loads(data['show_list'])
            self._assert_search_result_base(
                result=show_list[0], recid=1, user=user, profile=user.profile, is_score=False, is_playback=False)
            if param_key in ['login_code']:
                self.assertEqual(show_list[0][param_key], bizuser.login_code)
            if param_key in ['org' + str(i) for i in range(1, 11)] + ['item' + str(i) for i in range(1, 11)]:
                self.assertEqual(show_list[0][param_key], getattr(member, param_key))

    @ddt.unpack
    @ddt.data(
        ('', '50', False, 1), ('', '20', False, 0), ('', '0', False, 0),
        ('20', '', False, 1), ('31', '', False, 0),
        ('29', '31', False, 1), ('31', '50', False, 0), ('30', '30', False, 1),
        ('', '', True, 0), ('20', '30', True, 0)
    )
    def test_reminder_search_ajax_detail_score_other(self, param_from, param_to, param_no, expect):
        self.setup_user()
        director_manager = self._director_manager

        self._create_achievement_score_column()
        self._create_score_batch_status()

        user1 = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course_spoc1.id)
        CourseEnrollmentFactory.create(user=user1, course_id=self.course_spoc1.id)
        ContractRegisterFactory.create(user=user1, contract=self.contract_submission_reminder, status='Register')
        self._create_achievement_score_data(username=user1.username, email=user1.email)

        for i in range(1, 6):
            param_args = {
                'detail_condition_score_name_' + str(i): self._score_section_name1,
                'detail_condition_score_from_' + str(i): param_from,
                'detail_condition_score_to_' + str(i): param_to
            }
            if param_no:
                param_args['detail_condition_score_no_' + str(i)] = 1
            param = self._create_reminder_search_param(**dict(param_args))

            with self.skip_check_course_selection(current_organization=self.contract_org,
                                                  current_contract=self.contract_submission_reminder,
                                                  current_course=self.course_spoc1, current_manager=director_manager):
                response = self.client.post(self._url_search_ajax, param)

            self.assertEqual(200, response.status_code)
            data = json.loads(response.content)
            self._assert_search_ajax_successful(data, expect)
            if expect > 0:
                show_list = json.loads(data['show_list'])
                self._assert_search_result_base(
                    result=show_list[0], recid=1, user=user1, profile=user1.profile, is_playback=False)

    @ddt.unpack
    @ddt.data(
        ('', '150', False, 1), ('', '99', False, 0), ('', '0', False, 0),
        ('100', '', False, 1), ('101', '', False, 0),
        ('99', '100', False, 1), ('101', '102', False, 0), ('100', '100', False, 1),
        ('', '', True, 0), ('50', '150', True, 0)
    )
    def test_reminder_search_ajax_detail_playback_other(self, param_from, param_to, param_no, expect):
        self.setup_user()
        director_manager = self._director_manager
        self._create_playback_batch_status()
        self._create_achievement_playback_column()
        user1 = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course_spoc1.id)
        CourseEnrollmentFactory.create(user=user1, course_id=self.course_spoc1.id)
        ContractRegisterFactory.create(user=user1, contract=self.contract_submission_reminder, status='Register')
        self._create_achievement_playback_data(username=user1.username, email=user1.email)

        for i in range(1, 6):
            param_args = {
                'detail_condition_playback_name_' + str(i): self._playback_section_name1,
                'detail_condition_playback_from_' + str(i): param_from,
                'detail_condition_playback_to_' + str(i): param_to
            }
            if param_no:
                param_args['detail_condition_playback_no_' + str(i)] = 1
            param = self._create_reminder_search_param(**dict(param_args))

            with self.skip_check_course_selection(current_organization=self.contract_org,
                                                  current_contract=self.contract_submission_reminder,
                                                  current_course=self.course_spoc1, current_manager=director_manager):
                response = self.client.post(self._url_search_ajax, param)

            self.assertEqual(200, response.status_code)
            data = json.loads(response.content)
            self._assert_search_ajax_successful(data, expect)
            if expect > 0:
                show_list = json.loads(data['show_list'])
                self._assert_search_result_base(
                    result=show_list[0], recid=1, user=user1, profile=user1.profile, is_score=False)

    @ddt.unpack
    @ddt.data(
        ('', '100', 1), ('', '80', 0),
        ('70', '', 1), ('91', '', 0),
        ('89', '91', 1), ('91', '92', 0), ('90', '90', 1)
    )
    def test_reminder_search_ajax_total_score(self, param_from, param_to, expect):
        self.setup_user()
        director_manager = self._director_manager
        user1 = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course_spoc1.id)
        CourseEnrollmentFactory.create(user=user1, course_id=self.course_spoc1.id)
        ContractRegisterFactory.create(user=user1, contract=self.contract_submission_reminder, status='Register')
        self._create_score_batch_status()
        self._create_achievement_score_column()
        self._create_achievement_score_data(username=user1.username, email=user1.email)

        param = self._create_reminder_search_param(total_score_from=param_from, total_score_to=param_to)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, expect)
        if expect > 0:
            show_list = json.loads(data['show_list'])
            self._assert_search_result_base(
                result=show_list[0], recid=1, user=user1, profile=user1.profile, is_playback=False)

    @ddt.unpack
    @ddt.data(
        ('', '170', False, 1), ('', '165', False, 0),
        ('165', '', False, 1), ('170', '', False, 0),
        ('165', '170', False, 1), ('169', '170', False, 0), ('168', '168', False, 1),
        ('', '', True, 0), ('165', '170', True, 0),
    )
    def test_reminder_search_ajax_total_playback(self, param_from, param_to, param_no, expect):
        self.setup_user()
        director_manager = self._director_manager
        user1 = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course_spoc1.id)
        CourseEnrollmentFactory.create(user=user1, course_id=self.course_spoc1.id)
        ContractRegisterFactory.create(user=user1, contract=self.contract_submission_reminder, status='Register')
        self._create_playback_batch_status()
        self._create_achievement_playback_column()
        self._create_achievement_playback_data(username=user1.username, email=user1.email)

        if param_no:
            param = self._create_reminder_search_param(
                total_playback_from=param_from, total_playback_to=param_to, total_playback_no=True)
        else:
            param = self._create_reminder_search_param(
                total_playback_from=param_from, total_playback_to=param_to)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, expect)
        if expect > 0:
            show_list = json.loads(data['show_list'])
            self._assert_search_result_base(
                result=show_list[0], recid=1, user=user1, profile=user1.profile, is_score=False)

    def test_reminder_search_ajax_student_status_enrolled(self):
        self.setup_user()
        director_manager = self._director_manager
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')
        # Search target user
        user1 = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course.id)
        enrollment = CourseEnrollmentFactory.create(user=user1, course_id=self.course.id)
        ContractRegisterFactory.create(user=user1, contract=self.contract_submission_reminder, status='Register')
        self.attr = CourseEnrollmentAttributeFactory.create(
            enrollment=enrollment, namespace='ga', name='attended_status',
            value='{"attended_date": "2010-10-10T10:10:10.123456+00:00"}')

        self.overview = CourseOverview.get_from_id(self.course.id)
        self.overview.extra.is_status_managed = True
        self.overview.extra.save()

        param = self._create_reminder_search_param(student_status='Enrolled', is_status_managed=True)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course, current_manager=director_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 1)
        show_list = json.loads(data['show_list'])
        self._assert_search_result_base(
            result=show_list[0], recid=1, user=user1, profile=user1.profile, status='During registration',
            student_status='Enrolled', is_score=False, is_playback=False, is_status_managed=True
        )

    def test_reminder_search_ajax_student_status_finish_enrolled(self):
        self.setup_user()
        director_manager = self._director_manager
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')
        # Search target user
        user1 = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course.id)
        enrollment = CourseEnrollmentFactory.create(user=user1, course_id=self.course.id)
        ContractRegisterFactory.create(user=user1, contract=self.contract_submission_reminder, status='Register')
        self.attr = CourseEnrollmentAttributeFactory.create(
            enrollment=enrollment, namespace='ga', name='attended_status',
            value='{"completed_date": "2010-10-10T10:10:10.123456+00:00"}')

        self.overview = CourseOverview.get_from_id(self.course.id)
        self.overview.extra.is_status_managed = True
        self.overview.extra.save()

        param = self._create_reminder_search_param(student_status='Finish Enrolled', is_status_managed=True)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course, current_manager=director_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 1)
        show_list = json.loads(data['show_list'])
        self._assert_search_result_base(
            result=show_list[0], recid=1, user=user1, profile=user1.profile, status='During registration',
            student_status='Finish Enrolled', is_score=False, is_playback=False, is_status_managed=True
        )

    def test_reminder_search_ajax_student_status_not_enrolled(self):
        self.setup_user()
        director_manager = self._director_manager
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')
        # Search target user
        user1 = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course.id)
        enrollment = CourseEnrollmentFactory.create(user=user1, course_id=self.course.id)
        ContractRegisterFactory.create(user=user1, contract=self.contract_submission_reminder, status='Register')
        self.overview = CourseOverview.get_from_id(self.course.id)
        self.overview.extra.is_status_managed = True
        self.overview.extra.save()

        param = self._create_reminder_search_param(student_status='Not Enrolled', is_status_managed=True)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course, current_manager=director_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 1)
        show_list = json.loads(data['show_list'])
        self._assert_search_result_base(
            result=show_list[0], recid=1, user=user1, profile=user1.profile, status='During registration',
            student_status='Not Enrolled', is_score=False, is_playback=False, is_status_managed=True
        )

    def test_reminder_search_ajax_status_unenrolled(self):
        self.setup_user()
        director_manager = self._director_manager
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')
        # Search target user
        user1 = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course.id)
        enrollment = CourseEnrollmentFactory.create(user=user1, course_id=self.course.id, is_active=False)
        enrollment.deactivate()
        ContractRegisterFactory.create(user=user1, contract=self.contract_submission_reminder, status='Register')
        self.overview = CourseOverview.get_from_id(self.course.id)
        self.overview.extra.is_status_managed = True
        self.overview.extra.save()

        param = self._create_reminder_search_param(is_status_managed=True)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course, current_manager=director_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 0)

    def test_reminder_search_ajax_status_disabled(self):
        self.setup_user()
        director_manager = self._director_manager
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')
        user1 = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course.id)
        UserStandingFactory.create(user=user1, account_status=UserStanding.ACCOUNT_DISABLED, changed_by=user1)
        CourseEnrollmentFactory.create(user=user1, course_id=self.course.id, is_active=False)
        ContractRegisterFactory.create(user=user1, contract=self.contract_submission_reminder, status='Register')
        self.overview = CourseOverview.get_from_id(self.course.id)
        self.overview.extra.is_status_managed = True
        self.overview.extra.save()

        param = self._create_reminder_search_param(is_status_managed=True)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course, current_manager=director_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 0)

    def test_reminder_search_ajax_status_expired(self):
        self.setup_user()
        director_manager = self._director_manager
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')
        user1 = UserFactory.create()
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course.id)
        CourseEnrollmentFactory.create(user=user1, course_id=self.course.id, is_active=False)
        ContractRegisterFactory.create(user=user1, contract=self.contract_submission_reminder, status='Register')
        self.course.created = datetime(year=2000, month=1, day=1)
        self.course.save()
        self.overview = CourseOverview.get_from_id(self.course.id)
        self.overview.extra.is_status_managed = True
        self.overview.extra.save()
        self._create_score_batch_status(course=self.course)
        self._create_achievement_score_column()
        self._create_achievement_score_data(user1.username, user1.email, course=self.course,
                                            status='Expired')

        param = self._create_reminder_search_param(is_status_managed=True)

        with self.skip_check_course_selection(
                current_organization=self.contract_org, current_contract=self.contract_submission_reminder,
                current_course=self.course, current_manager=director_manager), patch(
            'biz.djangoapps.ga_contract_operation.views.self_paced_api.is_course_closed') as mock_validate_task:
            mock_validate_task.return_value = True
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, 0)

    @ddt.unpack
    @ddt.data(('G01-01', 3), ('G01-01-01', 1), ('G02', 5))
    def test_reminder_search_ajax_manager_rights(self, group_code, expect):
        self.setup_user()
        manager_manager = self._manager_manager
        GroupUtil(org=self.contract_org, user=self.user).import_data()
        group = Group.objects.get(org=self.contract_org, group_code=group_code)
        RightFactory.create(org=self.contract_org, group=group, user=manager_manager.user, created_by=self.user,
                            creator_org=self.contract_org)
        ContractDetailFactory.create(contract=self.contract_submission_reminder, course_id=self.course_spoc1.id)
        for i, group in enumerate(Group.objects.filter(org=self.contract_org)):
            user = UserFactory.create()
            CourseEnrollmentFactory.create(user=user, course_id=self.course_spoc1.id)
            ContractRegisterFactory.create(user=user, contract=self.contract_submission_reminder, status='Register')
            self._create_member(org=self.contract_org, group=group, code='code' + str(i), user=user)

        param = self._create_reminder_search_param()

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=manager_manager):
            response = self.client.post(self._url_search_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self._assert_search_ajax_successful(data, expect)

    # ------------------------------------------------------------
    # Search Reminder Mail
    # ------------------------------------------------------------
    @property
    def _url_search_send_ajax(self):
        return reverse('biz:contract_operation:reminder_search_mail_send_ajax')

    def _create_reminder_search_send_param(self, emails, subject, body, contract=None, is_test=False):
        return {
            'contract_id': contract.id if contract else self.contract_submission_reminder.id,
            'is_test': 1 if is_test else 0,
            'search_user_emails': ','.join(emails),
            'mail_subject': subject,
            'mail_body': body,
        }

    def test_reminder_search_mail_send_ajax(self):
        self.setup_user()
        director_manager = self._director_manager
        user1 = UserFactory.create()
        enrollment = CourseEnrollmentFactory.create(user=user1, course_id=self.course_self_paced1.id)
        subject = "subject {username},{email_address},{fullname},{course_name},{expire_date}"
        body = "body {username},{email_address},{fullname},{course_name},{expire_date}"
        param = self._create_reminder_search_send_param(
            emails=[user1.email], subject=subject, body=body)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_self_paced1,
                                              current_manager=director_manager), patch(
                'biz.djangoapps.ga_contract_operation.views.send_mail') as send_mail:
            response = self.client.post(self._url_search_send_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        # self.assertEqual(data['info'], 'Complete of send the e-mail.')
        self.assertEqual(data['info'], 'Began the processing of Reminder Bulk Email.Execution status, please check from the task history.')
        # self.assertEqual(json.loads(data['error_messages']), [])
        # send_mail.assert_called_with(user1, subject, body.encode('utf-8'), {
        #     'username': user1.username,
        #     'email_address': user1.email,
        #     'fullname': user1.profile.name,
        #     'course_name': self.course_self_paced1.display_name,
        #     'expire_date': datetime(2016, 1, 5, 0, 0, 0, tzinfo=tzutc()).strftime("%Y-%m-%d"),
        # })

    @ddt.data(True, False)
    def test_reminder_search_mail_send_ajax_test(self, exist_profile):
        self.setup_user()
        director_manager = self._director_manager
        subject = "subject {username},{email_address},{fullname},{course_name},{expire_date}"
        body = "body {username},{email_address},{fullname},{course_name},{expire_date}"
        param = self._create_reminder_search_send_param(
            emails=[], subject=subject, body=body, is_test=True)
        profile = UserProfile.objects.get(user=self.user)
        if not exist_profile:
            profile.delete()

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_self_paced1,
                                              current_manager=director_manager), patch(
                'biz.djangoapps.ga_contract_operation.views.send_mail') as send_mail:
            response = self.client.post(self._url_search_send_ajax, param)
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['info'], 'Complete of send the e-mail.')
        self.assertEqual(json.loads(data['error_messages']), [])
        send_mail.assert_called_with(self.user, subject, body.encode('utf-8'), {
            'username': self.user.username,
            'email_address': self.user.email,
            'fullname': profile.name if exist_profile else '',
            'course_name': self.course_self_paced1.display_name,
            'expire_date': datetime(2016, 1, 5, 0, 0, 0, tzinfo=tzutc()).strftime("%Y-%m-%d"),
        })

    def test_reminder_search_mail_send_ajax_authorized_error(self):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_reminder_search_send_param(emails=[], subject='Sample', body='Sample')
        param.pop('contract_id')

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            response = self.client.post(self._url_search_send_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Unauthorized access.")

    def test_reminder_search_mail_send_ajax_unmatch_contract(self):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_reminder_search_send_param(emails=[], subject='Sample', body='Sample')
        param['contract_id'] = 999

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            response = self.client.post(self._url_search_send_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Current contract is changed. Please reload this page.")

    def test_reminder_search_mail_send_ajax_empty_selected_email(self):
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_reminder_search_send_param(emails=[], subject='Sample', body='Sample')

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            response = self.client.post(self._url_search_send_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Please select user that you want send reminder mail.")

    def test_reminder_search_mail_send_ajax_not_exist_email_selected(self):
        from biz.djangoapps.ga_contract_operation.models import (
            ContractMail, ContractReminderMail,
            ContractTaskHistory, ContractTaskTarget, StudentRegisterTaskTarget,
            StudentUnregisterTaskTarget, AdditionalInfoUpdateTaskTarget, StudentMemberRegisterTaskTarget,
            ReminderMailTaskHistory, ReminderMailTaskTarget
        )
        self.setup_user()
        director_manager = self._director_manager
        param = self._create_reminder_search_send_param(emails=['sample@example.com'], subject='Sample', body='Sample')

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            with patch('biz.djangoapps.ga_contract_operation.views.send_mail'):
                response = self.client.post(self._url_search_send_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        # self.assertEqual(data['info'], 'Complete of send the e-mail.')
        self.assertEqual(data['info'], 'Began the processing of Reminder Bulk Email.Execution status, please check from the task history.')
        self.assertEqual(ReminderMailTaskTarget.objects.all()[0].student_email, u'sample@example.com,,,sample@example.com:Not found selected user.')
        # self.assertEqual(json.loads(data['error_messages']),
        #                  ['{0}:Not found selected user.'.format('sample@example.com')])

    def test_reminder_search_mail_send_ajax_empty_mail_subject(self):
        self.setup_user()
        director_manager = self._director_manager
        user1 = UserFactory.create()
        param = self._create_reminder_search_send_param(emails=[user1.email], subject='', body='Sample')

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            with patch('biz.djangoapps.ga_contract_operation.views.send_mail'):
                response = self.client.post(self._url_search_send_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], "Please enter the subject of an e-mail.")

    def test_reminder_search_mail_send_ajax_over_max_length_mail_subject(self):
        self.setup_user()
        director_manager = self._director_manager
        user1 = UserFactory.create()
        max_length = ContractReminderMail._meta.get_field('mail_subject').max_length
        param = self._create_reminder_search_send_param(
            emails=[user1.email], subject=''.join(map(str, [num for num in range(max_length + 1)])), body='Sample')

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            with patch('biz.djangoapps.ga_contract_operation.views.send_mail'):
                response = self.client.post(self._url_search_send_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Subject within {0} characters.'.format(max_length))

    def test_reminder_search_mail_send_ajax_empty_mail_body(self):
        self.setup_user()
        director_manager = self._director_manager
        user1 = UserFactory.create()
        param = self._create_reminder_search_send_param(emails=[user1.email], subject='Sample', body='')

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1, current_manager=director_manager):
            with patch('biz.djangoapps.ga_contract_operation.views.send_mail'):
                response = self.client.post(self._url_search_send_ajax, param)

        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Please enter the body of an e-mail.')

    def test_reminder_search_mail_send_ajax_error_send_mail(self):
        self.setup_user()
        director_manager = self._director_manager
        user1 = UserFactory.create()
        param = self._create_reminder_search_send_param(emails=[user1.email], subject='Sample', body='Sample')

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_spoc1,
                                              current_manager=director_manager), patch(
            'biz.djangoapps.ga_contract_operation.views.send_mail', side_effect=Exception('test')), patch(
            'biz.djangoapps.ga_contract_operation.views.log.exception') as exception_log:
            response = self.client.post(self._url_search_send_ajax, param)

        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        # self.assertEqual(data['info'], 'Complete of send the e-mail.')
        self.assertEqual(data['info'], 'Began the processing of Reminder Bulk Email.Execution status, please check from the task history.')
        # exception_log.assert_called_with('Failed to send the e-mail.test')
        # self.assertEqual(json.loads(data['error_messages']), ['{0}:Failed to send the e-mail.'.format(user1.email)])

    @freeze_time('2005-01-01 21:00:00')
    def test_reminder_send_button_disbled(self):
        self.setup_user()
        director_manager = self._director_manager
        subject = "subject {username},{email_address},{fullname},{course_name},{expire_date}"
        body = "body {username},{email_address},{fullname},{course_name},{expire_date}"
        param = self._create_reminder_search_send_param(
            emails=[], subject=subject, body=body, is_test=True)
        profile = UserProfile.objects.get(user=self.user)

        with self.skip_check_course_selection(current_organization=self.contract_org,
                                              current_contract=self.contract_submission_reminder,
                                              current_course=self.course_self_paced1,
                                              current_manager=director_manager), patch(
            'biz.djangoapps.ga_contract_operation.views.send_mail') as send_mail:
            response = self.client.post(self._url_search_send_ajax, param)
        self.assertEqual(400, response.status_code)
        data = json.loads(response.content)
        # self.assertEqual(data['error'], 'Please enter the body of an e-mail.')

# -*- coding: utf-8 -*-
import copy
from django.db.models.loading import get_model

from django.utils.translation import ugettext as _

## test base
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from biz.djangoapps.util.tests.testcase import BizViewTestBase, BizStoreTestBase

## models
from django.contrib.auth.models import User
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_org_group.models import Group
from biz.djangoapps.ga_contract.models import Contract, ContractDetail
from biz.djangoapps.ga_invitation.models import ContractRegister
from student.models import CourseEnrollment
from biz.djangoapps.ga_login.models import BizUser
from student.models import UserProfile
from ga_survey.models import SurveySubmission

## factories class
from xmodule.modulestore.tests.factories import CourseFactory
from student.tests.factories import UserFactory
from student.tests.factories import CourseEnrollmentFactory
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from ga_survey.tests.factories import SurveySubmissionFactory

## target views
from biz.djangoapps.ga_course_anslist import views as view
from biz.djangoapps.ga_course_anslist import helpers as helper

import logging
log = logging.getLogger(__name__)

CONST_REGISTER_INVITATION_CODE = 'Register'

class SurveyDbTest(BizViewTestBase, ModuleStoreTestCase, BizStoreTestBase):

    def setUp(self):
        super(BizViewTestBase, self).setUp()

        ## organization
        self.org100 = self._create_organization(org_name='gacco100', org_code='gacco-100', creator_org=self.gacco_organization)
        self.org200 = self._create_organization(org_name='gacco200', org_code='gacco-200', creator_org=self.gacco_organization)

        ## course
        self.course10 = CourseFactory.create(org='gacco', number='course', run='run10')
        self.course20 = CourseFactory.create(org='gacco', number='course20', run='run20')
        self.course30 = CourseFactory.create(org='gacco', number='course30', run='run30')

        ## contract
        self.contract1 = self._create_contract(
                            contract_name='contract1', contractor_organization=self.org100,
                            detail_courses=[self.course10.id], additional_display_names=['country', 'dept'],
                            send_submission_reminder=True,
        )

        ## user
        self.user10 = UserFactory.create(username='na10000', email='nauser10000@example.com')
        self.user11 = UserFactory.create(username='na11000', email='nauser11000@example.com')
        self.user12 = UserFactory.create(username='na12000', email='nauser12000@example.com')
        self.user20 = UserFactory.create(username='na20000', email='nauser20000@example.com')
        self.user88 = UserFactory.create(username='na88000', email='nauser88000@example.com')
        self.user98 = UserFactory.create(username='na98000', email='nauser98000@example.com')
        self.user99 = UserFactory.create(username='na99000', email='nauser99000@example.com')

        ## enrollment
        self.enroll10 = CourseEnrollmentFactory.create(user=self.user10, course_id=self.course10.id)
        self.enroll11 = CourseEnrollmentFactory.create(user=self.user11, course_id=self.course10.id)
        self.enroll12 = CourseEnrollmentFactory.create(user=self.user12, course_id=self.course10.id)
        self.enroll88 = CourseEnrollmentFactory.create(user=self.user88, course_id=self.course10.id)
        self.enroll98 = CourseEnrollmentFactory.create(user=self.user98, course_id=self.course20.id)
        self.enroll99 = CourseEnrollmentFactory.create(user=self.user99, course_id=self.course20.id)

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
        self.group1110 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='1110', group_name='G1110', org=self.org100,
            created_by=self.user, modified_by=self.user)
        self.group2000 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='2000', group_name='H2000', org=self.org200,
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
        self.member12 = MemberFactory.create(
            org=self.org100,
            group=self.group1110,
            user=self.user12,
            code='0012',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org3='gacco11',
        )
        self.member20 = MemberFactory.create(
            org=self.org100,
            group=self.group1200,
            user=self.user20,
            code='0020',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org2='gacco11',
        )
        # self.member88 = MemberFactory.create(
        #     org=self.org200,
        #     group=self.group1200,
        #     user=self.user88,
        #     code='0088',
        #     created_by=self.user,
        #     creator_org=self.gacco_organization,
        #     updated_by=self.user,
        #     updated_org=self.gacco_organization,
        #     org1='gacco99',
        # )
        # self.member98 = MemberFactory.create(
        #     org=self.org200,
        #     group=self.group2000,
        #     user=self.user98,
        #     code='0098',
        #     created_by=self.user,
        #     creator_org=self.gacco_organization,
        #     updated_by=self.user,
        #     updated_org=self.gacco_organization,
        #     org1='gacco99',
        # )
        # member99 = MemberFactory.create(
        #     org=self.org200,
        #     group=self.group2000,
        #     user=self.user99,
        #     code='0099',
        #     created_by=self.user,
        #     creator_org=self.gacco_organization,
        #     updated_by=self.user,
        #     updated_org=self.gacco_organization,
        #     org1='gacco99',
        # )

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

        ### user88
        submission88_c10_survey1_data = {
            'course_id': self.course30.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user88,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission88_c10_survey1 = SurveySubmissionFactory.create(**submission88_c10_survey1_data)

        submission88_c30_survey2_data = {
            'course_id': self.course30.id,
            'unit_id': '22222222222222222222222222222222',
            'user': self.user88,
            'survey_name': 'survey2',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission88_c30_survey2 = SurveySubmissionFactory.create(**submission88_c30_survey2_data)

        # submission88_c10_survey3_data = {
        #     'course_id': self.course10.id,
        #     'unit_id': '33333333333333333333333333333333',
        #     'user': self.user88,
        #     'survey_name': 'survey3',
        #     'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        # }
        # self.submission88_c10_survey3 = SurveySubmissionFactory.create(**submission88_c10_survey3_data)
        #
        ### user99
        submission99_c20_survey100_data = {
            'course_id': self.course20.id,
            'unit_id': '11111111111111111111111111111100',
            'user': self.user99,
            'survey_name': 'survey100',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission99_c20_survey100 = SurveySubmissionFactory.create(**submission99_c20_survey100_data)

        submission99_c20_survey200_data = {
            'course_id': self.course20.id,
            'unit_id': '22222222222222222222222222222200',
            'user': self.user99,
            'survey_name': 'survey200',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission99_c20_survey200 = SurveySubmissionFactory.create(**submission99_c20_survey200_data)

    def test_get_survey_names_list_org100_c10(self):
        ## Arrange
        #org_id = self.org100.id
        course_id = self.course10.id
        expected_cnt = 2
        expected_0 = (self.submission10_c10_survey1.unit_id, self.submission10_c10_survey1.survey_name)
        expected_1 = (self.submission10_c10_survey2.unit_id, self.submission10_c10_survey2.survey_name)
        ## Act
        rows = view._get_survey_names_list(course_id)
        actual_cnt = len(rows)
        actual_0 = rows[0]
        actual_1 = rows[1]
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        self.assertEqual(expected_0, actual_0)
        self.assertEqual(expected_1, actual_1)

    # def test_get_survey_names_list_org100_c20(self):
    #     ## Arrange
    #     #org_id = self.org100.id
    #     course_id = self.course20.id
    #     expected_cnt = 0
    #     ## Act
    #     rows = view._get_survey_names_list(course_id)
    #     actual_cnt = len(rows)
    #     ## Assert
    #     self.assertEqual(expected_cnt, actual_cnt)
    #
    # def test_get_survey_names_list_org200_c10(self):
    #     ## Arrange
    #     #org_id = self.org200.id
    #     course_id = self.course10.id
    #     expected_cnt = 3
    #     expected_0 = (self.submission88_c10_survey1.unit_id, self.submission88_c10_survey1.survey_name)
    #     expected_1 = (self.submission88_c10_survey2.unit_id, self.submission88_c10_survey2.survey_name)
    #     expected_2 = (self.submission88_c10_survey3.unit_id, self.submission88_c10_survey3.survey_name)
    #     ## Act
    #     rows = view._get_survey_names_list(course_id)
    #     actual_cnt = len(rows)
    #     actual_0 = rows[0]
    #     actual_1 = rows[1]
    #     actual_2 = rows[2]
    #     ## Assert
    #     self.assertEqual(expected_cnt, actual_cnt)
    #     self.assertEqual(expected_0, actual_0)
    #     self.assertEqual(expected_1, actual_1)
    #     self.assertEqual(expected_2, actual_2)

    def test_get_survey_names_list_org200_c20(self):
        ## Arrange
        #org_id = self.org200.id
        course_id = self.course20.id
        expected_cnt = 2
        ## Act
        rows = view._get_survey_names_list(course_id)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_course_members_c10_base(self):
        ## Arrange
        user_ids = [self.user10.id, self.user11.id, self.user12.id]
        course_id = self.course10.id
        expected_cnt = 3
        ## Act
        rows = view._get_course_members(user_ids, course_id)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_course_members_c10_not_in(self):
        ## Arrange
        user_ids = [self.user10.id, self.user20.id]
        course_id = self.course10.id
        expected_cnt = 1
        ## Act
        rows = view._get_course_members(user_ids, course_id)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_course_members_c20_not_in(self):
        ## Arrange
        user_ids = [self.user10.id, self.user20.id]
        course_id = self.course20.id
        expected_cnt = 0
        ## Act
        rows = view._get_course_members(user_ids, course_id)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)


    def test_get_surveysubmission_c10_u10(self):
        ## Arrange
        user_ids = [self.user10.id]
        course_id = self.course10.id
        expected_cnt = 2
        ## Act
        rows = view._get_surveysubmission(user_ids, course_id)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_surveysubmission_c10_u10_11(self):
        ## Arrange
        user_ids = [self.user10.id, self.user11.id]
        course_id = self.course10.id
        expected_cnt = 3
        ## Act
        rows = view._get_surveysubmission(user_ids, course_id)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_surveysubmission_c10_u10_12(self):
        ## Arrange
        user_ids = [self.user10.id, self.user11.id, self.user12.id]
        course_id = self.course10.id
        expected_cnt = 3
        ## Act
        rows = view._get_surveysubmission(user_ids, course_id)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_surveysubmission_c20_u10_12(self):
        ## Arrange
        user_ids = [self.user10.id, self.user11.id, self.user12.id]
        course_id = self.course20.id
        expected_cnt = 0
        ## Act
        rows = view._get_surveysubmission(user_ids, course_id)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_members_g1000_1100_1200(self):
        ## Arrange
        org_id = self.org100.id
        group_ids = [self.group1000.id, self.group1100.id, self.group1200.id]
        expected_cnt = 3
        ## Act
        rows = view._get_members(org_id, group_ids)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_members_g1000_1100(self):
        ## Arrange
        org_id = self.org100.id
        group_ids = [self.group1000.id, self.group1100.id]
        expected_cnt = 2
        ## Act
        rows = view._get_members(org_id, group_ids)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_members_g1000(self):
        ## Arrange
        org_id = self.org100.id
        group_ids = [self.group1000.id]
        expected_cnt = 1
        ## Act
        rows = view._get_members(org_id, group_ids)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_members_g1200(self):
        ## Arrange
        org_id = self.org100.id
        group_ids = [self.group1200.id]
        expected_cnt = 1
        ## Act
        rows = view._get_members(org_id, group_ids)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_members_g1000_org200(self):
        ## Arrange
        org_id = self.org200.id
        group_ids = [self.group1000.id]
        expected_cnt = 0
        ## Act
        rows = view._get_members(org_id, group_ids)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_members_g1000_1100_1200_cond_org1_gacco1(self):
        ## Arrange
        org_id = self.org100.id
        group_ids = [self.group1000.id, self.group1100.id, self.group1200.id]
        conditions = [{'field':[u'org1'] , 'value':u'gacco1'}]
        expected_cnt = 2
        ## Act
        rows = view._get_members(org_id, group_ids, conditions)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_members_g1000_1100_1200_cond_org1_gacco2(self):
        ## Arrange
        org_id = self.org100.id
        group_ids = [self.group1000.id, self.group1100.id, self.group1200.id]
        conditions = [{'field':[u'org1'] , 'value':u'gacco2'}]
        expected_cnt = 1
        ## Act
        rows = view._get_members(org_id, group_ids, conditions)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_members_g1000_1100_1200_cond_org2_gacco11(self):
        ## Arrange
        org_id = self.org100.id
        group_ids = [self.group1000.id, self.group1100.id, self.group1200.id]
        conditions = [{'field':[u'org2'] , 'value':u'gacco11'}]
        expected_cnt = 2
        ## Act
        rows = view._get_members(org_id, group_ids, conditions)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def test_get_members_g1000_1100_1200_cond_org1_gacco1_org2_gacco11(self):
        ## Arrange
        org_id = self.org100.id
        group_ids = [self.group1000.id, self.group1100.id, self.group1200.id]
        conditions = [{'field':[u'org1'] , 'value':u'gacco1'}, {'field':[u'org2'] , 'value':u'gacco11'}]
        expected_cnt = 1
        ## Act
        rows = view._get_members(org_id, group_ids, conditions)
        actual_cnt = len(rows)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)

    def _populate_dct(self, user, member, group):
        profile = UserProfile.objects.get(user=user)
        try:
            bizuser = BizUser.objects.get(user=user)
        except BizUser.DoesNotExist:
            bizuser = None

        ret_dct = {
            'id': user.id,
            'Member Code': member.code,
            'Username': user.username,
            'Email': user.email,
            'Full Name': profile.name if profile else None,
            'Login Code': bizuser.login_code if bizuser else None,
            'Organization1': member.org1,
            'Organization2': member.org2,
            'Organization3': member.org3,
            'Organization4': member.org4,
            'Organization5': member.org5,
            'Organization6': member.org6,
            'Organization7': member.org7,
            'Organization8': member.org8,
            'Organization9': member.org9,
            'Organization10': member.org10,
            'Item1': member.item1,
            'Item2': member.item2,
            'Item3': member.item3,
            'Item4': member.item4,
            'Item5': member.item5,
            'Item6': member.item6,
            'Item7': member.item7,
            'Item8': member.item8,
            'Item9': member.item9,
            'Item10': member.item10,
            'Organization Name': group.group_name,
            'Group Code': group.group_code,
        }
        ret_dct.update({'obj' : copy.deepcopy(ret_dct)})

        return ret_dct


    def test_populate_members(self):
        ## Arrange
        org_id = self.org100.id
        expected_cnt = 4
        user_id_1 = self.user10.id
        expected_dct_1 = self._populate_dct(self.user10, self.member10, self.group1000)
        user_id_2 = self.user11.id
        expected_dct_2 = self._populate_dct(self.user11, self.member11, self.group1100)
        user_id_3 = self.user12.id
        expected_dct_3 = self._populate_dct(self.user12, self.member12, self.group1110)
        user_id_4 = self.user20.id
        expected_dct_4 = self._populate_dct(self.user20, self.member20, self.group1200)

        ## Act
        results = Member.find_active_by_org(org=org_id).select_related(
            'group', 'user', 'user__bizuser', 'user__profile').values(*[
            'code', 'org1', 'org2', 'org3', 'org4', 'org5', 'org6', 'org7', 'org8', 'org9', 'org10',
            'item1', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7', 'item8', 'item9', 'item10',
            'user__id', 'user__username', 'user__email', 'user__profile__name', 'user__bizuser__login_code',
            'group__group_name', 'group__group_code'
        ])

        for res in results:
            log.debug(res['user__id'])
            log.debug(res['user__username'])

        actual_cnt = len(results)
        ret = view._populate_members(results)
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        actual_dct_1 = ret[user_id_1]
        self.assertEqual(expected_dct_1['id'], actual_dct_1['id'])
        self.assertEqual(expected_dct_1['Member Code'], actual_dct_1[_('Member Code')])
        self.assertEqual(expected_dct_1['Username'], actual_dct_1[_('Username')])
        self.assertEqual(expected_dct_1['Email'], actual_dct_1[_('Email')])
        self.assertEqual(expected_dct_1['Full Name'], actual_dct_1[_('Full Name')])
        self.assertEqual(expected_dct_1['Login Code'], actual_dct_1[_('Login Code')])
        self.assertEqual(expected_dct_1['Organization1'], actual_dct_1[_('Organization') + '1'])
        self.assertEqual(expected_dct_1['Organization2'], actual_dct_1[_('Organization') + '2'])
        self.assertEqual(expected_dct_1['Organization3'], actual_dct_1[_('Organization') + '3'])
        self.assertEqual(expected_dct_1['Organization4'], actual_dct_1[_('Organization') + '4'])
        self.assertEqual(expected_dct_1['Organization5'], actual_dct_1[_('Organization') + '5'])
        self.assertEqual(expected_dct_1['Organization6'], actual_dct_1[_('Organization') + '6'])
        self.assertEqual(expected_dct_1['Organization7'], actual_dct_1[_('Organization') + '7'])
        self.assertEqual(expected_dct_1['Organization8'], actual_dct_1[_('Organization') + '8'])
        self.assertEqual(expected_dct_1['Organization9'], actual_dct_1[_('Organization') + '9'])
        self.assertEqual(expected_dct_1['Organization10'], actual_dct_1[_('Organization') + '10'])
        self.assertEqual(expected_dct_1['Item1'], actual_dct_1[_('Item') + '1'])
        self.assertEqual(expected_dct_1['Item2'], actual_dct_1[_('Item') + '2'])
        self.assertEqual(expected_dct_1['Item3'], actual_dct_1[_('Item') + '3'])
        self.assertEqual(expected_dct_1['Item4'], actual_dct_1[_('Item') + '4'])
        self.assertEqual(expected_dct_1['Item5'], actual_dct_1[_('Item') + '5'])
        self.assertEqual(expected_dct_1['Item6'], actual_dct_1[_('Item') + '6'])
        self.assertEqual(expected_dct_1['Item7'], actual_dct_1[_('Item') + '7'])
        self.assertEqual(expected_dct_1['Item8'], actual_dct_1[_('Item') + '8'])
        self.assertEqual(expected_dct_1['Item9'], actual_dct_1[_('Item') + '9'])
        self.assertEqual(expected_dct_1['Item10'], actual_dct_1[_('Item') + '10'])
        self.assertEqual(expected_dct_1['Organization Name'], actual_dct_1[_('Organization Name')])
        self.assertEqual(expected_dct_1['Group Code'], actual_dct_1[_('Group Code')])

        actual_dct_2 = ret[user_id_2]
        self.assertEqual(expected_dct_2['Member Code'], actual_dct_2[_('Member Code')])
        actual_dct_3 = ret[user_id_3]
        self.assertEqual(expected_dct_3['Username'], actual_dct_3[_('Username')])
        actual_dct_4 = ret[user_id_4]
        self.assertEqual(expected_dct_4['Group Code'], actual_dct_4[_('Group Code')])

    def test_retrieve_grid_data_o100_g1100_1110_c10_no_member_condition(self):
        org_id = self.org100.id
        child_group_ids = [self.group1100.id, self.group1110.id]
        contract_id = self.contract1
        course_id = self.course10.id
        is_filter = 'on'
        members_conditions = []
        expected_cnt = 2
        ## Act
        results = view._retrieve_grid_data(org_id, child_group_ids, contract_id, course_id, is_filter)
        actual_cnt = len(results)
        self.assertEqual(expected_cnt, actual_cnt)

    def test_retrieve_grid_data_o100_g1100_c10_no_member_condition(self):
        org_id = self.org100.id
        child_group_ids = [self.group1110.id]
        contract_id = self.contract1
        course_id = self.course10.id
        is_filter = 'on'
        members_conditions = []
        expected_cnt = 1
        ## Act
        results = view._retrieve_grid_data(org_id, child_group_ids, contract_id, course_id, is_filter)
        actual_cnt = len(results)
        self.assertEqual(expected_cnt, actual_cnt)


class SurveyDbTestBase(BizViewTestBase, ModuleStoreTestCase, BizStoreTestBase):
    def setUp(self):
        super(BizViewTestBase, self).setUp()

        ## organization
        self.org100 = self._create_organization(org_name='gacco100', org_code='gacco-100', creator_org=self.gacco_organization)
        self.org200 = self._create_organization(org_name='gacco200', org_code='gacco-200', creator_org=self.gacco_organization)

        ## course
        self.course10 = CourseFactory.create(org='gacco', number='course10', run='run10')
        self.course11 = CourseFactory.create(org='gacco', number='course11', run='run11')
        self.course20 = CourseFactory.create(org='gacco', number='course20', run='run20')
        self.course30 = CourseFactory.create(org='gacco', number='course30', run='run30')

        ## contract
        self.contract1 = self._create_contract(
                            contract_name='contract1', contractor_organization=self.org100,
                            detail_courses=[self.course10.id, self.course11.id], additional_display_names=['country', 'dept'],
                            send_submission_reminder=True,
        )
        self.contract2 = self._create_contract(
                            contract_name='contract2', contractor_organization=self.org200,
                            detail_courses=[self.course20.id], additional_display_names=['country', 'dept'],
                            send_submission_reminder=True,
        )

        ## user
        self.user10 = UserFactory.create(username='na10000', email='nauser10000@example.com')
        self.user11 = UserFactory.create(username='na11000', email='nauser11000@example.com')
        self.user12 = UserFactory.create(username='na12000', email='nauser12000@example.com')
        self.user19 = UserFactory.create(username='na19000', email='nauser19000@example.com')
        self.user20 = UserFactory.create(username='na20000', email='nauser20000@example.com')
        self.user50 = UserFactory.create(username='na50000', email='nauser50000@example.com')
        self.user51 = UserFactory.create(username='na51000', email='nauser51000@example.com')
        self.user60 = UserFactory.create(username='na60000', email='nauser60000@example.com')
        self.user70 = UserFactory.create(username='na70000', email='nauser70000@example.com')
        self.user75 = UserFactory.create(username='na75000', email='nauser75000@example.com')
        self.user79 = UserFactory.create(username='na79000', email='nauser79000@example.com')
        self.user80 = UserFactory.create(username='na80000', email='nauser80000@example.com')
        self.user85 = UserFactory.create(username='na85000', email='nauser85000@example.com')
        self.user89 = UserFactory.create(username='na89000', email='nauser89000@example.com')
        self.user90 = UserFactory.create(username='na90000', email='nauser90000@example.com')
        self.user95 = UserFactory.create(username='na95000', email='nauser95000@example.com')

        ## enrollment
        ### user30, user70, user80 are not enrolled
        self.enro10_c10 = CourseEnrollmentFactory.create(user=self.user10, course_id=self.course10.id)
        self.enro10_c11 = CourseEnrollmentFactory.create(user=self.user10, course_id=self.course11.id)
        self.enro11_c10 = CourseEnrollmentFactory.create(user=self.user11, course_id=self.course10.id)
        self.enro12_c10 = CourseEnrollmentFactory.create(user=self.user12, course_id=self.course10.id)
        self.enro20_c11 = CourseEnrollmentFactory.create(user=self.user20, course_id=self.course11.id)
        self.enro50_c10 = CourseEnrollmentFactory.create(user=self.user50, course_id=self.course10.id)
        self.enro50_c11 = CourseEnrollmentFactory.create(user=self.user50, course_id=self.course11.id)
        self.enro51_c10 = CourseEnrollmentFactory.create(user=self.user51, course_id=self.course10.id)
        self.enro60_c11 = CourseEnrollmentFactory.create(user=self.user60, course_id=self.course11.id)
        self.enro70_c20 = CourseEnrollmentFactory.create(user=self.user70, course_id=self.course20.id)
        self.enro75_c20 = CourseEnrollmentFactory.create(user=self.user75, course_id=self.course20.id)
        self.enro80_c20 = CourseEnrollmentFactory.create(user=self.user80, course_id=self.course20.id)
        self.enro85_c10 = CourseEnrollmentFactory.create(user=self.user85, course_id=self.course10.id)
        self.enro90_c30 = CourseEnrollmentFactory.create(user=self.user90, course_id=self.course30.id)
        self.enro95_c10 = CourseEnrollmentFactory.create(user=self.user95, course_id=self.course10.id)

        ## contract register for member
        self.reg10_c1 = ContractRegisterFactory.create(user=self.user10, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg11_c1 = ContractRegisterFactory.create(user=self.user11, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg12_c1 = ContractRegisterFactory.create(user=self.user12, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg20_c1 = ContractRegisterFactory.create(user=self.user20, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg50_c1 = ContractRegisterFactory.create(user=self.user50, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg51_c1 = ContractRegisterFactory.create(user=self.user51, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg60_c1 = ContractRegisterFactory.create(user=self.user60, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg70_c2 = ContractRegisterFactory.create(user=self.user70, contract=self.contract2, status=CONST_REGISTER_INVITATION_CODE)
        self.reg75_c2 = ContractRegisterFactory.create(user=self.user75, contract=self.contract2, status=CONST_REGISTER_INVITATION_CODE)
        self.reg80_c2 = ContractRegisterFactory.create(user=self.user80, contract=self.contract2, status=CONST_REGISTER_INVITATION_CODE)
        #self.reg85_c1 = ContractRegisterFactory.create(user=self.user85, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)

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
        self.group1110 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='1110', group_name='G1110', org=self.org100,
            created_by=self.user, modified_by=self.user)
        self.group2000 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='2000', group_name='H2000', org=self.org200,
            created_by=self.user, modified_by=self.user)
        self.group2005 = GroupFactory.create(
            parent_id=0, level_no=0, group_code='1110', group_name='G1110', org=self.org200,
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
        self.member12 = MemberFactory.create(
            org=self.org100,
            group=self.group1110,
            user=self.user12,
            code='0012',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org3='gacco11',
        )
        self.member19 = MemberFactory.create(
            org=self.org100,
            group=self.group1110,
            user=self.user19,
            code='0019',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org3='gacco11',
        )
        self.member20 = MemberFactory.create(
            org=self.org100,
            group=self.group1000,
            user=self.user20,
            code='0020',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org2='gacco11',
        )
        self.member70 = MemberFactory.create(
            org=self.org200,
            group=self.group2000,
            user=self.user70,
            code='0070',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org2='gacco11',
        )
        self.member75 = MemberFactory.create(
            org=self.org200,
            group=self.group1110,
            user=self.user75,
            code='0075',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org2='gacco11',
        )
        self.member79 = MemberFactory.create(
            org=self.org200,
            group=self.group2000,
            user=self.user79,
            code='0079',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco99',
        )

        ## Survey Submission
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

        submission10_c11_survey1_data = {
            'course_id': self.course11.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user10,
            'survey_name': 'survey c11',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission10_c11_survey1 = SurveySubmissionFactory.create(**submission10_c11_survey1_data)

        ### user11
        submission11_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user11,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission11_c10_survey1 = SurveySubmissionFactory.create(**submission11_c10_survey1_data)

        ### user20
        submission20_c11_survey1_data = {
            'course_id': self.course11.id,
            'unit_id': 'c11b1111111111111111111111111111',
            'user': self.user20,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission20_c11_survey1 = SurveySubmissionFactory.create(**submission20_c11_survey1_data)

        ### user50
        submission50_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user50,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission50_c10_survey1 = SurveySubmissionFactory.create(**submission50_c10_survey1_data)

        submission50_c11_survey1_data = {
            'course_id': self.course11.id,
            'unit_id': 'c11b1111111111111111111111111111',
            'user': self.user50,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission50_c11_survey1 = SurveySubmissionFactory.create(**submission50_c11_survey1_data)

        ### user51
        submission51_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user51,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission51_c10_survey1 = SurveySubmissionFactory.create(**submission51_c10_survey1_data)

        ### user60
        submission60_c11_survey1_data = {
            'course_id': self.course11.id,
            'unit_id': 'c11b1111111111111111111111111111',
            'user': self.user60,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission60_c11_survey1 = SurveySubmissionFactory.create(**submission60_c11_survey1_data)

        ### user70
        submission70_c20_survey1_data = {
            'course_id': self.course20.id,
            'unit_id': 'c20b1111111111111111111111111111',
            'user': self.user70,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission70_c20_survey1 = SurveySubmissionFactory.create(**submission70_c20_survey1_data)

        ### user75
        submission75_c20_survey1_data = {
            'course_id': self.course20.id,
            'unit_id': 'c20b1111111111111111111111111111',
            'user': self.user75,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission75_c20_survey1 = SurveySubmissionFactory.create(**submission75_c20_survey1_data)

        ### user80
        submission80_c20_survey1_data = {
            'course_id': self.course20.id,
            'unit_id': 'c20b1111111111111111111111111111',
            'user': self.user80,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission80_c20_survey1 = SurveySubmissionFactory.create(**submission80_c20_survey1_data)

        ### user85
        submission85_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user85,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission85_c10_survey1 = SurveySubmissionFactory.create(**submission85_c10_survey1_data)

        ### user90
        submission90_c30_survey1_data = {
            'course_id': self.course30.id,
            'unit_id': 'c30b1111111111111111111111111111',
            'user': self.user90,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission90_c30_survey1 = SurveySubmissionFactory.create(**submission90_c30_survey1_data)

        ### user95
        submission95_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user95,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission95_c10_survey1 = SurveySubmissionFactory.create(**submission95_c10_survey1_data)

    def _dump_list(self, rows):
        for r in rows:
            log.debug(r)

    def _convert_to_list(self, qs):
        model = qs.model
        headers = []
        rows = []
        for field in model._meta.fields:
            headers.append(field.name)

        for obj in qs:
            row = []
            for field in headers:
                val = getattr(obj, field)
                if callable(val):
                    val = val()
                if type(val) == unicode:
                    val = val.encode("utf-8")
                row.append(val)

            rows.append(copy.deepcopy(row))
            del row

        return [headers] + rows

    # # test data dump dummy function
    # def test_dump_data(self):
    #     ## dump all orgs
    #     organizations_all = Organization.objects.all()
    #     data = self._convert_to_list(organizations_all)
    #     self._dump_list(data)
    #     ## dump all contracts
    #     contracts_all = Contract.objects.all()
    #     data = self._convert_to_list(contracts_all)
    #     self._dump_list(data)
    #     ## dump all contract details
    #     contractdetails_all = ContractDetail.objects.all()
    #     data = self._convert_to_list(contractdetails_all)
    #     self._dump_list(data)
    #     ## dump all users
    #     users_all = User.objects.all()
    #     data = self._convert_to_list(users_all)
    #     self._dump_list(data)
    #     ## dump all entrollments
    #     contractregisters_all = ContractRegister.objects.all()
    #     data = self._convert_to_list(contractregisters_all)
    #     self._dump_list(data)
    #     ## dump all entrollments
    #     enrollments_all = CourseEnrollment.objects.all()
    #     data = self._convert_to_list(enrollments_all)
    #     self._dump_list(data)
    #     ## dump all submissions
    #     submissions_all = SurveySubmission.objects.all()
    #     data = self._convert_to_list(submissions_all)
    #     self._dump_list(data)
    #     ## dump all members
    #     members_all = Member.objects.all()
    #     data = self._convert_to_list(members_all)
    #     self._dump_list(data)
    #     ## dump all groups
    #     groups_all = Group.objects.all()
    #     data = self._convert_to_list(groups_all)
    #     self._dump_list(data)
    #
    #     self.assertTrue(False)


class SurveyDbAddTest(SurveyDbTestBase):

    def _populate_dct(self, user):

        profile = UserProfile.objects.get(user=user)
        try:
            bizuser = BizUser.objects.get(user=user)
        except BizUser.DoesNotExist:
            bizuser = None

        ret_dct = {
            'id': user.id,
            'Username': user.username,
            'Email': user.email,
            'Full Name': profile.name if profile else None,
            'Login Code': bizuser.login_code if bizuser else None,
            'Group Code': '',
            'Member Code': '',
        }
        ret_dct.update({'obj': copy.deepcopy(ret_dct)})

        return ret_dct

    def test_get_users_not_member_o100_c10(self):
        org_id = self.org100.id
        contract_id = self.contract1.id
        course_id = self.course10.id
        user_ids_of_members = [self.user10.id, self.user11.id, self.user12.id, self.user19.id, self.user20.id]
        expected_cnt = 2
        expected_user_id = self.user50.id
        ## Act
        results = view._get_users_not_member(org_id, contract_id, course_id, user_ids_of_members)
        log.debug('results={}'.format(results))
        log.debug('results_len={}'.format(len(results)))
        actual_cnt = len(results)
        actual_user_id = results[self.user50.id]['id']
        self.assertEqual(expected_cnt, actual_cnt)
        self.assertEqual(expected_user_id, actual_user_id)


    def test_populate_users_not_members_o100_c10(self):
        ## Arrange
        org_id = self.org100.id
        contract_id = self.contract1.id
        course_id = self.course10.id
        user_ids_of_members = [self.user10.id, self.user11.id, self.user12.id, self.user19.id, self.user20.id]
        expected_cnt = 2
        expected_dct = self._populate_dct(self.user50)

        ## Act
        sql_statement = helper._create_users_not_members_statement(org_id, contract_id, course_id, user_ids_of_members)
        results = SurveySubmission.objects.raw(sql_statement)

        ret = view._populate_users_not_members(results)
        actual_cnt = len(ret)
        log.debug(ret)
        actual_cnt = len(ret)

        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        actual_dct = ret[self.user50.id]
        #self.assertEqual(expected_dct, actual_dct)
        self.assertEqual(expected_dct['Username'], actual_dct[_('Username')])
        self.assertEqual(expected_dct['Email'], actual_dct[_('Email')])
        self.assertEqual(expected_dct['Full Name'], actual_dct[_('Full Name')])
        self.assertEqual(expected_dct['Login Code'], actual_dct[_('Login Code')])
        self.assertEqual(expected_dct['Group Code'], actual_dct[_('Group Code')])
        #self.assertTrue(False)

    def test_populate_users_no_members_o100_c10(self):
        org_id = self.org100.id
        contract_id = self.contract1.id
        course_id = self.course10.id
        user_ids_of_members = []
        expected_cnt = 5
        expected_dct = self._populate_dct(self.user50)

        ## Act
        sql_statement = helper._create_users_not_members_statement(org_id, contract_id, course_id, user_ids_of_members)
        results = SurveySubmission.objects.raw(sql_statement)

        ret = view._populate_users_not_members(results)
        log.debug(ret)
        actual_cnt = len(ret)

        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        actual_dct = ret[self.user50.id]
        self.assertEqual(expected_dct['Username'], actual_dct[_('Username')])
        #self.assertTrue(False)



class SurveyDbNoGroupTestBase(BizViewTestBase, ModuleStoreTestCase, BizStoreTestBase):
    def setUp(self):
        super(BizViewTestBase, self).setUp()

        ## organization
        self.org100 = self._create_organization(org_name='gacco100', org_code='gacco-100', creator_org=self.gacco_organization)
        self.org200 = self._create_organization(org_name='gacco200', org_code='gacco-200', creator_org=self.gacco_organization)

        ## course
        self.course10 = CourseFactory.create(org='gacco', number='course10', run='run10')
        self.course11 = CourseFactory.create(org='gacco', number='course11', run='run11')
        self.course20 = CourseFactory.create(org='gacco', number='course20', run='run20')
        self.course30 = CourseFactory.create(org='gacco', number='course30', run='run30')

        ## contract
        self.contract1 = self._create_contract(
                            contract_name='contract1', contractor_organization=self.org100,
                            detail_courses=[self.course10.id, self.course11.id], additional_display_names=['country', 'dept'],
                            send_submission_reminder=True,
        )
        self.contract2 = self._create_contract(
                            contract_name='contract2', contractor_organization=self.org200,
                            detail_courses=[self.course20.id], additional_display_names=['country', 'dept'],
                            send_submission_reminder=True,
        )

        ## user
        self.user10 = UserFactory.create(username='na10000', email='nauser10000@example.com')
        self.user11 = UserFactory.create(username='na11000', email='nauser11000@example.com')
        self.user12 = UserFactory.create(username='na12000', email='nauser12000@example.com')
        self.user19 = UserFactory.create(username='na19000', email='nauser19000@example.com')
        self.user20 = UserFactory.create(username='na20000', email='nauser20000@example.com')
        self.user50 = UserFactory.create(username='na50000', email='nauser50000@example.com')
        self.user51 = UserFactory.create(username='na51000', email='nauser51000@example.com')
        self.user60 = UserFactory.create(username='na60000', email='nauser60000@example.com')
        self.user70 = UserFactory.create(username='na70000', email='nauser70000@example.com')
        self.user75 = UserFactory.create(username='na75000', email='nauser75000@example.com')
        self.user79 = UserFactory.create(username='na79000', email='nauser79000@example.com')
        self.user80 = UserFactory.create(username='na80000', email='nauser80000@example.com')
        self.user85 = UserFactory.create(username='na85000', email='nauser85000@example.com')
        self.user89 = UserFactory.create(username='na89000', email='nauser89000@example.com')
        self.user90 = UserFactory.create(username='na90000', email='nauser90000@example.com')
        self.user95 = UserFactory.create(username='na95000', email='nauser95000@example.com')

        ## enrollment
        ### user30, user70, user80 are not enrolled
        self.enro10_c10 = CourseEnrollmentFactory.create(user=self.user10, course_id=self.course10.id)
        self.enro10_c11 = CourseEnrollmentFactory.create(user=self.user10, course_id=self.course11.id)
        self.enro11_c10 = CourseEnrollmentFactory.create(user=self.user11, course_id=self.course10.id)
        self.enro12_c10 = CourseEnrollmentFactory.create(user=self.user12, course_id=self.course10.id)
        self.enro20_c11 = CourseEnrollmentFactory.create(user=self.user20, course_id=self.course11.id)
        self.enro50_c10 = CourseEnrollmentFactory.create(user=self.user50, course_id=self.course10.id)
        self.enro50_c11 = CourseEnrollmentFactory.create(user=self.user50, course_id=self.course11.id)
        self.enro51_c10 = CourseEnrollmentFactory.create(user=self.user51, course_id=self.course10.id)
        self.enro60_c11 = CourseEnrollmentFactory.create(user=self.user60, course_id=self.course11.id)
        self.enro70_c20 = CourseEnrollmentFactory.create(user=self.user70, course_id=self.course20.id)
        self.enro75_c20 = CourseEnrollmentFactory.create(user=self.user75, course_id=self.course20.id)
        self.enro80_c20 = CourseEnrollmentFactory.create(user=self.user80, course_id=self.course20.id)
        self.enro85_c10 = CourseEnrollmentFactory.create(user=self.user85, course_id=self.course10.id)
        self.enro90_c30 = CourseEnrollmentFactory.create(user=self.user90, course_id=self.course30.id)
        self.enro95_c10 = CourseEnrollmentFactory.create(user=self.user95, course_id=self.course10.id)

        ## contract register for member
        self.reg10_c1 = ContractRegisterFactory.create(user=self.user10, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg11_c1 = ContractRegisterFactory.create(user=self.user11, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg12_c1 = ContractRegisterFactory.create(user=self.user12, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg20_c1 = ContractRegisterFactory.create(user=self.user20, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg50_c1 = ContractRegisterFactory.create(user=self.user50, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg51_c1 = ContractRegisterFactory.create(user=self.user51, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg60_c1 = ContractRegisterFactory.create(user=self.user60, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)
        self.reg70_c2 = ContractRegisterFactory.create(user=self.user70, contract=self.contract2, status=CONST_REGISTER_INVITATION_CODE)
        self.reg75_c2 = ContractRegisterFactory.create(user=self.user75, contract=self.contract2, status=CONST_REGISTER_INVITATION_CODE)
        self.reg80_c2 = ContractRegisterFactory.create(user=self.user80, contract=self.contract2, status=CONST_REGISTER_INVITATION_CODE)
        #self.reg85_c1 = ContractRegisterFactory.create(user=self.user85, contract=self.contract1, status=CONST_REGISTER_INVITATION_CODE)

        ## group none
        ## no use of group master

        ## member
        self.member10 = MemberFactory.create(
            org=self.org100,
            #group=,
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
            #group=,
            user=self.user11,
            code='0011',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco1',
            org2='gacco11',
        )
        self.member12 = MemberFactory.create(
            org=self.org100,
            #group=,
            user=self.user12,
            code='0012',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org3='gacco11',
        )
        self.member19 = MemberFactory.create(
            org=self.org100,
            #group=,
            user=self.user19,
            code='0019',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org3='gacco11',
        )
        self.member20 = MemberFactory.create(
            org=self.org100,
            #group=,
            user=self.user20,
            code='0020',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org2='gacco11',
        )
        self.member70 = MemberFactory.create(
            org=self.org200,
            #group=,
            user=self.user70,
            code='0070',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org2='gacco11',
        )
        self.member75 = MemberFactory.create(
            org=self.org200,
            #group=,
            user=self.user75,
            code='0075',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco2',
            org2='gacco11',
        )
        self.member79 = MemberFactory.create(
            org=self.org200,
            #group=,
            user=self.user79,
            code='0079',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco99',
        )

        ## Survey Submission
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

        submission10_c11_survey1_data = {
            'course_id': self.course11.id,
            'unit_id': 'c11b1111111111111111111111111111',
            'user': self.user10,
            'survey_name': 'survey c11',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission10_c11_survey1 = SurveySubmissionFactory.create(**submission10_c11_survey1_data)

        ### user11
        submission11_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user11,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission11_c10_survey1 = SurveySubmissionFactory.create(**submission11_c10_survey1_data)

        ### user20
        submission20_c11_survey1_data = {
            'course_id': self.course11.id,
            'unit_id': 'c11b1111111111111111111111111111',
            'user': self.user20,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission20_c11_survey1 = SurveySubmissionFactory.create(**submission20_c11_survey1_data)

        ### user50
        submission50_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user50,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission50_c10_survey1 = SurveySubmissionFactory.create(**submission50_c10_survey1_data)

        submission50_c11_survey1_data = {
            'course_id': self.course11.id,
            'unit_id': 'c11b1111111111111111111111111111',
            'user': self.user50,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission50_c11_survey1 = SurveySubmissionFactory.create(**submission50_c11_survey1_data)

        ### user51
        submission51_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user51,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission51_c10_survey1 = SurveySubmissionFactory.create(**submission51_c10_survey1_data)

        ### user60
        submission60_c11_survey1_data = {
            'course_id': self.course11.id,
            'unit_id': 'c11b1111111111111111111111111111',
            'user': self.user60,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission60_c11_survey1 = SurveySubmissionFactory.create(**submission60_c11_survey1_data)

        ### user70
        submission70_c20_survey1_data = {
            'course_id': self.course20.id,
            'unit_id': 'c20b1111111111111111111111111111',
            'user': self.user70,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission70_c20_survey1 = SurveySubmissionFactory.create(**submission70_c20_survey1_data)

        ### user75
        submission75_c20_survey1_data = {
            'course_id': self.course20.id,
            'unit_id': 'c20b1111111111111111111111111111',
            'user': self.user75,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission75_c20_survey1 = SurveySubmissionFactory.create(**submission75_c20_survey1_data)

        ### user80
        submission80_c20_survey1_data = {
            'course_id': self.course20.id,
            'unit_id': 'c20b1111111111111111111111111111',
            'user': self.user80,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission80_c20_survey1 = SurveySubmissionFactory.create(**submission80_c20_survey1_data)

        ### user85
        submission85_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user85,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission85_c10_survey1 = SurveySubmissionFactory.create(**submission85_c10_survey1_data)

        ### user90
        submission90_c30_survey1_data = {
            'course_id': self.course30.id,
            'unit_id': 'c30b1111111111111111111111111111',
            'user': self.user90,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission90_c30_survey1 = SurveySubmissionFactory.create(**submission90_c30_survey1_data)

        ### user95
        submission95_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user95,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission95_c10_survey1 = SurveySubmissionFactory.create(**submission95_c10_survey1_data)

    def _dump_list(self, rows):
        for r in rows:
            log.debug(r)

    def _convert_to_list(self, qs):
        model = qs.model
        headers = []
        rows = []
        for field in model._meta.fields:
            headers.append(field.name)

        for obj in qs:
            row = []
            for field in headers:
                val = getattr(obj, field)
                if callable(val):
                    val = val()
                if type(val) == unicode:
                    val = val.encode("utf-8")
                row.append(val)

            rows.append(copy.deepcopy(row))
            del row

        return [headers] + rows

    # # test data dump dummy function
    # def test_dump_data(self):
    #     ## dump all orgs
    #     organizations_all = Organization.objects.all()
    #     data = self._convert_to_list(organizations_all)
    #     self._dump_list(data)
    #     ## dump all contracts
    #     contracts_all = Contract.objects.all()
    #     data = self._convert_to_list(contracts_all)
    #     self._dump_list(data)
    #     ## dump all contract details
    #     contractdetails_all = ContractDetail.objects.all()
    #     data = self._convert_to_list(contractdetails_all)
    #     self._dump_list(data)
    #     ## dump all users
    #     users_all = User.objects.all()
    #     data = self._convert_to_list(users_all)
    #     self._dump_list(data)
    #     ## dump all members
    #     members_all = Member.objects.all()
    #     data = self._convert_to_list(members_all)
    #     self._dump_list(data)
    #     ## dump all groups
    #     groups_all = Group.objects.all()
    #     data = self._convert_to_list(groups_all)
    #     self._dump_list(data)
    #     ## dump all entrollments
    #     contractregisters_all = ContractRegister.objects.all()
    #     data = self._convert_to_list(contractregisters_all)
    #     self._dump_list(data)
    #     ## dump all entrollments
    #     enrollments_all = CourseEnrollment.objects.all()
    #     data = self._convert_to_list(enrollments_all)
    #     self._dump_list(data)
    #     ## dump all submissions
    #     submissions_all = SurveySubmission.objects.all()
    #     data = self._convert_to_list(submissions_all)
    #     self._dump_list(data)
    #
    #     self.assertTrue(False)


class SurveyDbNoGroupTest(SurveyDbNoGroupTestBase):

    def _populate_dct(self, user):

        profile = UserProfile.objects.get(user=user)
        try:
            bizuser = BizUser.objects.get(user=user)
        except BizUser.DoesNotExist:
            bizuser = None

        ret_dct = {
            'id': user.id,
            'Username': user.username,
            'Email': user.email,
            'Full Name': profile.name if profile else None,
            'Login Code': bizuser.login_code if bizuser else None,
            'Group Code': '',
            'Member Code': '',
        }
        ret_dct.update({'obj': copy.deepcopy(ret_dct)})

        return ret_dct

    def test_get_users_not_member_o100_c10(self):
        org_id = self.org100.id
        contract_id = self.contract1.id
        course_id = self.course10.id
        user_ids_of_members = [self.user10.id, self.user11.id, self.user12.id, self.user19.id, self.user20.id]
        expected_cnt = 2
        expected_user_id = self.user50.id
        ## Act
        results = view._get_users_not_member(org_id, contract_id, course_id, user_ids_of_members)
        log.debug('results={}'.format(results))
        log.debug('results_len={}'.format(len(results)))
        actual_cnt = len(results)
        actual_user_id = results[self.user50.id]['id']
        self.assertEqual(expected_cnt, actual_cnt)
        self.assertEqual(expected_user_id, actual_user_id)


    def test_populate_users_not_members_o100_c10(self):
        ## Arrange
        org_id = self.org100.id
        contract_id = self.contract1.id
        course_id = self.course10.id
        user_ids_of_members = [self.user10.id, self.user11.id, self.user12.id, self.user19.id, self.user20.id]
        expected_cnt = 2
        expected_dct = self._populate_dct(self.user50)

        ## Act
        sql_statement = helper._create_users_not_members_statement(org_id, contract_id, course_id, user_ids_of_members)
        results = SurveySubmission.objects.raw(sql_statement)

        ret = view._populate_users_not_members(results)
        log.debug(ret)
        actual_cnt = len(ret)

        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        actual_dct = ret[self.user50.id]
        #self.assertEqual(expected_dct, actual_dct)
        self.assertEqual(expected_dct['Username'], actual_dct[_('Username')])
        self.assertEqual(expected_dct['Email'], actual_dct[_('Email')])
        self.assertEqual(expected_dct['Full Name'], actual_dct[_('Full Name')])
        self.assertEqual(expected_dct['Login Code'], actual_dct[_('Login Code')])
        self.assertEqual(expected_dct['Group Code'], actual_dct[_('Group Code')])
        #self.assertTrue(False)

    def test_populate_users_no_members_o100_c10(self):
        org_id = self.org100.id
        contract_id = self.contract1.id
        course_id = self.course10.id
        user_ids_of_members = []
        expected_cnt = 5
        expected_dct = self._populate_dct(self.user50)

        ## Act
        sql_statement = helper._create_users_not_members_statement(org_id, contract_id, course_id, user_ids_of_members)
        results = SurveySubmission.objects.raw(sql_statement)

        ret = view._populate_users_not_members(results)
        log.debug(ret)
        actual_cnt = len(ret)

        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        actual_dct = ret[self.user50.id]
        self.assertEqual(expected_dct['Username'], actual_dct[_('Username')])
        #self.assertTrue(False)


    def test_retrieve_grid_data_o100_c10_no_member_no_condition(self):
        org_id = self.org100.id
        child_group_ids = []
        contract_id = self.contract1.id
        course_id = self.course10.id
        is_filter = 'off'
        expected_cnt = 5
        ## Act
        results = view._retrieve_grid_data(org_id, child_group_ids, contract_id, course_id, is_filter)
        actual_cnt = len(results)
        self.assertEqual(expected_cnt, actual_cnt)


    def test_get_survey_names_list_org100_c10(self):
        ## Arrange
        #org_id = self.org100.id
        course_id = self.course10.id
        expected_cnt = 2
        expected_0 = (self.submission10_c10_survey1.unit_id, self.submission10_c10_survey1.survey_name)
        expected_1 = (self.submission10_c10_survey2.unit_id, self.submission10_c10_survey2.survey_name)
        ## Act
        rows = view._get_survey_names_list(course_id)
        actual_cnt = len(rows)
        actual_0 = rows[0]
        actual_1 = rows[1]
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        self.assertEqual(expected_0, actual_0)
        self.assertEqual(expected_1, actual_1)
        #self.assertTrue(False)

    def test_get_survey_names_list_org100_c11(self):
        ## Arrange
        #org_id = self.org100.id
        course_id = self.course11.id
        expected_cnt = 1
        expected_0 = (self.submission10_c11_survey1.unit_id, self.submission10_c11_survey1.survey_name)
        ## Act
        rows = view._get_survey_names_list(course_id)
        log.debug(rows)
        actual_cnt = len(rows)
        actual_0 = rows[0]
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        self.assertEqual(expected_0, actual_0)
        #self.assertTrue(False)


    def test_get_survey_names_list_org200_c20(self):
        ## Arrange
        #org_id = self.org200.id
        course_id = self.course20.id
        expected_cnt = 1
        ## Act
        rows = view._get_survey_names_list(course_id)
        log.debug(rows)
        actual_cnt = len(rows)
        actual_0 = rows[0]
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        #self.assertTrue(False)


class SurveyNamesListAddTest(BizViewTestBase, ModuleStoreTestCase, BizStoreTestBase):
    def setUp(self):
        super(BizViewTestBase, self).setUp()

        ## course
        self.course10 = CourseFactory.create(org='gacco', number='course10', run='run10')

        ## user
        self.user10 = UserFactory.create(username='na10000', email='nauser10000@example.com')
        self.user11 = UserFactory.create(username='na11000', email='nauser11000@example.com')

        ### user10
        submission10_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user10,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission10_c10_survey1 = SurveySubmissionFactory.create(**submission10_c10_survey1_data)

        ### user11
        submission11_c10_survey1_data = {
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user11,
            'survey_name': 'survey modified',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission11_c10_survey1 = SurveySubmissionFactory.create(**submission11_c10_survey1_data)

    def test_get_survey_names_list_org100_c10(self):
        ## Arrange
        #org_id = self.org100.id
        course_id = self.course10.id
        expected_cnt = 1
        expected = (self.submission10_c10_survey1.unit_id, self.submission10_c10_survey1.survey_name)
        ## Act
        rows = view._get_survey_names_list(course_id)
        log.debug(rows)
        actual_cnt = len(rows)
        actual = rows[0]
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        self.assertEqual(expected, actual)
        #self.assertTrue(False)

    def test_get_survey_names_list_merged_org100_c10(self):
        ## Arrange
        #org_id = self.org100.id
        course_id = self.course10.id
        expected_cnt = 1
        expected = (self.submission11_c10_survey1.unit_id, self.submission11_c10_survey1.survey_name)
        ## Act
        rows = view._get_survey_names_list_merged(course_id)
        log.debug(rows)
        actual_cnt = len(rows)
        actual = rows[0]
        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        self.assertEqual(expected, actual)
        #self.assertTrue(False)

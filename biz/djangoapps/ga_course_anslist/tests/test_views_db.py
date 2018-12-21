# -*- coding: utf-8 -*-
import copy
from ddt import ddt

from django.utils.translation import ugettext as _

## test base
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from biz.djangoapps.util.tests.testcase import BizViewTestBase, BizStoreTestBase

## models
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.ga_login.models import BizUser
from student.models import UserProfile
from ga_survey.models import SurveySubmission

## factories class
from xmodule.modulestore.tests.factories import CourseFactory
from student.tests.factories import UserFactory
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from ga_survey.tests.factories import SurveySubmissionFactory
from student.tests.factories import CourseEnrollmentFactory

## target views
from biz.djangoapps.ga_course_anslist import views as view
from biz.djangoapps.ga_course_anslist import helpers as helper

import logging
log = logging.getLogger(__name__)

@ddt
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




@ddt
class SurveyDbAddTest(BizViewTestBase, ModuleStoreTestCase, BizStoreTestBase):

    def setUp(self):
        super(BizViewTestBase, self).setUp()

        ## organization
        self.org100 = self._create_organization(org_name='gacco100', org_code='gacco-100', creator_org=self.gacco_organization)
        self.org200 = self._create_organization(org_name='gacco200', org_code='gacco-200', creator_org=self.gacco_organization)

        ## course
        self.course10 = CourseFactory.create(org='gacco', number='course', run='run10')
        self.course20 = CourseFactory.create(org='gacco', number='course20', run='run20')

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
        self.user60 = UserFactory.create(username='na60000', email='nauser60000@example.com')

        ## register
        self.reg60 = self._register_contract(self.contract1, self.user60)

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
        self.member88 = MemberFactory.create(
            org=self.org200,
            group=self.group1200,
            user=self.user88,
            code='0088',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco99',
        )
        self.member98 = MemberFactory.create(
            org=self.org200,
            group=self.group2000,
            user=self.user98,
            code='0098',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco99',
        )
        member99 = MemberFactory.create(
            org=self.org200,
            group=self.group2000,
            user=self.user99,
            code='0099',
            created_by=self.user,
            creator_org=self.gacco_organization,
            updated_by=self.user,
            updated_org=self.gacco_organization,
            org1='gacco99',
        )

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
            'course_id': self.course10.id,
            'unit_id': '11111111111111111111111111111111',
            'user': self.user88,
            'survey_name': 'survey1',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission88_c10_survey1 = SurveySubmissionFactory.create(**submission88_c10_survey1_data)

        submission88_c10_survey2_data = {
            'course_id': self.course10.id,
            'unit_id': '22222222222222222222222222222222',
            'user': self.user88,
            'survey_name': 'survey2',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission88_c10_survey2 = SurveySubmissionFactory.create(**submission88_c10_survey2_data)

        submission88_c10_survey3_data = {
            'course_id': self.course10.id,
            'unit_id': '33333333333333333333333333333333',
            'user': self.user88,
            'survey_name': 'survey3',
            'survey_answer': '{"Q1": "1", "Q2": ["1", "2"], "Q3": "submission 1"}',
        }
        self.submission88_c10_survey3 = SurveySubmissionFactory.create(**submission88_c10_survey3_data)

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

    def test_get_users_not_member_o100_c10_u60(self):
        org_id = self.org100.id
        contract_id = self.contract1.id
        course_id = self.course10.id
        user_ids_of_members = [self.user10.id, self.user11.id, self.user12.id, self.user88.id]
        expected_cnt = 1
        expected_user_id = self.user60.id
        ## Act
        results = view._get_users_not_member(org_id, contract_id, course_id, user_ids_of_members)
        log.debug('results={}'.format(results))
        log.debug('results_len={}'.format(len(results)))
        actual_cnt = len(results)
        actual_user_id = results[self.user60.id]['id']
        self.assertEqual(expected_cnt, actual_cnt)
        self.assertEqual(expected_user_id, actual_user_id)


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

    def test_populate_users_not_members(self):
        ## Arrange
        org_id = self.org100.id
        contract_id = self.contract1.id
        course_id = self.course10.id
        user_ids_of_members = [self.user10.id, self.user11.id, self.user12.id, self.user88.id]
        expected_cnt = 1
        expected_dct = self._populate_dct(self.user60)

        ## Act
        sql_statement = helper._create_users_not_members_statement(org_id, contract_id, course_id, user_ids_of_members)
        results = SurveySubmission.objects.raw(sql_statement)

        ret = view._populate_users_not_members(results)
        actual_cnt = len(ret)

        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        actual_dct = ret[self.user60.id]
        #self.assertEqual(expected_dct, actual_dct)
        self.assertEqual(expected_dct['Username'], actual_dct[_('Username')])
        # self.assertEqual(expected_dct_1['Username'], actual_dct_1[_('Username')])
        # self.assertEqual(expected_dct_1['Email'], actual_dct_1[_('Email')])
        # self.assertEqual(expected_dct_1['Full Name'], actual_dct_1[_('Full Name')])
        # self.assertEqual(expected_dct_1['Login Code'], actual_dct_1[_('Login Code')])
        # self.assertEqual(expected_dct_1['Group Code'], actual_dct_1[_('Group Code')])

    def test_populate_users_no_members(self):
        org_id = self.org100.id
        contract_id = self.contract1.id
        course_id = self.course10.id
        user_ids_of_members = []
        expected_cnt = 1
        expected_dct = self._populate_dct(self.user60)

        ## Act
        sql_statement = helper._create_users_not_members_statement(org_id, contract_id, course_id, user_ids_of_members)
        results = SurveySubmission.objects.raw(sql_statement)

        ret = view._populate_users_not_members(results)
        actual_cnt = len(ret)

        ## Assert
        self.assertEqual(expected_cnt, actual_cnt)
        actual_dct = ret[self.user60.id]
        self.assertEqual(expected_dct['Username'], actual_dct[_('Username')])
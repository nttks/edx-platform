## test base
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from biz.djangoapps.util.tests.testcase import BizViewTestBase, BizStoreTestBase
#from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase

## factories class
from xmodule.modulestore.tests.factories import CourseFactory
from student.tests.factories import UserFactory
from biz.djangoapps.gx_member.tests.factories import MemberFactory
from biz.djangoapps.gx_org_group.tests.factories import GroupFactory
from ga_survey.tests.factories import SurveySubmissionFactory
from student.tests.factories import CourseEnrollmentFactory


class AnslistTestBase(BizViewTestBase, ModuleStoreTestCase, BizStoreTestBase):

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

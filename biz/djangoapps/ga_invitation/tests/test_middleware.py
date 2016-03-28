"""
Tests for ga_invitation middleware.
"""
from contextlib import nested
import ddt
from mock import patch

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase, RequestFactory
from django.utils.functional import SimpleLazyObject

from courseware.tests.helpers import LoginEnrollmentTestCase
from opaque_keys.edx.keys import CourseKey
from student.roles import CourseStaffRole
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory

from biz.djangoapps.ga_contract.models import (
    Contract, ContractDetail, CONTRACT_TYPE_PF,
    CONTRACT_TYPE_OWNERS, CONTRACT_TYPE_OWNER_SERVICE, CONTRACT_TYPE_GACCO_SERVICE,
)
from biz.djangoapps.ga_contract.tests.factories import ContractFactory, ContractDetailFactory
from biz.djangoapps.ga_invitation.middleware import SpocStatusMiddleware
from biz.djangoapps.ga_invitation.models import (
    ContractRegister, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE,
)
from biz.djangoapps.ga_invitation.tests.factories import ContractRegisterFactory
from biz.djangoapps.util.tests.testcase import BizViewTestBase


class SpocStatusTestBase(BizViewTestBase, ModuleStoreTestCase):

    def _create_contract(self, user, course_id, contract_type='PF'):
        contract = ContractFactory.create(
            contract_type=contract_type,
            contractor_organization=self.gacco_organization,
            owner_organization=self.gacco_organization,
            created_by=user
        )
        contract_detail = ContractDetailFactory.create(contract=contract, course_id=course_id)
        return contract_detail

    def _create_contract_register(self, user, contract, status):
        return ContractRegisterFactory.create(
            user=user, contract=contract, status=status
        )


@ddt.ddt
class SpocStatusMiddlewareTest(SpocStatusTestBase):
    """
    Tests that the middleware set spoc status to request.
    """

    USERNAME = 'test_user'
    PASSWORD = 'biz'

    def setUp(self):
        super(SpocStatusMiddlewareTest, self).setUp()

        self.user = UserFactory.create(username=self.USERNAME, password=self.PASSWORD)

        self.request = RequestFactory().request()
        self.request.user = self.user

    @ddt.data(
        '/courses/course-v1:org+course+run/',
        '/courses/course-v1:org+course+run/about',
        '/courses/course-v1:org+course+run/info',
        '/courses/course-v1:org+course+run/courseware',
        '/courses/course-v1:org+course+run/discussion/forum',
        '/courses/course-v1:org+course+run/progress',
    )
    def test_process_request_target_path(self, request_path):
        self.request.path = request_path

        SpocStatusMiddleware().process_request(self.request)

        # Verify spoc_status is lazy
        self.assertTrue(isinstance(self.request.spoc_status, SimpleLazyObject))
        self.assertEqual((False, False), self.request.spoc_status)

    @ddt.data(
        '/courses/course-v1:org+course+run',
        '/foo/courses/course-v1:org+course+run/',
        '/coursesX/course-v1:org+course+run/',
    )
    def test_process_request_not_target_path(self, request_path):
        self.request.path = request_path

        SpocStatusMiddleware().process_request(self.request)

        # Verify spoc_status is not lazy
        self.assertFalse(isinstance(self.request.spoc_status, SimpleLazyObject))
        self.assertEqual((False, False), self.request.spoc_status)

    @ddt.data(
        '/courses/course-v999:org+course+run/',
    )
    def test_process_request_invalid_course_id(self, request_path):
        self.request.path = request_path

        SpocStatusMiddleware().process_request(self.request)

        # Verify spoc_status is not lazy
        self.assertFalse(isinstance(self.request.spoc_status, SimpleLazyObject))
        self.assertEqual((False, False), self.request.spoc_status)

    def test_process_request_not_spoc_and_has_access_input(self):
        course_id = CourseKey.from_string('course-v1:org+course+run')

        # Create Contract but not SPOC
        contract_detail = self._create_contract(
            user=self.user,
            course_id=course_id,
            contract_type=CONTRACT_TYPE_GACCO_SERVICE[0]
        )
        # Create ContractRegister as INPUT_INVITATION_CODE.
        self._create_contract_register(self.user, contract_detail.contract, INPUT_INVITATION_CODE)

        self.request.path = '/courses/{}/'.format(course_id)

        SpocStatusMiddleware().process_request(self.request)

        # If course is not SPOC, has_access is False regardless of the status of ContractRegister
        self.assertEqual((False, False), self.request.spoc_status)

    def test_process_request_spoc_course(self):
        course_id = CourseKey.from_string('course-v1:org+course+run')

        # Create SPOC contract. Not create ContractRegister.
        self._create_contract(
            user=self.user,
            course_id=course_id,
            contract_type=CONTRACT_TYPE_PF[0]
        )

        self.request.path = '/courses/{}/'.format(course_id)

        SpocStatusMiddleware().process_request(self.request)

        self.assertEqual((True, False), self.request.spoc_status)

    def test_process_request_spoc_course_with_staff(self):
        course_id = CourseKey.from_string('course-v1:org+course+run')
        CourseFactory.create(org=course_id.org, number=course_id.course, run=course_id.run)

        staff_user = UserFactory.create(username='test_staff', password='test', is_staff=True)
        self.request.user = staff_user

        # Create SPOC contract. Not create ContractRegister.
        self._create_contract(
            user=self.user,
            course_id=course_id,
            contract_type=CONTRACT_TYPE_PF[0]
        )

        self.request.path = '/courses/course-v1:org+course+run/'

        SpocStatusMiddleware().process_request(self.request)

        # has_spoc_access is True if user is staff
        self.assertEqual((True, True), self.request.spoc_status)

    @ddt.data(
        INPUT_INVITATION_CODE,
        REGISTER_INVITATION_CODE,
    )
    def test_process_request_spoc_course_and_status(self, status):
        course_id = CourseKey.from_string('course-v1:org+course+run')

        contract_detail = self._create_contract(
            user=self.user,
            course_id=course_id,
            contract_type=CONTRACT_TYPE_PF[0]
        )
        self._create_contract_register(self.user, contract_detail.contract, status=status)

        self.request.path = '/courses/course-v1:org+course+run/'

        SpocStatusMiddleware().process_request(self.request)

        expected_has_access = status in (INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE)
        self.assertEqual((True, expected_has_access), self.request.spoc_status)


@ddt.ddt
class CourseAboutTest(SpocStatusTestBase):
    """
    Tests for secret course about
    """

    def setUp(self):
        super(CourseAboutTest, self).setUp()
        self.course = CourseFactory.create(org='org', number='course', run='run')
        self.about = ItemFactory.create(
            category='about', parent_location=self.course.location,
            data="Test Secret Course About", display_name='overview'
        )

    def test_spoc_course_with_not_logged_in(self):
        self.setup_user()

        # Create Contract as SPOC
        contract_detail = self._create_contract(
            user=self.user,
            course_id=self.course.id,
            contract_type=CONTRACT_TYPE_PF[0]
        )
        # Create ContractRegister as having SPOC access
        self._create_contract_register(self.user, contract_detail.contract, REGISTER_INVITATION_CODE)

        self.logout()

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_not_spoc_course_with_not_logged_in(self):
        self.setup_user()

        # Create Contract as SPOC
        contract_detail = self._create_contract(
            user=self.user,
            course_id=self.course.id,
            contract_type=CONTRACT_TYPE_GACCO_SERVICE[0]
        )

        self.logout()

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Test Secret Course About", resp.content)

    @ddt.unpack
    @ddt.data(
        (CONTRACT_TYPE_PF[0], INPUT_INVITATION_CODE),
        (CONTRACT_TYPE_PF[0], REGISTER_INVITATION_CODE),
        (CONTRACT_TYPE_OWNERS[0], INPUT_INVITATION_CODE),
        (CONTRACT_TYPE_OWNERS[0], REGISTER_INVITATION_CODE),
        (CONTRACT_TYPE_OWNER_SERVICE[0], INPUT_INVITATION_CODE),
        (CONTRACT_TYPE_OWNER_SERVICE[0], REGISTER_INVITATION_CODE),
    )
    def test_spoc_course_with_has_access(self, contract_type, status):
        self.setup_user()

        # Create Contract as SPOC
        contract_detail = self._create_contract(
            user=self.user,
            course_id=self.course.id,
            contract_type=contract_type
        )
        # Create ContractRegister as having SPOC access
        self._create_contract_register(self.user, contract_detail.contract, status)

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Test Secret Course About", resp.content)

    def test_not_spoc_with_not_has_access(self):
        self.setup_user()

        # Create Contract as not SPOC
        contract_detail = self._create_contract(
            user=self.user,
            course_id=self.course.id,
            contract_type=CONTRACT_TYPE_GACCO_SERVICE[0]
        )

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Test Secret Course About", resp.content)

    @ddt.data(
        CONTRACT_TYPE_PF[0],
        CONTRACT_TYPE_OWNERS[0],
        CONTRACT_TYPE_OWNER_SERVICE[0],
    )
    def test_spoc_course_with_not_has_access(self, contract_type):
        self.setup_user()

        # Create Contract but not SPOC
        contract_detail = self._create_contract(
            user=self.user,
            course_id=self.course.id,
            contract_type=contract_type
        )
        # Not Create ContractRegister

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        with patch('courseware.views.log.warning') as warning_log:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 404)
            warning_log.assert_called_with(
                'User(id={}) has no permission to access spoc course(course_id={}).'.format(
                    self.user.id, unicode(self.course.id)
                )
            )

    def test_spoc_course_with_global_staff(self):
        self.setup_user()

        # Make user to global_staff
        self.user.is_staff = True
        self.user.save()

        # Create Contract but not SPOC
        contract_detail = self._create_contract(
            user=self.user,
            course_id=self.course.id,
            contract_type=CONTRACT_TYPE_PF[0]
        )
        # Not Create ContractRegister

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_spoc_course_with_course_staff(self):
        self.setup_user()

        # Make user to course staff
        CourseStaffRole(self.course.id).add_users(User.objects.get(pk=self.user.id))

        # Create Contract but not SPOC
        contract_detail = self._create_contract(
            user=self.user,
            course_id=self.course.id,
            contract_type=CONTRACT_TYPE_PF[0]
        )
        # Not Create ContractRegister

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

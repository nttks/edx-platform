"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".
"""
import logging

from django.core.management import call_command
from django.test import TestCase
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from biz.djangoapps.ga_contract_operation.management.commands import unregister_masked_user
from biz.djangoapps.ga_invitation.models import ContractRegister, UNREGISTER_INVITATION_CODE
from biz.djangoapps.util.tests.testcase import BizStoreTestBase
from student.models import CourseEnrollment
from student.tests.factories import UserFactory, CourseEnrollmentFactory


class TestArgParsing(TestCase):
    """
    Tests for parsing arguments of the `unregister_masked_user` command
    """

    def setUp(self):
        super(TestArgParsing, self).setUp()
        self.command = unregister_masked_user.Command()

    def test_args_debug(self):
        self.command.execute(debug=True)
        self.assertEquals(unregister_masked_user.log.level, logging.DEBUG)


class UnregisterMaskedUserTest(BizStoreTestBase, ModuleStoreTestCase):
    def setUp(self):
        super(UnregisterMaskedUserTest, self).setUp()

    def test_unregister_masked_user(self):
        course = CourseFactory.create(
            org='edx',
            number='verified',
            display_name='Verified Course'
        )

        # create a contract
        contract = self._create_contract()
        # create a masked user
        masked_user = self._create_user_by_email('masked_email')
        # register contract to a masked user
        ContractRegister.objects.get_or_create(user=masked_user, contract=contract)
        # register a course to a masked user
        CourseEnrollmentFactory.create(user=masked_user, course_id=course.id)
        # create a non masked user
        unmasked_user = self._create_user_by_email('unmasked@example.com')
        # register a contract to a non masked user
        ContractRegister.objects.get_or_create(user=unmasked_user, contract=contract)
        # register a course to a non masked user
        CourseEnrollmentFactory.create(user=unmasked_user, course_id=course.id)
        # assert contract register status
        masked_user_contract_register = ContractRegister.objects.get(user=masked_user, contract=contract)
        self.assertNotEqual(UNREGISTER_INVITATION_CODE, masked_user_contract_register.status)
        # assert course enrollment before command
        for course_key in [detail.course_id for detail in masked_user_contract_register.contract.details.all()]:
            self.assertTrue(CourseEnrollment.is_enrolled(masked_user_contract_register.user, course_key))
        # assert contract register status
        unmasked_user_contract_register = ContractRegister.objects.get(user=unmasked_user, contract=contract)
        self.assertNotEqual(UNREGISTER_INVITATION_CODE, unmasked_user_contract_register.status)
        # assert course enrollment before command
        for course_key in [detail.course_id for detail in unmasked_user_contract_register.contract.details.all()]:
            self.assertTrue(CourseEnrollment.is_enrolled(unmasked_user_contract_register.user, course_key))
        # call unregister_masked_user command
        call_command('unregister_masked_user', debug=False)
        # assert contract register status
        masked_user_contract_register = ContractRegister.objects.get(user=masked_user, contract=contract)
        self.assertEquals(UNREGISTER_INVITATION_CODE, masked_user_contract_register.status)
        # assert course unenrollment after command
        for course_key in [detail.course_id for detail in masked_user_contract_register.contract.details.all()]:
            self.assertFalse(CourseEnrollment.is_enrolled(masked_user_contract_register.user, course_key))
        # assert contract register status
        unmasked_user_contract_register = ContractRegister.objects.get(user=unmasked_user, contract=contract)
        self.assertNotEqual(UNREGISTER_INVITATION_CODE, unmasked_user_contract_register.status)
        # assert course enrollment after command
        for course_key in [detail.course_id for detail in unmasked_user_contract_register.contract.details.all()]:
            self.assertTrue(CourseEnrollment.is_enrolled(unmasked_user_contract_register.user, course_key))

    def _create_user_by_email(self, email):
        user = UserFactory.create(email=email)
        return user

    def _unenroll(self, user, course):
        CourseEnrollment.unenroll(user, course.id)

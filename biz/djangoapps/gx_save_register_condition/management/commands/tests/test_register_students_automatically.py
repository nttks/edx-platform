# -*- coding: utf-8 -*-
"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import json
import logging
from datetime import datetime
from django.core.management import call_command
from django.test import TestCase
from biz.djangoapps.ga_contract.models import ContractOption
from biz.djangoapps.gx_save_register_condition.management.commands import register_students_automatically
from biz.djangoapps.gx_save_register_condition.models import ReflectConditionTaskHistory
from biz.djangoapps.util.tests.testcase import BizViewTestBase
from openedx.core.djangoapps.ga_task.models import Task
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase


class TestArgParsing(TestCase):
    """
    Tests for parsing arguments of the `register_students_automatically` command
    """
    def setUp(self):
        super(TestArgParsing, self).setUp()

    def test_args_debug(self):
        call_command('register_students_automatically', debug=True)
        self.assertEquals(register_students_automatically.log.level, logging.DEBUG)


class RegisterStudentsAutomatically(BizViewTestBase, ModuleStoreTestCase):
    """
    Note: Detail test is written to 'gx_save_register_condition/tests/test_utils.py'.
    """
    def setUp(self):
        super(RegisterStudentsAutomatically, self).setUp()
        # Create default mail
        self._create_contract_mail_default()
        # Course
        self.course_spoc_org1_contract1 = CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc1', run='run1')
        self.course_spoc_org1_contract2= CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc2', run='run2')
        self.course_spoc_org2_contract1= CourseFactory.create(
            org=self.gacco_organization.org_code, number='spoc3', run='run2')

        # Organization 1
        self.org1 = self._create_organization(
            org_code='sample001', creator_org=self.gacco_organization, org_name='sample001')
        self.org1_contract1 = self._create_contract(
            contractor_organization=self.org1,
            detail_courses=[self.course_spoc_org1_contract1.id],
            additional_display_names=['dept'],
            auto_register_reservation_date=datetime.now()
        )
        self.org1_contract2 = self._create_contract(
            contractor_organization=self.org1,
            detail_courses=[self.course_spoc_org1_contract2.id],
            additional_display_names=['country'])

        # Organization 3
        self.org2 = self._create_organization(
            org_code='sample002', creator_org=self.gacco_organization, org_name='sample002')
        self.org2_contract1 = self._create_contract(
            contractor_organization=self.org2,
            detail_courses=[self.course_spoc_org2_contract1.id],
            auto_register_students_flg=True,
            additional_display_names=['country'])

    def test_target_contract(self):
        call_command('register_students_automatically')

        # Reservation
        task_history1 = ReflectConditionTaskHistory.objects.get(organization=self.org1, contract=self.org1_contract1)
        self.assertTrue(task_history1.result)
        self.assertEqual('', task_history1.messages)
        task_list1 = Task.objects.filter(task_id=task_history1.task_id)
        self.assertEqual(1, len(task_list1))
        task1 = task_list1[0]
        self.assertEqual(task1.task_type, 'reflect_conditions_reservation')
        self.assertEqual(task1.task_state, 'SUCCESS')
        task_output1 = json.loads(task1.task_output)
        self.assertTrue(all(key in task_output1 for key in [
            'total','failed','student_register', 'student_unregister', 'personalinfo_mask']))
        self.assertEqual(0, task_output1['total'])
        self.assertEqual(0, task_output1['student_register'])
        self.assertEqual(0, task_output1['student_unregister'])
        self.assertEqual(0, task_output1['personalinfo_mask'])
        self.assertEqual(0, task_output1['failed'])
        self.assertEqual(None, ContractOption.objects.get(contract=self.org1_contract1).auto_register_reservation_date)
        # Batch
        task_history2 = ReflectConditionTaskHistory.objects.get(organization=self.org2, contract=self.org2_contract1)
        self.assertTrue(task_history2.result)
        self.assertEqual('', task_history2.messages)
        task_list2 = Task.objects.filter(task_id=task_history2.task_id)
        self.assertEqual(1, len(task_list2))
        task2 = task_list2[0]
        self.assertEqual(task2.task_type, 'reflect_conditions_batch')
        self.assertEqual(task2.task_state, 'SUCCESS')
        task_output2 = json.loads(task2.task_output)
        self.assertTrue(all(key in task_output2 for key in [
            'total','failed','student_register', 'student_unregister', 'personalinfo_mask']))
        self.assertEqual(0, task_output2['total'])
        self.assertEqual(0, task_output2['student_register'])
        self.assertEqual(0, task_output2['student_unregister'])
        self.assertEqual(0, task_output2['personalinfo_mask'])
        self.assertEqual(0, task_output2['failed'])
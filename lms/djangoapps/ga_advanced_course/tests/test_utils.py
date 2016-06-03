
from datetime import timedelta

from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ga_advanced_course.exceptions import InvalidOrder
from ga_advanced_course.utils import (
    is_advanced_course_purchased, is_advanced_course_full, is_advanced_course_end_of_sale,
    check_order_can_purchase,
)
from ga_shoppingcart.utils import SC_SESSION_TIMEOUT
from .factories import AdvancedF2FCourseFactory, AdvancedCourseTicketFactory
from .utils import purchase_ticket, start_purchase_ticket, make_ticket_to_out_of_sale


class UtilsTest(ModuleStoreTestCase):

    def setUp(self):
        super(UtilsTest, self).setUp()
        self.users = [UserFactory.create() for _ in range(3)]
        self.course_1 = CourseFactory.create()
        self.course_2 = CourseFactory.create()

        self.advanced_course_1 = AdvancedF2FCourseFactory.create(
            course_id=self.course_1.id,
            display_name='display_name_1'
        )
        self.advanced_course_2 = AdvancedF2FCourseFactory.create(
            course_id=self.course_1.id,
            display_name='display_name_2'
        )
        self.advanced_course_3 = AdvancedF2FCourseFactory.create(
            course_id=self.course_2.id,
            display_name='display_name_3'
        )
        self.advanced_course_tickets_1 = [
            AdvancedCourseTicketFactory.create(advanced_course=self.advanced_course_1),
            AdvancedCourseTicketFactory.create(advanced_course=self.advanced_course_1)
        ]
        self.advanced_course_tickets_2 = [
            AdvancedCourseTicketFactory.create(advanced_course=self.advanced_course_2),
            AdvancedCourseTicketFactory.create(advanced_course=self.advanced_course_2)
        ]
        self.advanced_course_tickets_3 = [
            AdvancedCourseTicketFactory.create(advanced_course=self.advanced_course_3),
            AdvancedCourseTicketFactory.create(advanced_course=self.advanced_course_3)
        ]

    def test_check_order_can_purchase(self):
        order = start_purchase_ticket(self.users[0], self.advanced_course_tickets_1[0])
        # Normal order
        check_order_can_purchase(order)

    def test_check_order_can_purchase_order_not_paying(self):
        order = purchase_ticket(self.users[0], self.advanced_course_tickets_1[0])

        with self.assertRaises(InvalidOrder):
            check_order_can_purchase(order)

    def test_check_order_can_purchase_item_not_paying(self):
        order = start_purchase_ticket(self.users[0], self.advanced_course_tickets_1[0])
        _item = order.orderitem_set.all()[0]
        _item.status = 'purchased'
        _item.save()

        with self.assertRaises(InvalidOrder):
            check_order_can_purchase(order)

    def test_check_order_can_purchase_timeout(self):
        order = start_purchase_ticket(self.users[0], self.advanced_course_tickets_1[0])
        _item = order.orderitem_set.all()[0]
        _item.created = _item.created - timedelta(seconds=SC_SESSION_TIMEOUT)
        _item.save()

        with self.assertRaises(InvalidOrder):
            check_order_can_purchase(order)

    def test_is_advanced_course_purchased(self):
        # user0:
        #   paying ticket_1_0
        #   purchased ticket_2_0
        start_purchase_ticket(self.users[0], self.advanced_course_tickets_1[0])
        purchase_ticket(self.users[0], self.advanced_course_tickets_2[0])

        # user1:
        #   paying ticket_2_0
        #   purchased ticket_1_0
        start_purchase_ticket(self.users[1], self.advanced_course_tickets_2[0])
        purchase_ticket(self.users[1], self.advanced_course_tickets_1[0])

        self.assertFalse(is_advanced_course_purchased(self.users[0], self.advanced_course_1))
        self.assertTrue(is_advanced_course_purchased(self.users[0], self.advanced_course_2))
        self.assertTrue(is_advanced_course_purchased(self.users[1], self.advanced_course_1))
        self.assertFalse(is_advanced_course_purchased(self.users[1], self.advanced_course_2))

        # Verify no item record user
        self.assertFalse(is_advanced_course_purchased(self.users[2], self.advanced_course_1))
        self.assertFalse(is_advanced_course_purchased(self.users[2], self.advanced_course_2))

    def test_is_advanced_course_full(self):
        # 9 tickets purchase
        for _ in range(5):
            purchase_ticket(self.users[0], self.advanced_course_tickets_1[0])
        for _ in range(4):
            purchase_ticket(self.users[0], self.advanced_course_tickets_1[1])

        # Verify not full
        self.assertFalse(is_advanced_course_full(self.advanced_course_1))

        # last ticket purchase
        order = purchase_ticket(self.users[0], self.advanced_course_tickets_1[0])

        # Verify full
        self.assertTrue(is_advanced_course_full(self.advanced_course_1))

        # Cancel last purchased ticket
        order.refund()
        # Verify not full
        self.assertFalse(is_advanced_course_full(self.advanced_course_1))

        # last ticket purchase again
        purchase_ticket(self.users[0], self.advanced_course_tickets_1[0])

        # Verify full
        self.assertTrue(is_advanced_course_full(self.advanced_course_1))

    def test_is_advanced_course_full_with_paying(self):
        # 9 tickets purchase
        for _ in range(5):
            purchase_ticket(self.users[0], self.advanced_course_tickets_1[0])
        for _ in range(4):
            purchase_ticket(self.users[0], self.advanced_course_tickets_1[1])

        # Verify not full
        self.assertFalse(is_advanced_course_full(self.advanced_course_1))

        # last ticket paying
        purchase_ticket(self.users[0], self.advanced_course_tickets_1[0])

        # Verify full
        self.assertTrue(is_advanced_course_full(self.advanced_course_1))

    def test_is_advanced_course_end_of_sale(self):
        # All tickets are end of sale.
        for ticket in self.advanced_course_tickets_1:
            make_ticket_to_out_of_sale(ticket)
        self.assertTrue(is_advanced_course_end_of_sale(self.advanced_course_1))
        self.assertTrue(is_advanced_course_end_of_sale(self.advanced_course_1, self.advanced_course_tickets_1))

        # Not all tickets are end of sale.
        make_ticket_to_out_of_sale(self.advanced_course_tickets_2[0])
        self.assertFalse(is_advanced_course_end_of_sale(self.advanced_course_2))
        self.assertFalse(is_advanced_course_end_of_sale(self.advanced_course_2, self.advanced_course_tickets_2))

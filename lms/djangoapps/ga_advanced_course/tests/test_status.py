
from mock import patch

from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ga_advanced_course.status import AdvancedCourseStatus
from .factories import AdvancedF2FCourseFactory, AdvancedCourseTicketFactory
from .utils import purchase_ticket, start_purchase_ticket, make_ticket_to_out_of_sale


class AdvancedCourseStatusTest(ModuleStoreTestCase):

    def setUp(self):
        super(AdvancedCourseStatusTest, self).setUp()
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

    def _make_limit_state(self):
        # Make advanced_course_1 to full just before
        for _ in range(8):
            purchase_ticket(UserFactory.create(), self.advanced_course_tickets_1[0])

        # Make advanced_course_2 to full just before
        for _ in range(9):
            purchase_ticket(UserFactory.create(), self.advanced_course_tickets_2[0])

        # Make ticket except ticket_1_0 to out of sale
        make_ticket_to_out_of_sale(self.advanced_course_tickets_1[1])
        make_ticket_to_out_of_sale(self.advanced_course_tickets_2[1])

    def test_has_available_f2f_course_full(self):
        self._make_limit_state()

        course = self.course_1
        self.client.user = self.users[0]

        # Verify available default
        self.assertTrue(AdvancedCourseStatus(self.client, course).has_available_f2f_course())

        # Make advanced_course_1 to full
        purchase_ticket(self.users[1], self.advanced_course_tickets_1[0])
        purchase_ticket(self.users[2], self.advanced_course_tickets_1[0])

        # Verify available
        self.assertTrue(AdvancedCourseStatus(self.client, course).has_available_f2f_course())

        # Make advanced_course_2 to full
        purchase_ticket(self.users[1], self.advanced_course_tickets_2[0])

        # Verify unavailable
        self.assertFalse(AdvancedCourseStatus(self.client, course).has_available_f2f_course())

    def test_has_available_f2f_course_out_of_sale(self):
        self._make_limit_state()

        course = self.course_1
        self.client.user = self.users[0]

        # Verify available default
        self.assertTrue(AdvancedCourseStatus(self.client, course).has_available_f2f_course())

        # Make all tickets of advanced_course_1 to out-of-sale
        make_ticket_to_out_of_sale(self.advanced_course_tickets_1[0])

        # Verify available
        self.assertTrue(AdvancedCourseStatus(self.client, course).has_available_f2f_course())

        # Make all tickets of advanced_course_2 to out-of-sale
        make_ticket_to_out_of_sale(self.advanced_course_tickets_2[0])

        # Verify available
        self.assertFalse(AdvancedCourseStatus(self.client, course).has_available_f2f_course())

    def test_has_available_f2f_course_full_and_out_of_sale(self):
        self._make_limit_state()

        course = self.course_1
        self.client.user = self.users[0]

        # Verify available default
        self.assertTrue(AdvancedCourseStatus(self.client, course).has_available_f2f_course())

        # Make advanced_course_1 to full
        purchase_ticket(self.users[1], self.advanced_course_tickets_1[0])
        purchase_ticket(self.users[2], self.advanced_course_tickets_1[0])
        # Make all ticket of advanced_course_2 to out-of-sale
        make_ticket_to_out_of_sale(self.advanced_course_tickets_2[0])

        # Verify available default
        self.assertFalse(AdvancedCourseStatus(self.client, course).has_available_f2f_course())

    def test_has_available_f2f_course_purchased(self):
        self._make_limit_state()

        course = self.course_1
        self.client.user = self.users[0]

        # Verify available default
        self.assertTrue(AdvancedCourseStatus(self.client, course).has_available_f2f_course())

        # Purchase
        purchase_ticket(self.client.user, self.advanced_course_tickets_1[0])

        # Verify available even if purchased
        self.assertTrue(AdvancedCourseStatus(self.client, course).has_available_f2f_course())

    def test_is_purchased(self):
        course = self.course_1
        self.client.user = self.users[0]

        # Verify not purchased default
        self.assertFalse(AdvancedCourseStatus(self.client, course).is_purchased())
        self.assertFalse(AdvancedCourseStatus(self.client, course).is_purchased(self.advanced_course_1.id))
        self.assertFalse(AdvancedCourseStatus(self.client, course).is_purchased(self.advanced_course_2.id))

        # Purchase
        purchase_ticket(self.client.user, self.advanced_course_tickets_1[0])

        # Verify purchased
        self.assertTrue(AdvancedCourseStatus(self.client, course).is_purchased())
        self.assertTrue(AdvancedCourseStatus(self.client, course).is_purchased(self.advanced_course_1.id))
        self.assertFalse(AdvancedCourseStatus(self.client, course).is_purchased(self.advanced_course_2.id))

        with self.assertRaises(ValueError):
            self.assertTrue(AdvancedCourseStatus(self.client, course).is_purchased(self.advanced_course_3.id))

    def test_get_purchased_orders(self):
        course = self.course_1
        self.client.user = self.users[0]

        # Verify no order default
        self.assertEqual([], AdvancedCourseStatus(self.client, course).get_purchased_orders())

        # Just start purchase
        start_purchase_ticket(self.client.user, self.advanced_course_tickets_1[0])
        self.assertEqual([], AdvancedCourseStatus(self.client, course).get_purchased_orders())

        # purchased
        order1 = purchase_ticket(self.client.user, self.advanced_course_tickets_1[0])
        self.assertEqual([order1], AdvancedCourseStatus(self.client, course).get_purchased_orders())

        # by another user
        self.client.user = self.users[1]
        self.assertEqual([], AdvancedCourseStatus(self.client, course).get_purchased_orders())
        self.client.user = self.users[0]

        # purchased more
        order2 = purchase_ticket(self.client.user, self.advanced_course_tickets_2[0])
        self.assertEqual([order1, order2], AdvancedCourseStatus(self.client, course).get_purchased_orders())

    def test_show_upsell_message_purchased(self):
        course = self.course_1
        self.client.user = self.users[0]

        # Verify shown default
        self.assertTrue(AdvancedCourseStatus(self.client, course).show_upsell_message())

        # after purchased of another course
        purchase_ticket(self.client.user, self.advanced_course_tickets_3[0])
        self.assertTrue(AdvancedCourseStatus(self.client, course).show_upsell_message())

        # after purchased
        purchase_ticket(self.client.user, self.advanced_course_tickets_1[0])
        self.assertFalse(AdvancedCourseStatus(self.client, course).show_upsell_message())

    def test_show_upsell_message_disabled_upsell(self):
        course = self.course_1
        self.client.user = self.users[0]

        # Verify shown default
        self.assertTrue(AdvancedCourseStatus(self.client, course).show_upsell_message())

        with patch('ga_advanced_course.status.is_upsell_disabled', return_value=True):
            self.assertFalse(AdvancedCourseStatus(self.client, course).show_upsell_message())


from selenium.common.exceptions import NoSuchElementException

from . import BASE_URL
from .course_about import CourseAboutPage as EdXCourseAboutPage
from .pay_and_verify import (
    FakePaymentPage as EdXFakePaymentPage,
    PaymentAndVerificationFlow as EdXPaymentAndVerificationFlow,
)

from .ga_dashboard import DashboardPage as GaDashboradPage


class PaymentAndVerificationFlow(EdXPaymentAndVerificationFlow):

    def proceed_to_payment(self):
        """Interact with the payment button."""
        self.q(css=".payment-button").click()

        return FakePaymentPage(self.browser, self._course_id).wait_for_page()

    def go_to_dashboard(self):
        self.q(css='.action-buttons a')[0].click()
        return DashboardPage(self.browser).wait_for_page()

    def get_payment_content(self):
        data = self.q(css='.product-info')
        return {
            'description': self.q(css='.product-name')[0].text,
            'price': self.q(css='.product-info .price')[0].text.split(' ')[0][1:],
        }

    def get_receipt_content(self):
        data = self.q(css='.report-receipt td')
        return {
            'receipt_num': data[0].text,
            'description': data[1].text,
            'datetime': data[2].text,
            'payment_method': data[3].text,
            'price': data[4].text.split(' ')[0][1:],
        }


class CourseAboutPage(EdXCourseAboutPage):

    def register(self):
        self.q(css='a.register').first.click()
        return PaymentAndVerificationFlow(self.browser, self.course_id).wait_for_page()


class FakePaymentPage(EdXFakePaymentPage):

    url = BASE_URL + "/shoppingcart/payment_fake_gmo"

    def submit_payment(self, payment_method='card'):
        """Interact with the payment submission button."""
        self.q(css="input[value='Submit {}']".format(payment_method)).click()

        return PaymentAndVerificationFlow(self.browser, self._course_id, entry_point='payment-confirmation').wait_for_page()


class DashboardPage(GaDashboradPage):

    def has_paid_course_purchased_message(self, course_name):
        try:
            self._get_element_in_course(course_name, ".advanced-course-information.paid-course.purchased")
            return True
        except NoSuchElementException:
            return False

    def show_receipt_page(self, course_id, course_name):
        self._get_element_in_course(course_name, '.advanced-course-information.paid-course.purchased .btn').click()

        return PaymentAndVerificationFlow(self.browser, course_id, entry_point='payment-confirmation').wait_for_page()

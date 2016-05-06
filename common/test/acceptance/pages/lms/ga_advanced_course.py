"""
Pages for advanced course
"""
from selenium.common.exceptions import NoSuchElementException

from bok_choy.page_object import PageObject

from . import BASE_URL
from .course_about import CourseAboutPage as EdXCourseAboutPage
from .pay_and_verify import FakePaymentPage as EdXFakePaymentPage

from .ga_dashboard import DashboardPage as GaDashboradPage


class AdvancedCourseChoosePage(PageObject):

    def __init__(self, browser, course_id):
        super(AdvancedCourseChoosePage, self).__init__(browser)
        self.course_id = course_id

    @property
    def url(self):
        return '{base}/advanced_course/choose/{course_id}/'.format(
            base=BASE_URL, course_id=self.course_id
        )

    def is_browser_on_page(self):
        return self.browser.title.startswith("Enroll mode selection")

    def _get_face_to_face_element(self, selector):
        elements = self.q(css='.course_select_area').results
        for element in elements:
            if 'Face 2 Face Classroom (Fee-charging)' in element.find_element_by_css_selector('h3').text:
                return element.find_element_by_css_selector(selector)
        raise Exception("No face_to_face element was found on the choose page")

    def _get_online_element(self, selector):
        elements = self.q(css='.course_select_area').results
        for element in elements:
            if 'Online Course (Free of charge)' in element.find_element_by_css_selector('h3').text:
                return element.find_element_by_css_selector(selector)
        raise Exception("No online element was found on the choose page")

    def has_face_to_face_track(self):
        try:
            self._get_face_to_face_element('h3')
            return True
        except NoSuchElementException:
            return False

    def has_online_track(self):
        try:
            self._get_online_element('h3')
            return True
        except NoSuchElementException:
            return False

    def show_face_to_face_courses_page(self):
        self._get_face_to_face_element('.t_btn').click()
        return AdvancedF2FCoursesPage(self.browser, self.course_id).wait_for_page()


class AdvancedCoursesPage(PageObject):

    url = None

    def __init__(self, browser, course_id):
        super(AdvancedCoursesPage, self).__init__(browser)
        self.course_id = course_id

    def is_browser_on_page(self):
        return self.q(css='.ticket_page_wrap .course_list').present

    def _get_element_in_course_summary(self, course_name, selector):
        course_listing = self.q(css='ul.course_list li').filter(lambda el: course_name in el.text).results
        if course_listing:
            el = course_listing[0]
            return el.find_element_by_css_selector(selector)
        else:
            raise NoSuchElementException("No course named {} was found on the advanced course summaries".format(course_name))

    def _get_element_in_course_detail(self, course_name, selector, multi=False):
        course_listing = self.q(css='.course_info').filter(lambda el: course_name in el.text).results
        if course_listing:
            el = course_listing[0]
            if multi:
                return el.find_elements_by_css_selector(selector)
            else:
                return el.find_element_by_css_selector(selector)
        else:
            raise NoSuchElementException("No course named {} was found on the advanced course details".format(course_name))

    def get_error_message(self):
        elements = self.q(css='.purchase_error p')
        return ' '.join([element.text for element in elements])

    def check_course_name(self, course_name):
        try:
            return (
                self._get_element_in_course_summary(course_name, '.title').text == course_name and
                self._get_element_in_course_detail(course_name, 'h4').text.endswith(course_name)
            )
        except NoSuchElementException:
            return False

    def check_course_button(self, course_name, btn_text):
        try:
            if btn_text == 'Subscribe':
                btn_summary = self._get_element_in_course_summary(course_name, '.t_btn.apply')
                btn_detail = self._get_element_in_course_detail(course_name, '.t_btn.apply')
            else:
                btn_summary = self._get_element_in_course_summary(course_name, '.t_btn.disabled')
                btn_detail = self._get_element_in_course_detail(course_name, '.t_btn.disabled')
            return btn_summary.text == btn_text and btn_detail.text == btn_text
        except NoSuchElementException:
            return False

    def get_course_content(self, course_name):
        openning_time = self._get_element_in_course_detail(course_name, '.course-opening-time').text
        try:
            other_content = self._get_element_in_course_detail(course_name, '.course-other-content').text
        except NoSuchElementException:
            other_content = None

        tickets = self._get_element_in_course_detail(course_name, '.course-ticket', multi=True)

        return {
            'description': self._get_element_in_course_detail(course_name, '.course-description').text,
            'place_name': self._get_element_in_course_detail(course_name, '.course-place').text,
            'tickets': [t.text for t in tickets],
            'place_link': self._get_element_in_course_detail(course_name, '.course-place a').get_attribute('href'),
            'place_address': self._get_element_in_course_detail(course_name, '.course-address').text,
            'place_access': self._get_element_in_course_detail(course_name, '.course-access').text,
            'start_date': ' '.join(openning_time.split()[:2]),
            'start_time': openning_time.split(' ', 2)[2].split('-')[0].strip(),
            'end_time': openning_time.split(' ', 2)[2].split('-')[1].strip(),
            'other_content': other_content,
        }

    def subscribe_by_summary(self, course_name):
        self._get_element_in_course_summary(course_name, '.t_btn.apply').click()
        return AdvancedCourseChooseTicketPage(self.browser, self.course_id).wait_for_page()

    def subscribe_by_detail(self, course_name):
        self._get_element_in_course_detail(course_name, '.t_btn.apply').click()
        return AdvancedCourseChooseTicketPage(self.browser, self.course_id).wait_for_page()

    def is_displayed_toggle_area(self, course_name):
        return self._get_element_in_course_detail(course_name, '.toggleArea').is_displayed()

    def toggle_show_more(self, course_name):
        """
        Open or close toggle area.
        """
        is_opened = self.is_displayed_toggle_area(course_name)
        self._get_element_in_course_detail(course_name, '.show_more').click()

        if is_opened:
            self.wait_for(lambda: not self.is_displayed_toggle_area(course_name), 'Toggle area did not close')
        else:
            self.wait_for(lambda: self.is_displayed_toggle_area(course_name), 'Toggle area did not open')


class AdvancedF2FCoursesPage(AdvancedCoursesPage):

    @property
    def url(self):
        return '{base}/advanced_course/{course_id}/face_to_face'.format(
            base=BASE_URL, course_id=self.course_id
        )


class AdvancedCourseChooseTicketPage(PageObject):

    def __init__(self, browser, course_id):
        super(AdvancedCourseChooseTicketPage, self).__init__(browser)
        self.course_id = course_id

    url = None

    def is_browser_on_page(self):
        return self.q(css='.ticket_page_wrap .items').present

    def _get_element_in_ticket(self, ticket_name, selector):
        ticket_listing = self.q(css='.items').filter(lambda el: ticket_name in el.text).results
        if ticket_listing:
            el = ticket_listing[0]
            return el.find_element_by_css_selector(selector)
        else:
            raise NoSuchElementException("No ticket named {} was found on the tickets".format(ticket_name))

    def check_ticket_name(self, ticket_name):
        try:
            return self._get_element_in_ticket(ticket_name, 'h4').text == ticket_name
        except NoSuchElementException:
            return False

    def get_ticket_content(self, ticket_name):
        def _is_end_of_sale():
            try:
                self._get_element_in_ticket(ticket_name, '.t_btn.disabled')
                return True
            except NoSuchElementException:
                return False
        is_end_of_sale = _is_end_of_sale()
        price = self._get_element_in_ticket(ticket_name, '.t_btn.apply').text[1:] if not is_end_of_sale else ''
        return {
            'description': self._get_element_in_ticket(ticket_name, 'p').text,
            'price': price,
            'is_end_of_sale': is_end_of_sale,
        }

    def purchase(self, ticket_name):
        self._get_element_in_ticket(ticket_name, '.t_btn.apply').click()

        self.wait_for_ajax()
        return FakePaymentPage(self.browser).wait_for_page()


class AdvancedCourseReceiptPage(PageObject):

    def __init__(self, browser):
        super(AdvancedCourseReceiptPage, self).__init__(browser)

    url = None

    def is_browser_on_page(self):
        return self.q(css='.ticket_page_wrap .receipt_area').present

    def has_thanks_message(self):
        return self.q(css='#thanks-msg').present

    def show_courses_page(self):
        btn = self.q(css='.t_btn')[0]
        course_id = btn.get_attribute('href').split('/')[-2]
        btn.click()

        # Now, only returns f2f page
        return AdvancedF2FCoursesPage(self.browser, course_id).wait_for_page()

    def show_dashboard_page(self):
        self.q(css='.t_btn')[1].click()

        return DashboardPage(self.browser).wait_for_page()

    def get_receipt_content(self):
        openning_time = self.q(css='#course-opening-time')[0].text
        return {
            'course_name': self.q(css='h3')[0].text,
            'ticket_name': self.q(css='#ticket-name')[0].text,
            'start_date': openning_time.splitlines()[0],
            'start_time': openning_time.splitlines()[1].split('-')[0].strip(),
            'end_time': openning_time.splitlines()[1].split('-')[1].strip(),
            'place_name': self.q(css='#course-place')[0].text,
            'price': self.q(css='#ticket-price')[0].text.split()[0][1:],
            'payment_method': self.q(css="#payment-method")[0].text,
        }

    def get_receipt_number(self):
        return self.q(css='#receipt-number')[0].text[1:]


class FakePaymentPage(EdXFakePaymentPage):

    def __init__(self, browser):
        super(FakePaymentPage, self).__init__(browser, None)

    url = BASE_URL + "/shoppingcart/payment_fake_gmo"

    def submit_payment(self, payment_method='card'):
        """Interact with the payment submission button."""
        self.q(css="input[value='Submit {}']".format(payment_method)).click()

        return AdvancedCourseReceiptPage(self.browser).wait_for_page()


class CourseAboutPage(EdXCourseAboutPage):

    def enroll(self):
        self.q(css='a.register').first.click()

        advanced_course_choose_page = AdvancedCourseChoosePage(self.browser, self.course_id)
        advanced_course_choose_page.wait_for_page()
        return advanced_course_choose_page


class DashboardPage(GaDashboradPage):

    def has_advanced_course_upsell_message(self, course_name):
        try:
            element = self._get_element_in_course(course_name, ".advanced-course-message")
            return element.is_displayed()
        except NoSuchElementException:
            return False

    def wait_for_upsell_invisibility(self, course_name):
        _check_func = lambda: not self.has_advanced_course_upsell_message(course_name)
        self.wait_for(_check_func, 'Upsell message did not close')

    def has_advanced_course_purchased_message(self, course_name):
        try:
            self._get_element_in_course(course_name, ".advanced-course-information-label.purchased")
            return True
        except NoSuchElementException:
            return False

    def show_advanced_courses_page_by_upsell(self, course_name):
        btn = self._get_element_in_course(course_name, ".advanced-course-message .btn")
        course_id = btn.get_attribute('href').split('/')[-2]
        btn.click()
        return AdvancedF2FCoursesPage(self.browser, course_id).wait_for_page()

    def show_advanced_courses_page_by_information(self, course_name):
        btn = self._get_element_in_course(course_name, '.advanced-course-information-action')
        course_id = btn.get_attribute('href').split('/')[-2]
        btn.click()
        return AdvancedF2FCoursesPage(self.browser, course_id).wait_for_page()

    def show_receipt_page(self, course_name):
        self._get_element_in_course(course_name, '.advanced-course-information-action').click()

        return AdvancedCourseReceiptPage(self.browser).wait_for_page()

    def close_upsell(self, course_name):
        self._get_element_in_course(course_name, '.advanced-course-message-close').click()

    def get_refund_info_message(self):
        return self.q(css='#refund-info')[0].text

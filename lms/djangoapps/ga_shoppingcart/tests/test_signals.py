from mock import patch

from django.test import TestCase

from opaque_keys.edx.keys import CourseKey
from shoppingcart.models import CertificateItem, Order
from student.models import CourseEnrollment
from student.tests.factories import UserFactory

from ga_shoppingcart.models import CertificateItemAdditionalInfo


def _get_tax(value):
    return int(value) * 5 / 100


class CertificateItemTest(TestCase):

    def _create_cert_item(self):
        course_id = CourseKey.from_string('course-v1:org+course+run')
        user = UserFactory.create()
        order = Order.get_cart_for_user(user)
        enrollment = CourseEnrollment.get_or_create_enrollment(user, course_id)
        _item = CertificateItem(
            order=order,
            user=user,
            course_id=course_id,
            course_enrollment=enrollment,
            mode='no-id-professional'
        )
        _item.save()
        return _item

    def _assert_additional_info(self, item, tax):
        item_info = CertificateItemAdditionalInfo.objects.get(certificate_item=item)
        self.assertEqual(tax, item_info.tax)

    @patch('ga_shoppingcart.signals.get_tax', side_effect=_get_tax)
    def test_post_save(self, mock_get_tax):
        self.assertFalse(CertificateItemAdditionalInfo.objects.all().exists())

        self.assertEqual(0, mock_get_tax.call_count)
        items = [self._create_cert_item(), self._create_cert_item()]
        self.assertEqual(2, mock_get_tax.call_count)

        self.assertEqual(2, len(CertificateItemAdditionalInfo.objects.all()))

        for item in items:
            self._assert_additional_info(item, tax=0)

        items[0].unit_cost = 100
        items[0].save()
        self.assertEqual(3, mock_get_tax.call_count)

        self._assert_additional_info(items[0], tax=5)
        self._assert_additional_info(items[1], tax=0)

        items[1].delete()

        self.assertEqual(1, len(CertificateItemAdditionalInfo.objects.all()))
        self._assert_additional_info(items[0], tax=5)

from ga_daccount.models import DAccountNumber
from student.tests.factories import UserFactory
from django.test import TestCase
import base64


class DaccountTest(TestCase):

    def test_models_save(self):
        user = UserFactory.create()
        DAccountNumber.save_number(
            user=user,
            number='abc'
        )

        response_model = DAccountNumber.objects.filter(user=user).first()
        self.assertEqual('abc', base64.b64decode(response_model.number))

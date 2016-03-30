
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from student.tests.factories import UserFactory

from biz.djangoapps.ga_manager.middleware import BizAccessCheckMiddleware
from biz.djangoapps.ga_manager.tests.factories import ManagerFactory
from biz.djangoapps.util.tests.testcase import BizTestBase


class BizAccessCheckMiddlewareTest(BizTestBase):

    def setUp(self):
        super(BizAccessCheckMiddlewareTest, self).setUp()

        self.request = RequestFactory().request()

    def test_process_request_with_biz_user(self):
        user = UserFactory.create()
        ManagerFactory.create(
            org=self.gacco_organization, user=user, permissions=[self.platformer_permission]
        )
        self.request.user = user
        BizAccessCheckMiddleware().process_request(self.request)
        self.assertTrue(self.request.biz_accessible)

    def test_process_request_with_not_biz_user(self):
        self.request.user = UserFactory.create()
        BizAccessCheckMiddleware().process_request(self.request)
        self.assertFalse(self.request.biz_accessible)

    def test_process_request_with_anonymous_user(self):
        self.request.user = AnonymousUser()
        BizAccessCheckMiddleware().process_request(self.request)
        self.assertFalse(self.request.biz_accessible)

    def test_process_request_no_user_in_request(self):
        BizAccessCheckMiddleware().process_request(self.request)
        self.assertFalse(self.request.biz_accessible)

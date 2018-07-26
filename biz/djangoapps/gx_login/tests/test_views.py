# -*- coding: utf-8 -*-
"""
Test for login feature
"""
import ddt

from django.core.urlresolvers import reverse
from django.test.client import Client

from student.tests.factories import UserFactory

from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase
from biz.djangoapps.ga_manager.tests.factories import ManagerFactory


@ddt.ddt
class LoginTest(BizContractTestBase):
    """
    Test Class for gx_login
    """
    def setUp(self):
        super(BizContractTestBase, self).setUp()
        self.user_gacco_staff = UserFactory(username='gacco_staff', email="gacco_staff@example.com",
                                            is_staff=True, is_superuser=True)
        self.user_gacco_staff_password = 'test'

        self.user_aggregator = UserFactory(username='aggregator', email="aggregator@example.com")
        self.user_aggregator_password = 'test'
        self.manager_aggregator = ManagerFactory.create(org=self.gacco_organization, user=self.user_aggregator,
                                                        permissions=[self.aggregator_permission])

        self.user_director = UserFactory(username='director', email="director@example.com")
        self.user_director_password = 'test'
        self.manager_director = ManagerFactory.create(org=self.gacco_organization, user=self.user_director,
                                                      permissions=[self.director_permission])

        self.user_manager = UserFactory(username='manager', email="manager@example.com")
        self.user_manager_password = 'test'
        self.manager_manager = ManagerFactory.create(org=self.gacco_organization, user=self.user_manager,
                                                     permissions=[self.manager_permission])

        self.user_platformer = UserFactory(username='platformer', email="platformer@example.com")
        self.user_platformer_password = 'test'
        self.manager_platformer = ManagerFactory.create(org=self.gacco_organization, user=self.user_platformer,
                                                        permissions=[self.platformer_permission])

    @property
    def _url_index(self):
        return reverse("biz:admin:index")

    def _create_base_form_param(self, email='sample@example.com', password='password', next_url=''):
        return {
            'email': email,
            'password': password,
            'next': next_url,
        }

    def test_login_email_length_err(self):
        """
        Tests email length error
        :return:
        """
        param = self._create_base_form_param()
        param['email'] = ''
        response = self.client.post(self._url_index, param)
        self.assertEqual(200, response.status_code)

    def test_login_password_length_err(self):
        """
        Tests password length error
        :return:
        """
        param = self._create_base_form_param()
        param['password'] = ''
        response = self.client.post(self._url_index, param)
        self.assertEqual(200, response.status_code)

    def test_login_active_user_get_redirect(self):
        """
        Tests login active user with get method, and then redirect
        :return:
        """
        # init
        self.setup_user()
        c = Client()
        username = self.user_gacco_staff.username
        email = self.user_gacco_staff.email
        password = self.user_gacco_staff_password

        # redirect to default URL
        c.login(username=username, password=password)
        response = self.client.get(self._url_index)
        self.assertEqual(302, response.status_code)

        # redirect to default URL
        c.login(username=username, password=password)
        param = self._create_base_form_param(email, password, reverse('biz:index'))
        response = self.client.get(self._url_index, param)
        self.assertEqual(302, response.status_code)

    def test_login_active_user_post_auth_err(self):
        """
        Tests login active user with post method
        :return:
        """
        # init
        c = Client()

        # post LOGIN_ERROR_AUTH
        username = self.user_gacco_staff.username
        email = self.user_gacco_staff.email
        password = self.user_gacco_staff_password
        c.login(username=username, password=password)
        param = self._create_base_form_param(email, password)
        response = self.client.post(self._url_index, param)
        self.assertEqual(200, response.status_code)

    def test_login_active_user_post_aggregator(self):
        """
        Tests aggregator login active user with post method
        :return:
        """
        # init
        c = Client()

        # post LOGIN_ADMIN: aggregator, and then redirect
        username = self.user_aggregator.username
        email = self.user_aggregator.email
        password = self.user_aggregator_password
        c.login(username=username, password=password)
        param = self._create_base_form_param(email, password)
        response = self.client.post(self._url_index, param)
        self.assertEqual(302, response.status_code)

    def test_login_active_user_post_director(self):
        """
        Tests director login active user with post method
        :return:
        """
        # init
        c = Client()

        # post LOGIN_ADMIN: director, and then redirect
        username = self.user_director.username
        email = self.user_director.email
        password = self.user_director_password
        c.login(username=username, password=password)
        param = self._create_base_form_param(email, password)
        response = self.client.post(self._url_index, param)
        self.assertEqual(302, response.status_code)

    def test_login_active_user_post_manager(self):
        """
        Tests manager login active user with post method
        :return:
        """
        # init
        c = Client()

        # post LOGIN_ADMIN: manager, and then redirect
        username = self.user_manager.username
        email = self.user_manager.email
        password = self.user_manager_password
        c.login(username=username, password=password)
        param = self._create_base_form_param(email, password)
        response = self.client.post(self._url_index, param)
        self.assertEqual(302, response.status_code)

    def test_login_active_user_post_platformer(self):
        """
        Tests login platformaer active user with post method
        :return:
        """
        # init
        c = Client()

        # post LOGIN_ADMIN: platformer, and then redirect
        username = self.user_platformer.username
        email = self.user_platformer.email
        password = self.user_platformer_password
        c.login(username=username, password=password)
        param = self._create_base_form_param(email, password)
        response = self.client.post(self._url_index, param)
        self.assertEqual(302, response.status_code)

    def test_login_active_user_post_platformer_next_url(self):
        """
        Tests login platformaer active user with post method next url
        :return:
        """
        # init
        c = Client()

        # post LOGIN_ADMIN: platformer, and then redirect
        username = self.user_platformer.username
        email = self.user_platformer.email
        password = self.user_platformer_password
        c.login(username=username, password=password)
        param = self._create_base_form_param(email, password, reverse('biz:index'))
        response = self.client.post(self._url_index, param)
        self.assertEqual(302, response.status_code)

    def test_login_active_user_post_platformer_remember(self):
        """
        Tests login platformaer active user with post method next url
        :return:
        """
        # init
        c = Client()

        # post LOGIN_ADMIN: platformer, and then redirect
        username = self.user_platformer.username
        email = self.user_platformer.email
        password = self.user_platformer_password
        c.login(username=username, password=password)
        param = self._create_base_form_param(email, password)
        param['remember'] = 1
        response = self.client.post(self._url_index, param)
        self.assertEqual(302, response.status_code)

    def test_login_active_user_post_password_err(self):
        """
        Tests login password error
        :return:
        """
        # init
        c = Client()

        # post LOGIN_ADMIN: password error
        username = self.user_platformer.username
        email = self.user_platformer.email
        password = "*invalid*password*string*"
        c.login(username=username, password=password)
        param = self._create_base_form_param(email, password)
        response = self.client.post(self._url_index, param)
        self.assertEqual(200, response.status_code)

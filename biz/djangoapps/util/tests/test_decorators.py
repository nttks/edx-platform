"""
Tests for decorators
"""
import ddt
from mock import patch

from django.core.management.base import CommandError
from django.core.urlresolvers import reverse
from django.test import RequestFactory, TestCase
from django.utils.crypto import get_random_string

from biz.djangoapps.ga_contract.models import (
    CONTRACT_TYPE_PF, CONTRACT_TYPE_OWNERS, CONTRACT_TYPE_OWNER_SERVICE, CONTRACT_TYPE_GACCO_SERVICE,
)
from biz.djangoapps.ga_contract.tests.factories import ContractFactory, ContractDetailFactory
from biz.djangoapps.ga_manager.tests.factories import ManagerFactory
from biz.djangoapps.ga_organization.tests.factories import OrganizationFactory
from biz.djangoapps.util import cache_utils
from biz.djangoapps.util.decorators import check_course_selection, require_survey, handle_command_exception
from biz.djangoapps.util.tests.testcase import BizTestBase
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@check_course_selection
def check_course_selection_target(request):
    return "success"


class CheckCourseSelectionTestBase(BizTestBase, ModuleStoreTestCase):
    """check_course_selection test base"""

    def setUp(self):
        super(CheckCourseSelectionTestBase, self).setUp()

        self.request = RequestFactory().request()
        self.request.user = UserFactory.create()

        self.course = CourseFactory.create()

        patcher_render_to_string = patch('biz.djangoapps.util.decorators.render_to_string')
        self.mock_render_to_string = patcher_render_to_string.start()
        self.addCleanup(patcher_render_to_string.stop)

        patcher_render_to_response = patch('biz.djangoapps.util.decorators.render_to_response')
        self.mock_render_to_response = patcher_render_to_response.start()
        self.addCleanup(patcher_render_to_response.stop)

        patcher_log = patch('biz.djangoapps.util.decorators.log')
        self.mock_log = patcher_log.start()
        self.addCleanup(patcher_log.stop)

        patcher_messages = patch('biz.djangoapps.util.decorators.messages')
        self.mock_messages = patcher_messages.start()
        self.addCleanup(patcher_messages.stop)

    def _save_organization(self):
        return OrganizationFactory.create(
            org_name=get_random_string(8),
            org_code=get_random_string(8),
            creator_org=self.gacco_organization,
            created_by=self.request.user,
        )

    def _save_manager_for_platformer(self, org):
        return self._save_manager(org, [self.platformer_permission])

    def _save_manager_for_aggregator(self, org):
        return self._save_manager(org, [self.aggregator_permission])

    def _save_manager_for_director(self, org):
        return self._save_manager(org, [self.director_permission])

    def _save_manager_for_manager(self, org):
        return self._save_manager(org, [self.manager_permission])

    def _save_manager(self, org, permissions):
        return ManagerFactory.create(
            org=org,
            user=self.request.user,
            permissions=permissions,
        )

    def _save_contract_for_pf(self, contractor_org, owner_org):
        return self._save_contract(CONTRACT_TYPE_PF[0], contractor_org, owner_org)

    def _save_contract_for_owners(self, contractor_org, owner_org):
        return self._save_contract(CONTRACT_TYPE_OWNERS[0], contractor_org, owner_org)

    def _save_contract_for_gacco_service(self, contractor_org, owner_org):
        return self._save_contract(CONTRACT_TYPE_GACCO_SERVICE[0], contractor_org, owner_org)

    def _save_contract_for_owner_service(self, contractor_org, owner_org):
        return self._save_contract(CONTRACT_TYPE_OWNER_SERVICE[0], contractor_org, owner_org)

    def _save_contract(self, contract_type, contractor_org, owner_org):
        return ContractFactory.create(
            contract_name=get_random_string(8),
            contract_type=contract_type,
            invitation_code=get_random_string(8),
            contractor_organization=contractor_org,
            owner_organization=owner_org,
            created_by=self.request.user,
        )

    def _save_contract_detail(self, contract, course_id):
        return ContractDetailFactory.create(
            contract=contract,
            course_id=course_id,
        )

    def _index_view(self):
        return reverse('biz:index')

    def _organization_view(self):
        return reverse('biz:organization:index')

    def _contract_view(self):
        return reverse('biz:contract:index')

    def _manager_view(self):
        return reverse('biz:manager:index')

    def _course_operation_view(self, course_id):
        return reverse('biz:course_operation:dashboard', kwargs={'course_id': course_id})

    def _achievement_view(self):
        return reverse('biz:achievement:index')


class CheckCourseSelectionForPlatformerTest(CheckCourseSelectionTestBase):
    """check_course_selection test for Platformer"""

    def _save_default_manager(self, org):
        return self._save_manager_for_platformer(org)

    def _setup_default(self):
        self.org = self._save_organization()
        self.manager = self._save_default_manager(self.org)

    def test_with_only_one_org(self):
        self.path = self._index_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))
        self.assertEqual((self.org.id, None, None), cache_utils.get_course_selection(self.request.user))
        self.assertEqual(self.org.id, self.request.current_organization.id)
        self.assertEqual(self.manager.id, self.request.current_manager.id)
        self.assertIsNone(self.request.current_contract)
        self.assertIsNone(self.request.current_course)
        self.assertIdsOfListEqual([self.org], self.request.selection_organizations)
        self.assertIdsOfListEqual([], self.request.selection_contracts)
        self.assertIdsOfListEqual([], self.request.selection_contract_details)

    def test_with_no_manager(self):
        self.path = self._index_view()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with("User(id={}) has no manager model.".format(self.request.user.id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_with_two_orgs(self):
        self.path = self._index_view()
        self._setup_default()
        org2 = self._save_organization()
        manager2 = self._save_default_manager(org2)
        # Call test target
        check_course_selection_target(self.request)
        self.mock_log.info.assert_called_with("Redirect to org_not_specified page because org_id is not specified.")
        self.mock_messages.error.assert_called_with(self.request, "Organization is not specified.")
        self.mock_render_to_response.assert_called_with('ga_course_selection/org_not_specified.html')

    def test_with_two_orgs_if_cache_exists(self):
        self.path = self._index_view()
        self._setup_default()
        org2 = self._save_organization()
        manager2 = self._save_default_manager(org2)
        cache_utils.set_course_selection(self.request.user, org2.id, None, None)
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))
        self.assertEqual((org2.id, None, None), cache_utils.get_course_selection(self.request.user))

    def test_when_org_not_found(self):
        self.path = self._index_view()
        self._setup_default()
        invalid_org_id = 99999
        cache_utils.set_course_selection(self.request.user, invalid_org_id, None, None)
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with("No such organization(id={}) was found.".format(invalid_org_id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_when_manager_not_found(self):
        self.path = self._index_view()
        self._setup_default()
        org2 = self._save_organization()
        cache_utils.set_course_selection(self.request.user, org2.id, None, None)
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "User(id={}) has no permission to access to the specified organization(id={}).".format(
                self.request.user.id, org2.id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_organization_feature(self):
        self.request.path = self._organization_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))

    def test_contract_feature(self):
        self.request.path = self._contract_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))

    def test_manager_feature(self):
        self.request.path = self._manager_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))

    def test_course_operation_feature(self):
        self.request.path = self._course_operation_view(unicode(self.course.id))
        self._setup_default()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to handle '{}' feature.".format(self.manager.id, 'course_operation'))
        self.assertEqual(403, response.status_code)

    def test_achievement_feature(self):
        self.request.path = self._achievement_view()
        self._setup_default()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to handle '{}' feature.".format(self.manager.id, 'achievement'))
        self.assertEqual(403, response.status_code)


class CheckCourseSelectionForAggregatorTest(CheckCourseSelectionTestBase):
    """check_course_selection test for Aggregator"""

    def _save_default_manager(self, org):
        return self._save_manager_for_aggregator(org)

    def _save_default_contract(self, contractor_org, owner_org):
        return self._save_contract_for_owners(contractor_org, owner_org)

    def _setup_default(self):
        self.org = self._save_organization()
        self.org2 = self._save_organization()
        self.manager = self._save_default_manager(self.org)
        self.contract = self._save_default_contract(self.org, self.org2)

    def test_with_only_one_org_and_contract(self):
        self.path = self._index_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))
        self.assertEqual((self.org.id, self.contract.id, None), cache_utils.get_course_selection(self.request.user))
        self.assertEqual(self.org.id, self.request.current_organization.id)
        self.assertEqual(self.manager.id, self.request.current_manager.id)
        self.assertEqual(self.contract.id, self.request.current_contract.id)
        self.assertIsNone(self.request.current_course)
        self.assertIdsOfListEqual([self.org], self.request.selection_organizations)
        self.assertIdsOfListEqual([self.contract], self.request.selection_contracts)
        self.assertIdsOfListEqual([], self.request.selection_contract_details)

    def test_with_no_manager(self):
        self.path = self._index_view()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with("User(id={}) has no manager model.".format(self.request.user.id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_with_two_orgs(self):
        self.path = self._index_view()
        self._setup_default()
        manager2 = self._save_default_manager(self.org2)
        # Call test target
        check_course_selection_target(self.request)
        self.mock_log.info.assert_called_with("Redirect to org_not_specified page because org_id is not specified.")
        self.mock_messages.error.assert_called_with(self.request, "Organization is not specified.")
        self.mock_render_to_response.assert_called_with('ga_course_selection/org_not_specified.html')

    def test_with_two_contracts(self):
        self.path = self._index_view()
        self._setup_default()
        contract2 = self._save_default_contract(self.org, self.org2)
        # Call test target
        check_course_selection_target(self.request)
        self.mock_log.info.assert_called_with(
            "Redirect to contract_not_specified page because contract_id is not specified.")
        self.mock_messages.error.assert_called_with(self.request, "Contract is not specified.")
        self.mock_render_to_response.assert_called_with('ga_course_selection/contract_not_specified.html')

    def test_with_two_orgs_and_contracts_if_cache_exists(self):
        self.path = self._index_view()
        self._setup_default()
        manager2 = self._save_default_manager(self.org2)
        contract2 = self._save_default_contract(self.org, self.org2)
        cache_utils.set_course_selection(self.request.user, self.org.id, contract2.id, None)
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))
        self.assertEqual((self.org.id, contract2.id, None), cache_utils.get_course_selection(self.request.user))

    def test_with_owner_and_pf_contracts(self):
        self.path = self._index_view()
        self._setup_default()
        contract2 = self._save_contract_for_pf(self.org, self.org2)
        contract_detail = self._save_contract_detail(contract2, self.course.id)
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))
        self.assertEqual((self.org.id, self.contract.id, None), cache_utils.get_course_selection(self.request.user))

    def test_when_org_not_found(self):
        self.path = self._index_view()
        self._setup_default()
        invalid_org_id = 99999
        cache_utils.set_course_selection(self.request.user, invalid_org_id, self.contract.id, None)
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with("No such organization(id={}) was found.".format(invalid_org_id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_when_manager_not_found(self):
        self.path = self._index_view()
        self._setup_default()
        cache_utils.set_course_selection(self.request.user, self.org2.id, self.contract.id, None)
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "User(id={}) has no permission to access to the specified organization(id={}).".format(
                self.request.user.id, self.org2.id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_when_contract_not_found(self):
        self.path = self._index_view()
        self._setup_default()
        invalid_contract_id = 99999
        cache_utils.set_course_selection(self.request.user, self.org.id, invalid_contract_id, None)
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to access to the specified contract(id={}).".format(
                self.manager.id, invalid_contract_id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_organization_feature(self):
        self.request.path = self._organization_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))

    def test_organization_feature_with_no_contract_id(self):
        self.request.path = self._organization_view()
        self.org = self._save_organization()
        self.manager = self._save_default_manager(self.org)
        # Call test target
        check_course_selection_target(self.request)
        self.mock_log.info.assert_called_with(
            "Redirect to contract_not_specified page because contract_id is not specified.")
        self.mock_messages.error.assert_called_with(self.request, "Contract is not specified.")
        self.mock_render_to_response.assert_called_with('ga_course_selection/contract_not_specified.html')

    def test_contract_feature(self):
        self.request.path = self._contract_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))

    def test_contract_feature_with_no_contract_id(self):
        self.request.path = self._contract_view()
        self.org = self._save_organization()
        self.manager = self._save_default_manager(self.org)
        # Call test target
        check_course_selection_target(self.request)
        self.mock_log.info.assert_called_with(
            "Redirect to contract_not_specified page because contract_id is not specified.")
        self.mock_messages.error.assert_called_with(self.request, "Contract is not specified.")
        self.mock_render_to_response.assert_called_with('ga_course_selection/contract_not_specified.html')

    def test_manager_feature(self):
        self.request.path = self._manager_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))

    def test_manager_feature_with_no_contract_id(self):
        self.request.path = self._manager_view()
        self.org = self._save_organization()
        self.manager = self._save_default_manager(self.org)
        # Call test target
        check_course_selection_target(self.request)
        self.mock_log.info.assert_called_with(
            "Redirect to contract_not_specified page because contract_id is not specified.")
        self.mock_messages.error.assert_called_with(self.request, "Contract is not specified.")
        self.mock_render_to_response.assert_called_with('ga_course_selection/contract_not_specified.html')

    def test_course_operation_feature(self):
        self.request.path = self._course_operation_view(unicode(self.course.id))
        self._setup_default()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to handle '{}' feature.".format(self.manager.id, 'course_operation'))
        self.assertEqual(403, response.status_code)

    def test_achievement_feature(self):
        self.request.path = self._achievement_view()
        self._setup_default()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to handle '{}' feature.".format(self.manager.id, 'achievement'))
        self.assertEqual(403, response.status_code)


class CheckCourseSelectionForDirectorTest(CheckCourseSelectionTestBase):
    """check_course_selection test for Director"""

    def _save_default_manager(self, org):
        return self._save_manager_for_director(org)

    def _save_default_contract(self, contractor_org, owner_org):
        return self._save_contract_for_pf(contractor_org, owner_org)

    def _setup_default(self):
        self.org = self._save_organization()
        self.org2 = self._save_organization()
        self.manager = self._save_default_manager(self.org)
        self.contract = self._save_default_contract(self.org, self.org2)
        self.contract_detail = self._save_contract_detail(self.contract, self.course.id)

    def test_with_only_one_org_and_contract_and_course(self):
        self.path = self._index_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))
        self.assertEqual(
            (self.org.id, self.contract.id, unicode(self.contract_detail.course_id)),
            cache_utils.get_course_selection(self.request.user))
        self.assertEqual(self.org.id, self.request.current_organization.id)
        self.assertEqual(self.manager.id, self.request.current_manager.id)
        self.assertEqual(self.contract.id, self.request.current_contract.id)
        self.assertEqual(self.contract_detail.course_id, self.request.current_course.id)
        self.assertIdsOfListEqual([self.org], self.request.selection_organizations)
        self.assertIdsOfListEqual([self.contract], self.request.selection_contracts)
        self.assertIdsOfListEqual([self.contract_detail], self.request.selection_contract_details)

    def test_with_no_manager(self):
        self.path = self._index_view()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with("User(id={}) has no manager model.".format(self.request.user.id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_with_two_orgs(self):
        self.path = self._index_view()
        self._setup_default()
        manager2 = self._save_default_manager(self.org2)
        # Call test target
        check_course_selection_target(self.request)
        self.mock_log.info.assert_called_with("Redirect to org_not_specified page because org_id is not specified.")
        self.mock_messages.error.assert_called_with(self.request, "Organization is not specified.")
        self.mock_render_to_response.assert_called_with('ga_course_selection/org_not_specified.html')

    def test_with_two_contracts(self):
        self.path = self._index_view()
        self._setup_default()
        contract2 = self._save_default_contract(self.org, self.org2)
        # Call test target
        check_course_selection_target(self.request)
        self.mock_log.info.assert_called_with(
            "Redirect to contract_not_specified page because contract_id is not specified.")
        self.mock_messages.error.assert_called_with(self.request, "Contract is not specified.")
        self.mock_render_to_response.assert_called_with('ga_course_selection/contract_not_specified.html')

    def test_with_two_courses(self):
        self.path = self._index_view()
        self._setup_default()
        course2 = CourseFactory.create()
        self.contract_detail2 = self._save_contract_detail(self.contract, course2.id)
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))
        self.assertEqual((self.org.id, self.contract.id, None), cache_utils.get_course_selection(self.request.user))

    def test_with_two_orgs_and_contracts_and_courses_if_cache_exists(self):
        self.path = self._index_view()
        self._setup_default()
        manager2 = self._save_default_manager(self.org2)
        contract2 = self._save_default_contract(self.org, self.org2)
        course2 = CourseFactory.create()
        self.contract_detail2 = self._save_contract_detail(self.contract, course2.id)
        cache_utils.set_course_selection(self.request.user, self.org.id, self.contract.id, unicode(course2.id))
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))
        self.assertEqual(
            (self.org.id, self.contract.id, unicode(course2.id)), cache_utils.get_course_selection(self.request.user))

    def test_with_owner_and_pf_contracts(self):
        self.path = self._index_view()
        self._setup_default()
        contract2 = self._save_contract_for_owners(self.org, self.org2)
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))
        self.assertEqual((self.org.id, self.contract.id, unicode(self.contract_detail.course_id)),
                         cache_utils.get_course_selection(self.request.user))

    def test_when_org_not_found(self):
        self.path = self._index_view()
        self._setup_default()
        invalid_org_id = 99999
        cache_utils.set_course_selection(self.request.user, invalid_org_id, self.contract.id, unicode(self.course.id))
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with("No such organization(id={}) was found.".format(invalid_org_id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_when_manager_not_found(self):
        self.path = self._index_view()
        self._setup_default()
        cache_utils.set_course_selection(self.request.user, self.org2.id, self.contract.id, unicode(self.course.id))
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "User(id={}) has no permission to access to the specified organization(id={}).".format(
                self.request.user.id, self.org2.id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_when_contract_not_found(self):
        self.path = self._index_view()
        self._setup_default()
        invalid_contract_id = 99999
        cache_utils.set_course_selection(self.request.user, self.org.id, invalid_contract_id, unicode(self.course.id))
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to access to the specified contract(id={}).".format(
                self.manager.id, invalid_contract_id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_when_course_not_found(self):
        self.path = self._index_view()
        self._setup_default()
        invalid_course_id = 'invalid_course_id'
        cache_utils.set_course_selection(self.request.user, self.org.id, self.contract.id, invalid_course_id)
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "No such course was found in modulestore. course_id={}".format(invalid_course_id))
        self.assertEqual(403, response.status_code)
        self.assertEqual((None, None, None), cache_utils.get_course_selection(self.request.user))

    def test_organization_feature(self):
        self.request.path = self._organization_view()
        self._setup_default()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to handle '{}' feature.".format(self.manager.id, 'organization'))
        self.assertEqual(403, response.status_code)

    def test_contract_feature(self):
        self.request.path = self._contract_view()
        self._setup_default()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to handle '{}' feature.".format(self.manager.id, 'contract'))
        self.assertEqual(403, response.status_code)

    def test_manager_feature(self):
        self.request.path = self._manager_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))

    def test_course_operation_feature(self):
        self.request.path = self._course_operation_view(unicode(self.course.id))
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))

    def test_course_operation_feature_with_no_course_id(self):
        self.request.path = self._course_operation_view(unicode(self.course.id))
        self.org = self._save_organization()
        self.org2 = self._save_organization()
        self.manager = self._save_default_manager(self.org)
        self.contract = self._save_default_contract(self.org, self.org2)
        # Call test target
        check_course_selection_target(self.request)
        self.mock_log.info.assert_called_with(
            "Redirect to course_not_specified page because course_id is not specified.")
        self.mock_messages.error.assert_called_with(self.request, "Course is not specified.")
        self.mock_render_to_response.assert_called_with('ga_course_selection/course_not_specified.html')

    def test_achievement_feature(self):
        self.request.path = self._achievement_view()
        self._setup_default()
        # Call test target
        self.assertEqual('success', check_course_selection_target(self.request))

    def test_achievement_feature_with_no_course_id(self):
        self.request.path = self._achievement_view()
        self.org = self._save_organization()
        self.org2 = self._save_organization()
        self.manager = self._save_default_manager(self.org)
        self.contract = self._save_default_contract(self.org, self.org2)
        # Call test target
        check_course_selection_target(self.request)
        self.mock_log.info.assert_called_with(
            "Redirect to course_not_specified page because course_id is not specified.")
        self.mock_messages.error.assert_called_with(self.request, "Course is not specified.")
        self.mock_render_to_response.assert_called_with('ga_course_selection/course_not_specified.html')


class CheckCourseSelectionForManagerTest(CheckCourseSelectionForDirectorTest):
    """check_course_selection test for Manager"""

    def _save_default_manager(self, org):
        return self._save_manager_for_manager(org)

    def test_manager_feature(self):
        self.request.path = self._manager_view()
        self._setup_default()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to handle '{}' feature.".format(self.manager.id, 'manager'))
        self.assertEqual(403, response.status_code)

    def test_course_operation_feature(self):
        self.request.path = self._course_operation_view(unicode(self.course.id))
        self._setup_default()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to handle '{}' feature.".format(self.manager.id, 'course_operation'))
        self.assertEqual(403, response.status_code)

    def test_course_operation_feature_with_no_course_id(self):
        self.request.path = self._course_operation_view(unicode(self.course.id))
        self._setup_default()
        # Call test target
        response = check_course_selection_target(self.request)
        self.mock_log.warning.assert_called_with(
            "Manager(id={}) has no permission to handle '{}' feature.".format(self.manager.id, 'course_operation'))
        self.assertEqual(403, response.status_code)


@require_survey
def require_survey_target(request, course_id):
    return "success"


@ddt.ddt
class RequireSurveyTest(BizTestBase, ModuleStoreTestCase):

    def setUp(self):
        super(RequireSurveyTest, self).setUp()

        self.request = RequestFactory().request()
        self.request.user = UserFactory.create()

        self.request.current_manager = ManagerFactory.create(
            org=self.gacco_organization,
            user=UserFactory.create(),
            permissions=[
                self.platformer_permission,
                self.aggregator_permission,
                self.director_permission,
                self.manager_permission,
            ]
        )

        self.request.current_contract = ContractFactory.create(
            contract_type=CONTRACT_TYPE_PF[0],
            contractor_organization=self.gacco_organization,
            owner_organization=self.gacco_organization,
            created_by=UserFactory.create()
        )

        self.course = CourseFactory.create()
        self.request.current_course = self.course

    def test_success(self):
        self.assertEqual('success', require_survey_target(self.request, course_id=unicode(self.course.id)))

    @ddt.data(CONTRACT_TYPE_PF[0], CONTRACT_TYPE_OWNERS[0], CONTRACT_TYPE_OWNER_SERVICE[0])
    def test_spoc(self, contract_type):
        self.request.current_contract.contract_type = contract_type
        self.assertEqual('success', require_survey_target(self.request, course_id=unicode(self.course.id)))

    @ddt.data(CONTRACT_TYPE_GACCO_SERVICE[0])
    def test_not_spoc(self, contract_type):
        self.request.current_contract.contract_type = contract_type
        with patch('biz.djangoapps.util.decorators.render_to_string', return_value=''):
            response = require_survey_target(self.request, course_id=unicode(self.course.id))
            self.assertEqual(403, response.status_code)

    @ddt.data('current_manager', 'current_contract', 'current_course')
    def test_missing_params(self, param):
        setattr(self.request, param, None)
        with patch('biz.djangoapps.util.decorators.render_to_string', return_value=''):
            response = require_survey_target(self.request, course_id=unicode(self.course.id))
            self.assertEqual(403, response.status_code)

    def test_no_can_handle_course_operation(self):
        self.request.current_manager.manager_permissions.remove(self.director_permission)
        with patch('biz.djangoapps.util.decorators.render_to_string', return_value=''):
            response = require_survey_target(self.request, course_id=unicode(self.course.id))
            self.assertEqual(403, response.status_code)

    def test_different_course(self):
        with patch('biz.djangoapps.util.decorators.render_to_string', return_value=''):
            response = require_survey_target(self.request, course_id='course-v1:org+course+run')
            self.assertEqual(403, response.status_code)


@handle_command_exception('/path/to/output_file')
def handle_command_exception_target():
    return "success"


@handle_command_exception('/path/to/output_file')
def handle_command_exception_target_error():
    raise TypeError()


@handle_command_exception(None)
def handle_command_exception_target_output_file_is_none():
    return "success"


class HandleCommandExceptionTest(TestCase):
    """Test for handle_command_exception"""

    def setUp(self):
        super(HandleCommandExceptionTest, self).setUp()

        patcher_os_path = patch('os.path')
        self.mock_os_path = patcher_os_path.start()
        self.mock_os_path.exists.return_value = True
        self.addCleanup(patcher_os_path.stop)

        patcher_makedirs = patch('os.makedirs')
        self.mock_makedirs = patcher_makedirs.start()
        self.addCleanup(patcher_makedirs.stop)

        patcher_open = patch('__builtin__.open')
        self.mock_open = patcher_open.start()
        self.addCleanup(patcher_open.stop)

    def test_handle_command_exception(self):
        self.assertEqual('success', handle_command_exception_target())

    def test_handle_command_exception_if_command_raises_error(self):
        self.assertIsNone(handle_command_exception_target_error())

    def test_handle_command_exception_if_file_dir_does_not_exist(self):
        self.mock_os_path.exists.return_value = False
        self.assertEqual('success', handle_command_exception_target())

    def test_handle_command_exception_if_file_open_raises_error(self):
        self.mock_open.side_effect = IOError()
        with self.assertRaises(CommandError):
            handle_command_exception_target()

    def test_handle_command_exception_if_output_file_is_none(self):
        with self.assertRaises(CommandError):
            handle_command_exception_target_output_file_is_none()

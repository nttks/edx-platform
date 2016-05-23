from contextlib import contextmanager
from functools import wraps

from django.conf import settings
from django.db.models.query import QuerySet
from django.test import TestCase
from django.test.utils import override_settings
from mock import patch

from biz.djangoapps.ga_manager.tests.factories import ManagerPermissionFactory, ManagerFactory
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.ga_organization.tests.factories import OrganizationFactory
from biz.djangoapps.util.biz_mongo_connection import BizMongoConnection
from courseware.tests.helpers import LoginEnrollmentTestCase
from student.tests.factories import UserFactory


class BizTestBase(TestCase):

    def setUp(self):
        super(BizTestBase, self).setUp()

        # Create initial data
        self.gacco_organization = Organization(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,  # It means the first of Organization
            created_by=UserFactory.create(),
        )
        self.gacco_organization.save()

        self.platformer_permission = self._create_permission('platformer', 1, 1, 1, 0, 0, 0)
        self.aggregator_permission = self._create_permission('aggregator', 1, 1, 1, 0, 0, 0)
        self.director_permission = self._create_permission('director', 0, 0, 1, 1, 1, 1)
        self.manager_permission = self._create_permission('manager', 0, 0, 0, 0, 1, 0)

        self.addCleanup(self._clear_cache)

    def _clear_cache(self):
        from django.core.cache import cache
        cache.clear()

    def _create_permission(
        self, permission_name, can_handle_organization, can_handle_contract,
        can_handle_manager, can_handle_course_operation, can_handle_achievement,
        can_handle_contract_operation,
    ):
        return ManagerPermissionFactory.create(
            permission_name=permission_name,
            can_handle_organization=can_handle_organization,
            can_handle_contract=can_handle_contract,
            can_handle_manager=can_handle_manager,
            can_handle_course_operation=can_handle_course_operation,
            can_handle_achievement=can_handle_achievement,
            can_handle_contract_operation=can_handle_contract_operation,
        )

    def _create_manager(self, org, user, created, permissions):
        return ManagerFactory.create(org=org, user=user, created=created, permissions=permissions)

    def _create_organization(self, org_code, creator_org, org_name='test org', created_by=None):
        return OrganizationFactory.create(
            org_name=org_name,
            org_code=org_code,
            creator_org=creator_org,
            created_by=created_by or UserFactory.create(),
        )

    def assertIdsOfListEqual(self, seq1, seq2):
        """
        An equality assertion for 'id's of two lists.

        Args:
            seq1: The first sequence to compare.
            seq2: The second sequence to compare.
        """
        if isinstance(seq1, QuerySet):
            seq1 = list(seq1)
        if not isinstance(seq1, list):
            raise self.failureException('First sequence is not a list: %s' % seq1)

        if isinstance(seq2, QuerySet):
            seq2 = list(seq2)
        if not isinstance(seq2, list):
            raise self.failureException('Second sequence is not a list: %s' % seq2)

        if len(seq1) != len(seq2):
            raise self.failureException('Two sequences have different lengths: %s, %s' % (len(seq1), len(seq2)))

        for item1, item2 in zip(seq1, seq2):
            try:
                item1_id = item1.id
            except AttributeError:
                raise self.failureException('Unable to get id attribute from %s' % item1)

            try:
                item2_id = item2.id
            except AttributeError:
                raise self.failureException('Unable to get id attribute from %s' % item2)

            if item1_id != item2_id:
                raise self.failureException('id does not match: %s, %s' % (item1_id, item2_id))


_current_feature = None
_current_organization = None
_current_manager = None,
_current_contract = None
_current_course = None
_selection_organizations = []
_selection_contracts = []
_selection_contract_details = []


class BizViewTestBase(BizTestBase, LoginEnrollmentTestCase):

    @contextmanager
    def skip_check_course_selection(
        self, current_feature=None, current_organization=None,
        current_manager=None, current_contract=None,
        current_course=None, selection_organizations=[],
        selection_contracts=[], selection_contract_details=[],
    ):
        """
        Skip biz.djangoapps.util.decorators.check_course_selection and all of decorators based on it.
        """

        global _current_feature, _current_organization, _current_manager, _current_contract, _current_course
        global _selection_organizations, _selection_contracts, _selection_contract_details

        _current_feature = current_feature
        _current_organization = current_organization
        _current_manager = current_manager
        _current_contract = current_contract
        _current_course = current_course
        _selection_organizations = selection_organizations
        _selection_contracts = selection_contract_details
        _selection_contract_details = selection_contract_details

        def _mock_func(func):
            @wraps(func)
            def wrapper(request, *args, **kwargs):
                return func(request, *args, **kwargs)
            return wrapper

        def _mock_check_course_selection(func):
            @wraps(func)
            def wrapper(request, *args, **kwargs):
                request.current_feature = _current_feature
                request.current_organization = _current_organization
                request.current_manager = _current_manager
                request.current_contract = _current_contract
                request.current_course = _current_course
                request.selection_organizations = _selection_organizations
                request.selection_contracts = _selection_contracts
                request.selection_contract_details = _selection_contract_details
                return func(request, *args, **kwargs)
            return wrapper

        with patch(
            'biz.djangoapps.util.decorators.check_course_selection',
            side_effect=_mock_check_course_selection
        ), patch('biz.djangoapps.util.decorators.require_survey', side_effect=_mock_func):
            yield


def _biz_store_config():
    """
    Replace db name to test_biz. db that begin with test_ will be removed by
    scripts/delete-mongo-test-dbs.js in the end of the test process.
    """
    _biz_mongo = settings.BIZ_MONGO.copy()
    for key, conf in _biz_mongo.items():
        _biz_mongo[key]['db'] = 'test_biz'
    return _biz_mongo


class BizStoreTestBase(BizTestBase):

    BIZ_MONGO = _biz_store_config()

    def setUp(self):
        settings_override = override_settings(BIZ_MONGO=self.BIZ_MONGO)
        settings_override.__enter__()
        self.addCleanup(settings_override.__exit__, None, None, None)

        self.addCleanup(self._drop_mongo_collections)

        super(BizStoreTestBase, self).setUp()

    def _drop_mongo_collections(self):
        for config in settings.BIZ_MONGO.values():
            BizMongoConnection(**config).database.drop_collection(config['collection'])

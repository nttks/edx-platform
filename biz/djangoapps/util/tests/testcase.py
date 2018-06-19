from contextlib import contextmanager
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.db.models.query import QuerySet
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.crypto import get_random_string
from mock import patch

from biz.djangoapps.ga_contract.tests.factories import (
    AdditionalInfoFactory, ContractFactory,
    ContractAuthFactory, ContractDetailFactory,
    ContractOptionFactory,
)
from biz.djangoapps.ga_contract_operation.models import ContractMail, ContractReminderMail
from biz.djangoapps.ga_contract_operation.tests.factories import ContractMailFactory, ContractReminderMailFactory, ContractTaskHistoryFactory
from biz.djangoapps.ga_invitation.tests.factories import AdditionalInfoSettingFactory, ContractRegisterFactory
from biz.djangoapps.ga_invitation.models import ContractRegister, INPUT_INVITATION_CODE, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE
from biz.djangoapps.ga_manager.models import ManagerPermission
from biz.djangoapps.ga_manager.tests.factories import ManagerFactory
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.ga_organization.tests.factories import OrganizationFactory
from biz.djangoapps.util.biz_mongo_connection import BizMongoConnection
from biz.djangoapps.util.datetime_utils import timezone_today

from courseware.tests.helpers import LoginEnrollmentTestCase
from student.models import CourseEnrollment, UserStanding
from student.tests.factories import UserFactory, UserStandingFactory
from xmodule.course_module import CourseDescriptor
from xmodule.modulestore import ModuleStoreEnum


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

        self.platformer_permission = ManagerPermission.objects.get(permission_name='platformer')
        self.aggregator_permission = ManagerPermission.objects.get(permission_name='aggregator')
        self.director_permission = ManagerPermission.objects.get(permission_name='director')
        self.manager_permission = ManagerPermission.objects.get(permission_name='manager')

        self.addCleanup(self._clear_cache)

    def _clear_cache(self):
        from django.core.cache import cache
        cache.clear()

    def _create_manager(self, org, user, created, permissions):
        return ManagerFactory.create(org=org, user=user, created=created, permissions=permissions)

    def _create_organization(self, org_code='test code', creator_org=None, org_name='test org', created_by=None):
        return OrganizationFactory.create(
            org_name=org_name,
            org_code=org_code,
            creator_org=creator_org or self.gacco_organization,
            created_by=created_by or UserFactory.create(),
        )

    def _create_contract(self, contract_name='test contract', contract_type='PF', register_type='ERS',
                         contractor_organization=None, owner_organization=None, end_date=None,
                         detail_courses=[], additional_display_names=[], url_code=None, send_mail=False,
                         customize_mail=False, send_submission_reminder=False):
        contract = ContractFactory.create(
            contract_name=contract_name,
            contract_type=contract_type,
            register_type=register_type,
            contractor_organization=contractor_organization or self._create_organization(),
            owner_organization=owner_organization or self.gacco_organization,
            end_date=end_date or timezone_today() + timedelta(days=1),
            created_by=UserFactory.create(),
        )
        for c in detail_courses:
            course_id = c.id if isinstance(c, CourseDescriptor) else c
            ContractDetailFactory.create(contract=contract, course_id=course_id)
        for d in additional_display_names:
            self._create_additional_info(contract=contract, display_name=d)
        if url_code:
            ContractAuthFactory.create(contract=contract, url_code=url_code, send_mail=send_mail)
        if customize_mail or send_submission_reminder:
            ContractOptionFactory.create(contract=contract, customize_mail=customize_mail,
                                         send_submission_reminder=send_submission_reminder)
        return contract

    def _create_additional_info(self, contract=None, display_name=None):
        return AdditionalInfoFactory.create(
            contract=contract or self._create_contract(),
            display_name=display_name or get_random_string(8),
        )

    def _create_user_and_contract_register(self, contract, email=None):
        if email:
            user = UserFactory.create(email=email)
        else:
            user = UserFactory.create()
        return self._input_contract(user=user, contract=contract)

    def _input_contract(self, contract, user):
        register = ContractRegister.get_by_user_contract(user, contract)
        if register:
            register.status = INPUT_INVITATION_CODE
            register.save()
            return register
        else:
            return ContractRegisterFactory.create(user=user, contract=contract, status=INPUT_INVITATION_CODE)

    def _register_contract(self, contract, user, additional_value=''):
        for additional_info in contract.additional_info.all():
            AdditionalInfoSettingFactory.create(
                user=user,
                contract=contract,
                display_name=additional_info.display_name,
                value='{}_{}'.format(additional_info.display_name, additional_value)
            )
        for detail in contract.details.all():
            CourseEnrollment.enroll(user, detail.course_id)
        register = ContractRegister.get_by_user_contract(user, contract)
        if register:
            register.status = REGISTER_INVITATION_CODE
            register.save()
            return register
        else:
            return ContractRegisterFactory.create(user=user, contract=contract, status=REGISTER_INVITATION_CODE)

    def _unregister_contract(self, contract, user):
        register = ContractRegister.get_by_user_contract(user, contract)
        if register:
            register.status = UNREGISTER_INVITATION_CODE
            register.save()
            return register
        else:
            return ContractRegisterFactory.create(user=user, contract=contract, status=UNREGISTER_INVITATION_CODE)

    def _account_disable(self, user):
        return UserStandingFactory.create(user=user, account_status=UserStanding.ACCOUNT_DISABLED, changed_by=user)

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

    def _create_task_history(self, contract, requester=None):
        if requester:
            return ContractTaskHistoryFactory.create(contract=contract, requester=requester)
        else:
            return ContractTaskHistoryFactory.create(contract=contract)

    def _create_contract_mail_default(self):
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_NEW_USER,
            mail_subject='Test Subject New User Without Logincode',
            mail_body='Test Body New User Without Logincode',
        )
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER,
            mail_subject='Test Subject Exists User Without Logincode',
            mail_body='Test Body Exists User Without Logincode',
        )
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE,
            mail_subject='Test Subject New User With Logincode',
            mail_body='Test Body New User With Logincode',
        )
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE,
            mail_subject='Test Subject Exists User With Logincode',
            mail_body='Test Body Exists User With Logincode',
        )
        # Following records are illegal, to confirm that be not gotten.
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_NEW_USER,
            mail_subject='[Illegal]Test Subject New User Without Logincode',
            mail_body='[Illegal]Test Body New User Without Logincode',
        )
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER,
            mail_subject='[Illegal]Test Subject Exists User Without Logincode',
            mail_body='[Illegal]Test Body Exists User Without Logincode',
        )
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_NEW_USER_WITH_LOGINCODE,
            mail_subject='[Illegal]Test Subject New User With Logincode',
            mail_body='[Illegal]Test Body New User With Logincode',
        )
        ContractMailFactory.create(
            contract=None,
            mail_type=ContractMail.MAIL_TYPE_REGISTER_EXISTING_USER_WITH_LOGINCODE,
            mail_subject='[Illegal]Test Subject Exists User With Logincode',
            mail_body='[Illegal]Test Body Exists User With Logincode',
        )

    def _create_contract_reminder_mail_default(self, reminder_email_days=3):
        return ContractReminderMailFactory.create(
            contract=None,
            mail_type=ContractReminderMail.MAIL_TYPE_SUBMISSION_REMINDER,
            mail_subject='Test Subject for Submission Reminder',
            mail_body='Test Body for Submission Reminder {username} and {fullname}',
            mail_body2='Test Body2 for Submission Reminder',
            reminder_email_days=reminder_email_days,
        )


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
    if hasattr(settings, 'BIZ_MONGO'):
        _biz_mongo = settings.BIZ_MONGO.copy()
        for key, conf in _biz_mongo.items():
            _biz_mongo[key]['db'] = 'test_biz'
        return _biz_mongo
    else:
        return None


class BizStoreTestBase(BizTestBase):

    BIZ_MONGO = _biz_store_config()

    def setUp(self):
        if self.BIZ_MONGO:
            settings_override = override_settings(BIZ_MONGO=self.BIZ_MONGO)
            settings_override.__enter__()
            self.addCleanup(settings_override.__exit__, None, None, None)

            self.addCleanup(self._drop_mongo_collections)

        super(BizStoreTestBase, self).setUp()

    def _drop_mongo_collections(self):
        for config in settings.BIZ_MONGO.values():
            BizMongoConnection(**config).database.drop_collection(config['collection'])

    # Note: This method had removed since Dogwood release.
    #       So, we restored it from common/lib/xmodule/xmodule/modulestore/tests/django_utils.py (as Cypress ver.)
    def _create_course(self, org, course, run, block_info_tree=None, course_fields=None):
        """
        create a course in the default modulestore from the collection of BlockInfo
        records defining the course tree
        Returns:
            course: the course of created
        """
        with self.store.branch_setting(ModuleStoreEnum.Branch.draft_preferred, None):
            course = self.store.create_course(org, course, run, self.user.id, fields=course_fields)
            self.course_loc = course.location  # pylint: disable=attribute-defined-outside-init

            def create_sub_tree(parent_loc, block_info):
                """Recursively creates a sub_tree on this parent_loc with this block."""
                block = self.store.create_child(
                    self.user.id,
                    # TODO remove version_agnostic() when we impl the single transaction
                    parent_loc.version_agnostic(),
                    block_info.category, block_id=block_info.block_id,
                    fields=block_info.fields,
                )
                for tree in block_info.sub_tree:
                    create_sub_tree(block.location, tree)
                setattr(self, block_info.block_id, block.location.version_agnostic())

            for tree in block_info_tree:
                create_sub_tree(self.course_loc, tree)

            # remove version_agnostic when bulk write works
            self.store.publish(self.course_loc.version_agnostic(), self.user.id)
        # mod to return course
        # Note: Get course object to be able to use subtree by course.get_children()
        return self.store.get_course(course.id)

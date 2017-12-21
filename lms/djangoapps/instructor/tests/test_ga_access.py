"""
Test instructor.access
"""

from nose.plugins.attrib import attr
from instructor.access import (
    allow_access,
    list_with_level,
    revoke_access,
    update_forum_role
)
from student.roles import GaCourseScorerRole
from student.tests.factories import UserFactory
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase


@attr('shard_1')
class TestGaCourseScorerAccessList(SharedModuleStoreTestCase):
    """ Test access listings. """
    @classmethod
    def setUpClass(cls):
        super(TestGaCourseScorerAccessList, cls).setUpClass()
        cls.course = CourseFactory.create()

    def setUp(self):
        super(TestGaCourseScorerAccessList, self).setUp()
        self.ga_course_scorer = [UserFactory.create() for _ in xrange(4)]
        for user in self.ga_course_scorer:
            allow_access(self.course, user, 'ga_course_scorer')

    def test_list(self):
        ga_course_scorer = list_with_level(self.course, 'ga_course_scorer')
        self.assertEqual(set(ga_course_scorer), set(self.ga_course_scorer))


@attr('shard_1')
class TestGaCourseScorerAccessAllow(SharedModuleStoreTestCase):
    """ Test access allow. """
    @classmethod
    def setUpClass(cls):
        super(TestGaCourseScorerAccessAllow, cls).setUpClass()
        cls.course = CourseFactory.create()

    def setUp(self):
        super(TestGaCourseScorerAccessAllow, self).setUp()

        self.course = CourseFactory.create()

    def test_allow(self):
        user = UserFactory()
        allow_access(self.course, user, 'ga_course_scorer')
        self.assertTrue(GaCourseScorerRole(self.course.id).has_user(user))

    def test_allow_twice(self):
        user = UserFactory()
        allow_access(self.course, user, 'ga_course_scorer')
        allow_access(self.course, user, 'ga_course_scorer')
        self.assertTrue(GaCourseScorerRole(self.course.id).has_user(user))


@attr('shard_1')
class TestGaCourseScorerAccessRevoke(SharedModuleStoreTestCase):
    """ Test access revoke. """
    @classmethod
    def setUpClass(cls):
        super(TestGaCourseScorerAccessRevoke, cls).setUpClass()
        cls.course = CourseFactory.create()

    def setUp(self):
        super(TestGaCourseScorerAccessRevoke, self).setUp()
        self.ga_course_scorer = [UserFactory.create() for _ in xrange(4)]
        for user in self.ga_course_scorer:
            allow_access(self.course, user, 'ga_course_scorer')

    def test_revoke(self):
        user = self.ga_course_scorer[0]
        revoke_access(self.course, user, 'ga_course_scorer')
        self.assertFalse(GaCourseScorerRole(self.course.id).has_user(user))

    def test_revoke_twice(self):
        user = self.ga_course_scorer[0]
        revoke_access(self.course, user, 'ga_course_scorer')
        self.assertFalse(GaCourseScorerRole(self.course.id).has_user(user))

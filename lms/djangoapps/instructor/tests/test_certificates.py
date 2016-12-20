"""Tests for the certificates panel of the instructor dash. """
from nose.plugins.attrib import attr
from django.core.urlresolvers import reverse
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from config_models.models import cache
from courseware.tests.factories import GlobalStaffFactory, InstructorFactory
from certificates.models import CertificateGenerationConfiguration


@attr('shard_1')
class CertificatesInstructorDashTest(SharedModuleStoreTestCase):
    """Tests for the certificate panel of the instructor dash. """

    @classmethod
    def setUpClass(cls):
        super(CertificatesInstructorDashTest, cls).setUpClass()
        cls.course = CourseFactory.create()
        cls.url = reverse(
            'instructor_dashboard',
            kwargs={'course_id': unicode(cls.course.id)}
        )

    def setUp(self):
        super(CertificatesInstructorDashTest, self).setUp()
        self.global_staff = GlobalStaffFactory()
        self.instructor = InstructorFactory(course_key=self.course.id)

        # Need to clear the cache for model-based configuration
        cache.clear()

        # Enable the certificate generation feature
        CertificateGenerationConfiguration.objects.create(enabled=True)

    def test_not_visible_to_everyone(self):
        # Instructors can't see the certificates section
        self.client.login(username=self.instructor.username, password="test")
        self._assert_certificates_visible(False)

        # Global staff can't see the certificates section
        self.client.login(username=self.global_staff.username, password="test")
        self._assert_certificates_visible(False)

    def _assert_certificates_visible(self, is_visible):
        """Check that the certificates section is visible on the instructor dash. """
        response = self.client.get(self.url)
        if is_visible:
            self.assertContains(response, "Student-Generated Certificates")
        else:
            self.assertNotContains(response, "Student-Generated Certificates")

"""
Tests for mask utilities
"""
import ddt
from mock import patch

from biz.djangoapps.util import mask_utils
from biz.djangoapps.util.tests.testcase import BizTestBase
from certificates.models import CertificateStatuses
from certificates.tests.factories import GeneratedCertificateFactory
from student.tests.factories import UserFactory, CourseEnrollmentFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@ddt.ddt
class MaskUtilsTest(BizTestBase, ModuleStoreTestCase):
    """Test for mask utilities"""

    def setUp(self):
        super(MaskUtilsTest, self).setUp()

        self.course = CourseFactory.create(org='org', course='course1', run='run')

    @patch('biz.djangoapps.util.mask_utils.CertificatePDF.delete')
    @ddt.data(
        CertificateStatuses.unavailable,
        CertificateStatuses.regenerating,
        CertificateStatuses.deleting,
        CertificateStatuses.deleted,
        CertificateStatuses.notpassing,
        CertificateStatuses.restricted,
    )
    def test_delete_certificates_success(self, status, mock_delete):
        self.user = UserFactory.create()
        self.certificate = GeneratedCertificateFactory.create(
            status=status,
            key='key',
            user=self.user,
            course_id=self.course.id)
        CourseEnrollmentFactory.create(course_id=self.course.id, user=self.user)
        mask_utils.delete_certificates(self.user)

        self.assertEqual(self.certificate.status, status)

    @patch('biz.djangoapps.util.mask_utils.log.error')
    @patch('biz.djangoapps.util.mask_utils.CertificatePDF.delete')
    @ddt.data(
        CertificateStatuses.generating,
        CertificateStatuses.downloadable,
    )
    def test_delete_certificates_error(self, status, mock_delete, mock_log_error):
        self.user = UserFactory.create()
        error_message = 'Failed to delete certificates of User {user_id}.'.format(user_id=self.user.id)
        self.certificate = GeneratedCertificateFactory.create(
            status=status,
            key='key',
            user=self.user,
            course_id=self.course.id)
        CourseEnrollmentFactory.create(course_id=self.course.id, user=self.user)

        with self.assertRaises(Exception) as e:
            mask_utils.delete_certificates(self.user)
        self.assertEqual(e.exception.message, error_message)
        mock_log_error.assert_called_once_with('Failed to delete certificate. user={user_id}, course_id={course_id}'.format(user_id=self.user.id, course_id=self.course.id))

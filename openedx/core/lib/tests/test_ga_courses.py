"""
Tests for functionality in openedx/core/lib/courses.py.
"""
import ddt
from django.test.utils import override_settings

from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from ..courses import custom_logo_url


@ddt.ddt
class CourseImageTestCase(ModuleStoreTestCase):

    def verify_url(self, expected_url, actual_url):
        """
        Helper method for verifying the URL is as expected.
        """
        if not expected_url.startswith("/"):
            expected_url = "/" + expected_url
        self.assertEquals(expected_url, actual_url)

    def test_get_custom_logo(self):
        course = CourseFactory.create(custom_logo='dummy.png')
        self.verify_url(
            unicode(course.id.make_asset_key('asset', course.custom_logo)),
            custom_logo_url(course)
        )

    @override_settings(DEFAULT_CUSTOM_LOGO_IMAGE_URL='test.png')
    @override_settings(STATIC_URL='static/')
    @ddt.data(ModuleStoreEnum.Type.split, ModuleStoreEnum.Type.mongo)
    def test_empty_image_name(self, default_store):
        """
        Verify that if a course has empty `custom_logo`, `custom_logo_url` returns
        `DEFAULT_CUSTOM_LOGO_IMAGE_URL` defined in the settings.
        """
        course = CourseFactory.create(default_store=default_store)
        self.assertEquals(
            'static/test.png',
            custom_logo_url(course),
        )

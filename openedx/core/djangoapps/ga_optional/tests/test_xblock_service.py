
import ddt
from mock import patch

from xblock.core import XBlock

from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory

from ..xblock_service import OptionalService


class PureBlock(XBlock):
    pass


class BadBlock(object):

    def __init__(self, location):
        self.location = location


@ddt.ddt
class OptionalServiceTest(ModuleStoreTestCase):

    def setUp(self):
        super(OptionalServiceTest, self).setUp()

        self.course = CourseFactory.create()
        chapter = ItemFactory.create(parent=self.course, category='chapter')
        section = ItemFactory.create(parent=chapter, category='sequential')
        self.vertical = ItemFactory.create(parent=section, category='vertical')

    @XBlock.register_temp_plugin(PureBlock, 'pure_block')
    @ddt.data(True, False)
    @patch('openedx.core.djangoapps.ga_optional.api.is_available')
    def test_is_available(self, enabled, mock_is_available):
        service = OptionalService()
        mock_is_available.return_value = enabled

        xblock = ItemFactory.create(parent=self.vertical, category='pure_block')

        if enabled:
            self.assertTrue(service.is_available(xblock, 'test-key'))
        else:
            self.assertFalse(service.is_available(xblock, 'test-key'))

        mock_is_available.assert_called_with('test-key', course_key=self.course.id)

    @patch('openedx.core.djangoapps.ga_optional.api.is_available')
    def test_is_available_invalid_xblock(self, mock_is_available):
        service = OptionalService()
        mock_is_available.return_value = True

        # no location
        xblock = object()
        self.assertFalse(service.is_available(xblock, 'test-key'))

        # invalid location
        xblock = BadBlock('test-location')
        self.assertFalse(service.is_available(xblock, 'test-key'))

        mock_is_available.assert_not_called()

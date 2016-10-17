"""
Unit tests for course.py
"""
import json

from django.test.utils import override_settings

from contentstore.tests.utils import CourseTestCase
from contentstore.utils import reverse_course_url


class TestCourseDisplayName(CourseTestCase):
    """
    Unit tests for length of display_name.
    """

    def test_course_handler_display_name_over_max_length(self):
        org = 'test-org'
        number = 'test-number'
        run = '001'
        display_name = 'Course Display Name'

        post_data = {
            'org': org,
            'number': number,
            'run': run,
            'display_name': display_name,
        }

        # Fail to create course
        with override_settings(MAX_LENGTH_COURSE_DISPLAY_NAME=18):
            resp = self.client.post(
                reverse_course_url('course_handler', self.course.id),
                data=json.dumps(post_data),
                content_type='application/json',
                HTTP_ACCEPT='application/json',
            )
        self.assertEqual({
            u'ErrMsg': u'Course name, please be up to 18 characters.',
        }, json.loads(resp.content))

        # Success to create course
        with override_settings(MAX_LENGTH_COURSE_DISPLAY_NAME=19):
            resp = self.client.post(
                reverse_course_url('course_handler', self.course.id),
                data=json.dumps(post_data),
                content_type='application/json',
                HTTP_ACCEPT='application/json',
            )

        self.assertEqual({
            u'url': u'/course/{org}/{number}/{run}'.format(org=org, number=number, run=run),
            u'course_key': u'{org}/{number}/{run}'.format(org=org, number=number, run=run),
        }, json.loads(resp.content))

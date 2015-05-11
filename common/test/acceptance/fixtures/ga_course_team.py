"""
Fixture to add course team members.
"""

import json

from . import STUDIO_BASE_URL
from .base import StudioApiFixture, FixtureError


class CourseTeamFixture(StudioApiFixture):
    """
    Fixture to add course team members.
    """

    def __init__(self, course_id, email, is_instructor):
        """
        Configure the course team member to be created by the fixture.
        """
        super(CourseTeamFixture, self).__init__()
        self.course_id = course_id
        self.email = email
        self.is_instructor = is_instructor

    def install(self):
        """
        Add course team members.
        """
        if self.is_instructor:
            post_data = {'role': 'instructor'}
        else:
            post_data = {'role': 'staff'}

        response = self.session.post(
            '{base}/course_team/{course_id}/{email}'.format(
                base=STUDIO_BASE_URL,
                course_id=self.course_id,
                email=self.email
            ),
            data=json.dumps(post_data),
            headers=self.headers
        )

        if not response.ok:
            raise FixtureError("Could not add {email} to {course_id} as course team member({role}).".format(
                email=self.email,
                course_id=self.course_id,
                role=post_data['role'])
            )

        return self

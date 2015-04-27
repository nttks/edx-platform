# -*- coding: utf-8 -*-
from lettuce import step, world
from nose.tools import assert_in, assert_true


@step(u'Then I see a progress summary')
def then_i_see_a_progress_summary(step):
    world.wait_for_visible('#ProgressGrid')

    if world.role == 'instructor':
        summary_text = u'Course name: Test Course\nEnrollment counts: 1\nActive student counts: 1'
    elif world.role == 'staff':
        summary_text = u'Course name: Test Course\nEnrollment counts: 2\nActive student counts: 2'

    assert_true(world.browser.status_code.is_success())
    assert_in(summary_text, world.css_text("div.progress-summary"))

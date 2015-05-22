# -*- coding: utf-8 -*-
from lettuce import step, world
from nose.tools import assert_in, assert_true, assert_false, assert_equal, assert_not_equal, assert_regexp_matches, assert_raises 
from splinter.exceptions import ElementDoesNotExist
from capa.tests.response_xml_factory import OptionResponseXMLFactory
from courseware.tests.factories import StaffFactory, InstructorFactory, StudentModuleFactory

from openassessment.assessment.models import Assessment, AssessmentPart, PeerWorkflow
from openassessment.assessment.serializers import rubric_from_dict
from submissions import api as sub_api
from openassessment.assessment.api import peer as peer_api
from openassessment.workflow import api as workflow_api
import json


@step(u'Given I am "([^"]*)" for a course with problem & openassessment')
def i_am_staff_or_instructor(step, role):  # pylint: disable=unused-argument
    assert_in(role, ['instructor', 'staff'])
    world.clear_courses()

    world.scenario_dict['COURSE'] = world.CourseFactory.create(
        org='edx',
        number='999',
        display_name='Test Course'
    )
    world.scenario_dict['COURSE'].raw_grader = [{
        'drop_count': 0,
        'min_count': 1,
        'short_label': 'Final',
        'type': 'Final Exam',
        'weight': 1.0
    }]
    world.scenario_dict['COURSE'].grade_cutoffs = {'Pass': 0.1}

    section1 = world.ItemFactory.create(
        parent_location=world.scenario_dict['COURSE'].location,
        category='chapter',
        display_name="Test Section 1"
    )
    subsec1 = world.ItemFactory.create(
        parent_location=section1.location,
        category='sequential',
        display_name="Test Subsection 1"
    )
    vertical1 = world.ItemFactory.create(
        parent_location=subsec1.location,
        category='vertical',
        display_name="Test Vertical 1",
    )

    problem_xml = OptionResponseXMLFactory().build_xml(
        question_text='The correct answer is Correct',
        num_inputs=1,
        weight=1,
        options=['Correct', 'Incorrect'],
        correct_option='Correct'
    )
    problem = world.ItemFactory.create(
        parent_location=vertical1.location,
        category='problem',
        display_name="Problem_1",
        metadata={'graded': True, 'format': 'Final Exam'},
        data=problem_xml
    )
    problem.save()
    correct_map = {
        unicode(problem.location) + "_2_1": {
            "hint": "",
            "hintmode": "",
            "correctness": "correct",
            "npoints": "",
            "msg": "",
            "queuestate": ""
        },
    }
    student_answers = { unicode(problem.location) + "_2_1": "Correct" } 
    input_state = { unicode(problem.location) + "_2_1": {} }

    problem.correct_map = correct_map
    problem.student_answers = student_answers
    problem.input_state = input_state
    world.scenario_dict['COURSE'].save()

    world.course_key = world.scenario_dict['COURSE'].id

    world.role = 'instructor'
    # Log in as the an instructor or staff for the course
    if role == 'instructor':
        # Make & register an instructor for the course
        world.instructor = InstructorFactory(course_key=world.course_key)
        world.enroll_user(world.instructor, world.course_key)

        world.log_in(
            username=world.instructor.username,
            password='test',
            email=world.instructor.email,
            name=world.instructor.profile.name
        )
        world.user = world.instructor

    else:
        world.role = 'staff'
        # Make & register a staff member
        world.staff = StaffFactory(course_key=world.course_key)
        world.enroll_user(world.staff, world.course_key)

        world.log_in(
            username=world.staff.username,
            password='test',
            email=world.staff.email,
            name=world.staff.profile.name
        )
        world.user = world.staff

    StudentModuleFactory.create(
        grade=1,
        max_grade=1,
        student=world.user,
        course_id=world.course_key,
        module_type="problem",
        module_state_key=problem.location,
        state=json.dumps({
            'attempts': 2,
            'done': True,
            'correct_map': correct_map,
            'student_answers': student_answers,
            'input_state': input_state,
        })
    )

    new_student_item = {
        "student_id": world.user.username,
        "course_id": world.course_key,
        "item_id": "block@openassessment@999",
        "item_type": "Peer_Submission",
    }
    submission = sub_api.create_submission(new_student_item, 'Test Answer', None)
    peer_api.on_start(submission["uuid"])
    workflow_api.create_workflow(submission["uuid"], ['peer', 'self'])
    sub_api.set_score(submission["uuid"], 5, 8)

    RUBRIC_OPTIONS = [
        {"order_num": 0, "name": u"Poor", "label": u"Poor", "points": 0},
        {"order_num": 1, "name": u"Good", "label": u"Good", "points": 1},
        {"order_num": 2, "name": u"Excellent", "label": u"Excellent", "points": 2},
    ]
    RUBRIC = {
        'criteria': [
            {
                "order_num": 0,
                "name": u"Content",
                "label": u"Content",
                "prompt": u"Content",
                "options": RUBRIC_OPTIONS
            },
            {
                "order_num": 1,
                "name": u"Ideas",
                "label": u"Ideas",
                "prompt": u"Ideas",
                "options": RUBRIC_OPTIONS
            }
        ]
    }

    part_data = [
        {
            "selected": {'Content': 'Poor', 'Ideas': 'Good'},
            "feedback": {'Content': 'Good feedback'},
        },
        {
            "selected": {'Content': 'Excellent', 'Ideas': 'Good'},
            "feedback": {
                'Content': 'Excellent feedback',
                'Ideas': 'Poor feedback'
            },
        },
    ]

    rubric = rubric_from_dict(RUBRIC)
    assessment = Assessment.create(rubric, "Scorer", submission['uuid'], "PE")
    part1 = AssessmentPart.create_from_option_names(
        assessment, part_data[0]["selected"],
        feedback=part_data[0]["feedback"]
    )
    part2 = AssessmentPart.create_from_option_names(
        assessment, part_data[1]["selected"],
        feedback=part_data[1]["feedback"]
    )
    workflow = PeerWorkflow.objects.filter(submission_uuid=submission['uuid'])
    workflow.update(student_id=new_student_item["student_id"],
        item_id=new_student_item["item_id"],
        course_id=new_student_item["course_id"])

    assessment.save()
    part1[0].save()
    part2[0].save()


@step(u'Then I see a progress summary')
def then_i_see_a_progress_summary(step):
    world.wait_for_visible('#ProgressGrid')

    if world.role == 'instructor':
        summary_text = u'Course name: Test Course\nEnrollment counts: 1\nActive student counts: 1'
    elif world.role == 'staff':
        summary_text = u'Course name: Test Course\nEnrollment counts: 2\nActive student counts: 2'

    assert_true(world.browser.status_code.is_success())
    assert_in(summary_text, world.css_text("div.progress-summary"))


@step(u'Then I see a Progress Update')
def then_i_see_a_progress_update(step):
    world.wait_for_visible('#ProgressUpdate')
    str_date = world.css_text("#ProgressUpdate li span.structure")
    sub_date = world.css_text("#ProgressUpdate li span.submission")
    ora_date = world.css_text("#ProgressUpdate li span.openassessment")
    assert_regexp_matches(str_date, '^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}')
    assert_regexp_matches(sub_date, '^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}')
    assert_regexp_matches(ora_date, '^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}')


@step(u'Then I see a Progress Grid')
def then_i_see_a_progress_grid(step):
    world.wait_for_visible('#ProgressGrid div.slick-header')
    world.wait_for_visible('#ProgressGrid div.slick-viewport')
    world.wait_for_visible('#ProgressGrid .slick-row .slick-cell.l1')
    world.wait_for_visible('#ProgressGrid .slick-row .slick-cell.l3')
    world.wait_for_visible('#ProgressGrid .slick-row .slick-cell.l4')
    world.wait_for_visible('#ProgressGrid .slick-row .slick-cell.l5')

    with assert_raises(ElementDoesNotExist):
        world.browser.find_by_css("#ProgressGrid div.loading").first

    assert_equal("1", world.css_text("#ProgressGrid .slick-row .slick-cell.l3"))
    assert_equal("100", world.css_text("#ProgressGrid .slick-row .slick-cell.l4"))
    assert_equal("2", world.css_text("#ProgressGrid .slick-row .slick-cell.l5"))
    course_list = [c.text for c in world.browser.find_by_css(
        "#ProgressGrid .slick-row .slick-cell.l1")]
    assert_in(" Problem_1", course_list)

@step(u'When I click a Grid row')
def when_i_click_a_grid_row(step):
    world.css_click("#ProgressGrid .slick-row .slick-cell.l4")

@step(u'Then I see a answer distribution')
def then_i_see_a_grid_row(step):
    world.wait_for_visible("#AnswerDistribution canvas")
    answer_distribution = world.browser.find_by_css("#AnswerDistribution canvas")
    assert_true(answer_distribution.visible)

@step(u'Then I see a select options')
def then_i_see_a_select_options(step):
    world.wait_for_visible("select#BarChart_items option")
    options = world.browser.find_by_css("select#BarChart_items option")
    oa_chart = world.browser.find_by_css("#OpenassessmentScoreDistribution canvas")
    sub_chart = world.browser.find_by_css("#SubmissionScoreDistribution canvas")
    option_list = [ c.text for c in options]
    assert_in("Ideas", option_list)
    assert_in("Content", option_list)
    assert_in("Final_Score", option_list)
    assert_false(sub_chart.visible)
    assert_false(oa_chart.visible)

@step(u'When I select a oa chart')
def when_i_select_a_oa_chart(step):
    world.wait_for_visible('#BarChart_items option[value^="#Content"]')
    world.css_click('#BarChart_items option[value^="#Content"]')

@step(u'Then I see a oa chart')
def then_i_see_a_oa_chart(step):
    world.wait_for_visible("#OpenassessmentScoreDistribution canvas")
    oa_chart = world.browser.find_by_css("#OpenassessmentScoreDistribution canvas")
    sub_chart = world.browser.find_by_css("#SubmissionScoreDistribution canvas")
    assert_true(oa_chart.visible)
    assert_false(sub_chart.visible)
    
@step(u'When I select a submission chart')
def when_i_select_a_submission_chart(step):
    world.wait_for_visible('#BarChart_items option[value^="#Final_Score"]')
    world.css_click('#BarChart_items option[value^="#Final_Score"]')

@step(u'Then I see a submission chart')
def then_i_see_a_submission_chart(step):
    world.wait_for_visible("#SubmissionScoreDistribution canvas")
    oa_chart = world.browser.find_by_css("#OpenassessmentScoreDistribution canvas")
    sub_chart = world.browser.find_by_css("#SubmissionScoreDistribution canvas")
    assert_false(oa_chart.visible)
    assert_true(sub_chart.visible)

"""
Function to grasp the progress of the course.
"""
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_control
from instructor.views.tools import handle_dashboard_error
from instructor.views.api import require_level
from util.json_request import JsonResponse

from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import CourseLocator

from django.contrib.auth.models import User
from student.models import UserStanding
from courseware.models import StudentModule
from submissions.models import ScoreSummary
from openassessment.assessment.models import Assessment, PeerWorkflow, CriterionOption

from xmodule.modulestore.django import modulestore
from courseware.courses import get_course

import logging
import json


log = logging.getLogger("progress_report")


class ProgressReportBase(object):
    """"""
    def __init__(self, course_id):
        """Initialize."""
        self.course_id = self.get_course_id(course_id)
        self.course_location = self.get_course_location(course_id)
        self.location_list = []

    def get_course_id(self, course_id):
        if not isinstance(course_id, CourseKey):
            return CourseKey.from_string(course_id)

        return course_id

    def get_course_location(self, course_id):
        if not isinstance(course_id, CourseLocator):
            return CourseLocator.from_string(course_id)

        return course_id

    def get_display_name(self, course_location, item_id):
        display_name = None
        module = modulestore()
        module_list = module.get_items(
            course_location, qualifiers={'category': 'openassessment'})

        for module in module_list:
            if unicode(module.scope_ids.usage_id) == item_id:
                display_name = module.display_name_with_default

        return display_name


class ProblemReport(ProgressReportBase):
    """Problems report"""

    def __init__(self, course_id):
        """Initialize."""
        super(ProblemReport, self).__init__(course_id)

    def get_active_students(self):
        """Get active enrolled students."""
        enrollments = User.objects.filter(
            courseenrollment__course_id__exact=self.course_id)

        active_students = enrollments.filter(is_active=1).exclude(
            standing__account_status__exact=UserStanding.ACCOUNT_DISABLED)

        return (enrollments.count(), active_students.count())

    def get_course_structure(self):
        self.location_list = []
        course = get_course(self.course_id)
        self._get_children_module(course)

        return self.location_list

    def _get_children_module(self, course, parent=None):
        if parent is None:
            parent = []

        for child in course.get_children():
            if child.category not in (
                    "chapter", "sequential", "vertical", "problem"):
                continue

            module = {
                "usage_id": child.scope_ids.usage_id.to_deprecated_string(),
                "category": child.category,
                "display_name": child.display_name_with_default,
                "indent": len(parent),
                "module_size": 0,
                "has_children": child.has_children,
                "parent": list(parent),
            }

            self.location_list.append(module)

            if child.has_children:
                parent.append(child.scope_ids.usage_id.to_deprecated_string())
                self._get_children_module(child, parent)
                parent.pop()
            else:
                self.location_list[-1]["module_size"] += 1

    def get_problem_data(self):
        problem_data = {}
        for module in StudentModule.all_submitted_problems_read_only(self.course_id):
            key = str(module.module_state_key)
            state = json.loads(module.state)

            if key in problem_data:
                current = problem_data[key]
                problem_data[key] = {
                    "counts": current["counts"] + 1,
                    "attempts": current["attempts"] + state.get("attempts"),
                    "correct_maps": self._get_correctmap_data(
                        current["correct_maps"], state.get("correct_map")),
                    "student_answers": self._get_student_answers_data(
                        current["student_answers"], state.get("student_answers")),
                }
            else:
                problem_data[key] = {
                    "counts": 1,
                    "attempts": state.get("attempts"),
                    "correct_maps": self._get_correctmap_data(
                        {}, state.get("correct_map")),
                    "student_answers": self._get_student_answers_data(
                        {}, state.get("student_answers")),
                }

        return problem_data

    def _get_correctmap_data(self, sum_correct_map, correct_map):
        for key in correct_map.keys():
            corrects_data = {}
            if correct_map[key].get("correctness") == "correct":
                corrects_data.update({key: 1})
            else:
                corrects_data.update({key: 0})

            if key in sum_correct_map:
                sum_correct_map[key] += corrects_data[key]
            else:
                sum_correct_map[key] = corrects_data[key]

        return sum_correct_map

    def _get_student_answers_data(self, sum_student_answers, student_answers):

        for key, answers in student_answers.items():
            answers_data = {}
            if isinstance(answers, list):
                answers_data[key] = {}
                for answer in answers:
                    answers_data[key][answer] = 1
            else:
                answers_data[key] = {answers: 1}

            if key in sum_student_answers:
                for answer in answers_data[key].keys():
                    if answer in sum_student_answers[key]:
                        sum_student_answers[key][answer] += answers_data[key][answer]
                    else:
                        sum_student_answers[key][answer] = answers_data[key][answer]
            else:
                sum_student_answers[key] = answers_data[key]

        return sum_student_answers

    def get_progress_list(self):
        structure = self.get_course_structure()
        problems = self.get_problem_data()
        result = []

        for idx in xrange(0, len(structure)):
            if structure[idx]["category"] != "problem":
                result.append(structure[idx])
                continue

            usage_id = structure[idx]["usage_id"]

            if usage_id not in problems:
                continue

            i = 0
            for key, value in sorted(problems[usage_id]["student_answers"].items()):
                module = structure[idx].copy()
                module["module_id"] = key
                module["student_answers"] = value
                module["counts"] = problems[usage_id]["counts"]
                module["attempts"] = problems[usage_id]["attempts"]

                if key in problems[usage_id]["correct_maps"]:
                    module["correct_counts"] = problems[usage_id]["correct_maps"][key]

                result.append(module)

        return result


class OpenAssessmentReport(ProgressReportBase):
    """Problem report class."""

    def __init__(self, course_id):
        """Initialize."""
        super(OpenAssessmentReport, self).__init__(course_id)

    def get_oa_rubric_scores(self):
        """
        Example:
        {
            u'block-v1:org+cn1+run+type@openassessment+block@08e0dbcebea34f0fa205b14f18e0352d': {
            'display_name': u'',
            'rubrics': [ u'Content': {u'Poor': [8, 0L], u'Fair': [1, 1L], u'Excellent': [3, 3L]},
            u'Ideas': {u'Poor': [6, 0L], u'Good': [3, 2L], u'Fair': [3, 1L]}]
            },
            ...,
        }
        """
        #for assessment in Assessment.objects.iterator():

        scores = {}
        peer_list = PeerWorkflow.objects.filter(
            course_id=self.course_id).values_list("submission_uuid", flat=True)

        for assessment in Assessment.objects.filter(submission_uuid__in=list(peer_list)):
            item_id = PeerWorkflow.objects.filter(
                submission_uuid=assessment.submission_uuid
            ).values("item_id")[0]["item_id"]

            if item_id not in scores:
                scores.update({item_id: {}})
                scores[item_id]['display_name'] = self.get_display_name(
                    self.course_location, item_id)
                scores[item_id]['rubrics'] = {}

            for part in assessment.parts.all().select_related():
                criterion_id = part.criterion.id
                criterion_name = part.criterion.name
                option_order_num = part.option.order_num
                option_name = part.option.name

                if criterion_name not in scores[item_id]['rubrics']:
                    scores[item_id]['rubrics'].update({criterion_name: {}})

                    for option in CriterionOption.objects.filter(
                            criterion_id=criterion_id).values("name", "order_num"):

                        scores[item_id]['rubrics'][criterion_name].update(
                            {option["name"]: [0, option["order_num"]]})

                    scores[item_id]['rubrics'][criterion_name][option_name] = [
                        1, option_order_num]

                else:
                    count = scores[item_id]['rubrics'][criterion_name][option_name][0] + 1
                    scores[item_id]['rubrics'][criterion_name][option_name] = [
                        count, option_order_num]

        return scores


class SubmissionReport(ProgressReportBase):
    """Problem report class."""
    def __init__(self, course_id):
        """Initialize."""
        super(SubmissionReport, self).__init__(course_id)

    def get_submission_scores(self):
        """
        Example:
        {
            u'block-v1:org+cn1+run+type@openassessment+block@08e0dbcebea34f0fa205b14f18e0352d': {
            'display_name': u'',
            'rubrics': [ u'FinalScore': {u'0-9': [8, 0L], u'10-19': [1, 1L], u'20-29': [3, 3L]}],
            },
            ...,
        }
        """
        scores = {}
        partition_size = 10
        cname = 'FinalScore'

        score_summaries = ScoreSummary.objects.filter(
            student_item__course_id=unicode(self.course_location)
        ).select_related('latest', 'student_item')

        for summary in score_summaries:
            item_id = summary.student_item.item_id

            if not summary.latest.is_hidden():
                if item_id in scores:
                    for score, count in scores[item_id]['rubrics'][cname].items():
                        score_min, score_max = score.split('-')
                        if int(score_min) <= summary.latest.points_earned <= int(score_max):
                            scores[item_id]['rubrics'][cname][score][0] += 1
                            break

                else:
                    if summary.latest.points_possible >= partition_size:
                        incr = summary.latest.points_possible / partition_size
                    else:
                        incr = 1

                    scores.update({item_id: {}})
                    scores[item_id]['display_name'] = self.get_display_name(
                        self.course_location, item_id)
                    scores[item_id]['rubrics'] = {}
                    scores[item_id]['rubrics'][cname] = {}

                    score_min = 0
                    order_num = 0

                    for score_max in xrange(0, summary.latest.points_possible + incr, incr):
                        count = 0
                        if score_min <= summary.latest.points_earned <= score_max:
                            count = 1
                        scores[item_id]['rubrics'][cname].update(
                            {unicode(score_min) + '-' + unicode(score_max): [count, order_num]})
                        score_min = score_max + 1
                        order_num += 1

        return scores


@handle_dashboard_error
@require_level('staff')
@require_GET
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def ajax_get_progress_list(request, course_id):
    progress = ProblemReport(course_id)
    result = progress.get_progress_list()
    return JsonResponse(result)


@handle_dashboard_error
@require_level('staff')
@require_GET
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def ajax_get_oa_rubric_scores(request, course_id):
    progress = OpenAssessmentReport(course_id)
    result = progress.get_oa_rubric_scores()
    return JsonResponse(result)


@handle_dashboard_error
@require_level('staff')
@require_GET
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def ajax_get_submission_scores(request, course_id):
    progress = SubmissionReport(course_id)
    result = progress.get_submission_scores()
    return JsonResponse(result)

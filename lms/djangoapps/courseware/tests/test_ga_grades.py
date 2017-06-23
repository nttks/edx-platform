"""
Test grade calculation.
"""
import ddt

from capa.tests.response_xml_factory import ChoiceResponseXMLFactory, MultipleChoiceResponseXMLFactory
from xmodule.modulestore.tests.factories import ItemFactory

from .test_submitting_problems import TestSubmittingProblems as EdXTestSubmittingProblems


class TestSubmittingProblems(EdXTestSubmittingProblems):

    def add_multiple_to_section(self, section, name, choices, whole_point_addition=False):
        """
        Create and return a multiple choice problem.
        """
        prob_xml = MultipleChoiceResponseXMLFactory().build_xml(choices=choices)

        problem = ItemFactory.create(
            parent=section,
            parent_location=section.location,
            category='problem',
            data=prob_xml,
            metadata={'whole_point_addition': whole_point_addition},
            display_name=name
        )

        # re-fetch the course from the database so the object is up to date
        self.refresh_course()
        return problem

    def add_checkbox_to_section(self, section, name, choices, whole_point_addition=False):
        """
        Create and return a choice problem.
        """
        prob_xml = ChoiceResponseXMLFactory().build_xml(choice_type='checkbox', choices=choices)

        problem = ItemFactory.create(
            parent=section,
            parent_location=section.location,
            category='problem',
            data=prob_xml,
            metadata={'whole_point_addition': whole_point_addition},
            display_name=name
        )

        # re-fetch the course from the database so the object is up to date
        self.refresh_course()
        return problem

    def count_attempted_section(self):
        """
        Count the number of attempted sections from grade_summary.totaled_scores.
        """
        grade_summary = self.get_grade_summary()
        totaled_scores = grade_summary.get('totaled_scores', {})
        count = 0
        for _, scores in totaled_scores.iteritems():
            for score in scores:
                if score.is_attempted:
                    count += 1
        return count


@ddt.ddt
class CourseGraderWholeAdditionPointTestMixin(object):
    """
    Mixin for test the course grader with whole_addition_point.
    """

    def problem_setup(self, late=False, reset=False, showanswer=False):
        """
        Set up a simple course for testing basic grading functionality.
        """

        grading_policy = {
            "GRADER": [{
                "type": "Homework",
                "min_count": 1,
                "drop_count": 0,
                "short_label": "HW",
                "weight": 1.0
            }],
            "GRADE_CUTOFFS": {
                'A': .8,
                'B': .33,
            }
        }
        self.add_grading_policy(grading_policy)

        # set up a simple course with four problems
        self.homework = self.add_graded_section_to_course('homework', late=late, reset=reset, showanswer=showanswer)
        self.create_problem(self.homework, 'p1')
        self.create_problem(self.homework, 'p2', True)
        self.create_problem(self.homework, 'p3')
        self.refresh_course()

    def test_none_grade(self):
        """
        Check grade is 0 to begin with.
        """
        self.problem_setup()
        self.check_grade_percent(0)
        self.assertEqual(self.get_grade_summary()['grade'], None)
        self.assertEqual(self.score_for_hw('homework'), [0.0, 0.0, 0.0])
        self.assertEqual(self.count_attempted_section(), 0)

    @ddt.data(
        ('p1', False),
        ('p2', True),
        ('p3', False),
    )
    @ddt.unpack
    def test_only_look_at(self, problem, whole_point_addition):
        """
        Check grade is added after look at question with whole_point_addition.
        """
        self.problem_setup()

        # look at problem with no whole_point_addition 
        self.look_at_question(problem)

        if whole_point_addition:
            self.check_grade_percent(0.33)
            self.assertEqual(self.get_grade_summary()['grade'], 'B')
            self.assertEqual(self.score_for_hw('homework'), [0.0, 1.0, 0.0])
            self.assertEqual(self.count_attempted_section(), 0)
        else:
            self.check_grade_percent(0)
            self.assertEqual(self.count_attempted_section(), 0)

    def test_grade_with_correct(self):
        """
        Check grade when currect answer has been submitted.
        """
        self.problem_setup()

        self.submit_question_answer('p1', self.correct_answer)
        self.submit_question_answer('p2', self.correct_answer)
        self.submit_question_answer('p3', self.correct_answer)

        self.check_grade_percent(1.0)
        self.assertEqual(self.get_grade_summary()['grade'], 'A')
        self.assertEqual(self.score_for_hw('homework'), [1.0, 1.0, 1.0])
        self.assertEqual(self.count_attempted_section(), 1)

    def test_grade_with_incorrect(self):
        """
        Check grade is added even if incurrect answer has been submitted.
        """
        self.problem_setup()

        self.submit_question_answer('p1', self.incorrect_answer)
        self.submit_question_answer('p2', self.incorrect_answer)
        self.submit_question_answer('p3', self.incorrect_answer)

        self.check_grade_percent(0.33)
        self.assertEqual(self.get_grade_summary()['grade'], 'B')
        self.assertEqual(self.score_for_hw('homework'), [0.0, 1.0, 0.0])
        self.assertEqual(self.count_attempted_section(), 1)


class CourseGraderChoiceTest(CourseGraderWholeAdditionPointTestMixin, TestSubmittingProblems):

    @property
    def correct_answer(self):
        return {'2_1[]': ['choice_1', 'choice_2']}

    @property
    def incorrect_answer(self):
        return {'2_1[]': ['choice_0']}

    def create_problem(self, section, name, whole_point_addition=False):
        return self.add_checkbox_to_section(section, name, [False, True, True], whole_point_addition)


class CourseGraderMultipleTest(CourseGraderWholeAdditionPointTestMixin, TestSubmittingProblems):

    @property
    def correct_answer(self):
        return {'2_1': 'choice_1'}

    @property
    def incorrect_answer(self):
        return {'2_1': 'choice_0'}

    def create_problem(self, section, name, whole_point_addition=False):
        return self.add_multiple_to_section(section, name, [False, True, False], whole_point_addition)

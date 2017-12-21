"""
Progress Restriction
"""
import json
from courseware.models import StudentModuleHistory

PROGRESS_RESTRICTION_TYPE = {
    'no-restriction': 'No Restriction',
    'correct-answer-rate': 'Correct Answer Rate',
}
UNCONDITIONAL_PASSING = 100


class ProgressRestriction(object):
    def __init__(self, course_key, user, course_module):
        self.dict_section_name_by_vertical_name = {}

        self.list_restricted_chapter_name = []
        self.list_restricted_section_name = []

        self.list_restricted_chapter_index = []
        self.dict_restricted_sections_by_chapter_index = {}
        self.dict_restricted_verticals_by_section_name = {}

        if course_module:
            student_module_histories = StudentModuleHistory.objects.filter(
                student_module__course_id=course_key,
                student_module__student_id=user.id,
            )

            passed_restricted_vertical = False
            for chapter_idx, chapter in enumerate(course_module.get_display_items()):
                if chapter.visible_to_staff_only:
                    # visible_to_staff_only is not used as condition
                    # of progress restriction
                    continue

                if passed_restricted_vertical:
                    self.list_restricted_chapter_name.append(unicode(chapter.location.name))
                    self.list_restricted_chapter_index.append(chapter_idx)

                restricted_sections = []

                for section_idx, section in enumerate(chapter.get_display_items()):
                    if section.visible_to_staff_only:
                        # visible_to_staff_only is not used as condition
                        # of progress restriction
                        continue

                    if passed_restricted_vertical:
                        self.list_restricted_section_name.append(unicode(section.location.name))
                        restricted_sections.append(section_idx + 1)

                    restricted_verticals = []

                    for vertical_idx, vertical in enumerate(section.get_display_items()):
                        if vertical.visible_to_staff_only:
                            # visible_to_staff_only is not used as condition
                            # of progress restriction
                            continue

                        if passed_restricted_vertical:
                            restricted_verticals.append(vertical_idx)

                        is_restricted_vertical = passed_restricted_vertical
                        if not is_restricted_vertical and vertical.progress_restriction['type'] == PROGRESS_RESTRICTION_TYPE['correct-answer-rate']:
                            problems = [
                                {
                                    'location': component.location,
                                    'count': component.get_score()['total'],
                                    'whole_point_addition': component.whole_point_addition
                                } for component in vertical.get_children() if hasattr(component, 'category') and component.category == u'problem'
                            ]
                            problem_count = sum([p['count'] for p in problems])

                            if problem_count:
                                problems = filter(lambda p: not p['whole_point_addition'], problems)
                                correct_count = problem_count - sum([p['count'] for p in problems])
                                has_answered_correctly = {}
                                for sm in student_module_histories.filter(student_module__module_state_key__in=[p['location'] for p in problems]):
                                    st = json.loads(sm.state)
                                    for k in st.get('correct_map', []):
                                        if st['correct_map'][k]['correctness'] == 'correct':
                                            has_answered_correctly[k] = True
                                correct_count += len(filter(lambda v: v, has_answered_correctly.values()))

                                is_restricted_vertical = (100 * correct_count / problem_count) < vertical.progress_restriction.get('passing_mark', 0)

                        self.dict_section_name_by_vertical_name[unicode(vertical.location.name)] = unicode(section.location.name)

                        if is_restricted_vertical and not passed_restricted_vertical:
                            passed_restricted_vertical = True

                    if restricted_verticals:
                        self.dict_restricted_verticals_by_section_name[unicode(section.location.name)] = restricted_verticals

                    self.dict_restricted_sections_by_chapter_index[chapter_idx] = restricted_sections

    def get_restricted_list_in_section(self, section):
        """
        Returns a list of sequence numbers of restricted vertical-blocks in specific section
        """
        return self.dict_restricted_verticals_by_section_name.get(unicode(section), [])

    def get_restricted_list_in_same_section(self, vertical_name):
        """
        Returns a list of sequence numbers of restricted vertical-blocks
        in section including specific vertical-block
        """
        return self.get_restricted_list_in_section(self.dict_section_name_by_vertical_name[vertical_name]) if vertical_name in self.dict_section_name_by_vertical_name else []

    def get_restricted_chapters(self):
        """
        Returns a list of restricted chapters' sequence numbers, to use to gray out toc
        """
        return self.list_restricted_chapter_index

    def get_restricted_sections(self):
        """
        Returns a dict of chapters' numbers as keys and
        list of restricted sections' sequence numbers as values
        to use to gray out toc
        """
        return self.dict_restricted_sections_by_chapter_index

    def is_restricted_chapter(self, chapter):
        """
        Returns a boolean if chapter is restricted
        when the first vertical-block in the chapter is restricted the chapter is restricted
        """
        return chapter in self.list_restricted_chapter_name

    def is_restricted_section(self, section):
        """
        Returns a boolean if section is restricted
        when the first vertical-block in the section is restricted the section is restricted
        """
        return section in self.list_restricted_section_name

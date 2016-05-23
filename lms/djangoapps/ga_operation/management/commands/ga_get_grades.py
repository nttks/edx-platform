"""
Management command to generate a list of grades for
the perticipants of g1528
 (written by skim-ks <s.kim@gacco.co.jp>)
"""
from courseware import grades, courses
from django.core.management.base import BaseCommand, CommandError
import os
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from student.models import CourseEnrollment, UserSignupSource
from optparse import make_option
import unicodecsv as csv
from student.management.commands.get_grades import RequestMock


class Command(BaseCommand):
    help = """
    Generate a matrix of grades for g1528

    CSV will include the following:
      - username
      - email
      - computed grade

    Outputs grades to a csv file.

    Example:
      python manage.py ga_get_grade_g1528 \
        -s g1528.gacco.org -o /tmp/20130813-6.00x.csv course-v1:gacco+ga001+2014_04 ... \
        --settings=aws
    """
    args = '-s <site name> -o <output> <course_ID1> [course_ID2...] '
    option_list = BaseCommand.option_list + (
        make_option('-s', '--site',
                    metavar='SITE',
                    dest='sitename',
                    default='',
                    help='site name for the target organization'),
        make_option('-o', '--output',
                    metavar='FILE',
                    dest='output',
                    default=False,
                    help='Filename for grade output'),)

    def get_score(self, student, course, request):
        request.user = student

        grade = grades.grade(student, request, course)
        score = int(grade['percent'] * 100)
        return score

    def handle(self, *args, **options):
        if len(args) < 1:
            raise CommandError("Usage : ga_get_grades_g1528 {0}".format(self.args))

        if not options['sitename']:
            raise CommandError("Usage : ga_get_grades_g1528 {0}".format(self.args))

        if not options['output']:
            raise CommandError("Usage : ga_get_grades_g1528 {0}".format(self.args))

        if os.path.exists(options['output']):
            raise CommandError("File {0} already exists".format(
                options['output']))

        STATUS_INTERVAL = 50

        # ----------------generate student list ---------------------------------------
        print "Fetching students in {0}".format(options['sitename'])
        # UserSignupSource objects have just 2 attributes:
        # user : username
        # site : microsite ID (ex. g1528.gacco.org)
        enrolled_student_list = UserSignupSource.objects.filter(
            site=options['sitename'],
        )
        enrolled_students = map(lambda n: n.user, enrolled_student_list)

        total = len(enrolled_students)
        print "Total enrolled: {0}".format(total)

        # ----------------generate course list ----------------------------------------
        # courses for scoring
        course_key_list = []
        course_list = {}

        # parse out the course into a coursekey
        for course_id in args:
            try:
                course_key = CourseKey.from_string(course_id)
            # if it's not a new-style course key, parse it from an old-style course key
            except InvalidKeyError:
                course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
            course_key_list.append(course_key)
            course_list[course_key] = courses.get_course_by_id(course_key)

        # ----------------start grading -----------------------------------------------
        # rows: results
        rows = []
        # generate header
        rows.append(["email", "username"] + course_key_list + ["total"])

        print "Grading students"
        factory = RequestMock()
        request = factory.get('/')

        for count, student in enumerate(enrolled_students):
            count += 1
            if count % STATUS_INTERVAL == 0:
                print "{0}/{1} completed ".format(count, total)

            row = [student.email, student.username]
            total_score = 0
            for course_key in course_key_list:
                if CourseEnrollment.is_enrolled(student, course_key):
                    course = course_list[course_key]
                    score = self.get_score(student, course, request)
                    total_score += score
                else:
                    score = "N/A"

                row.append("{0}".format(score))
            row.append(total_score)
            rows.append(row)

        with open(options['output'], 'wb') as f:
            writer = csv.writer(f)
            writer.writerows(rows)

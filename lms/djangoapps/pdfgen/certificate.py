"""Django management command to force certificate generation"""
from django.contrib.auth.models import User
from django.test.client import RequestFactory
from certificates.models import (GeneratedCertificate,
    CertificateStatuses, CertificateWhitelist)
from courseware import grades, courses
from student.models import UserProfile
import json
import random
import hashlib
from pdfgen.views import create_cert_pdf, delete_cert_pdf


class CertPDFException(Exception):
    pass


class CertificatePDF(object):
    def __init__(self, user, course_id, debug, noop):
        self.user = user
        self.course_id = course_id
        self.debug = debug
        self.noop = noop

    def create(self):
        """Create pdf of certificate."""
        students = self._get_students()

        print "\nFetching course data for {0}".format(self.course_id)
        course = courses.get_course_by_id(self.course_id)
        course_name = course.display_name

        if not course.has_ended():
            raise CertPDFException('This couse is not ended.')

        request = self._create_request()

        print "Fetching enrollment for students({0})".format(self.course_id)
        for student in students:
            request.user = student

            cert, created = GeneratedCertificate.objects.get_or_create(
                user=student, course_id=self.course_id)

            grade = grades.grade(cert.user, request, course)
            print "User Name {0}: Grade {1}% - {2}".format(cert.user,
                grade['percent'] * 100, grade['grade']),

            self._create_cert_pdf(student, course_name, cert, grade)

    def _create_cert_pdf(self, student, course_name, cert, grade):
        profile = UserProfile.objects.get(user=student)
        cert.grade = grade['percent']
        cert.mode = 'honor'
        cert.user = student
        cert.course_id = self.course_id
        cert.name = profile.name

        is_whitelisted = CertificateWhitelist.objects.filter(
            user=student, course_id=self.course_id, whitelist=True).exists()

        if is_whitelisted or grade['grade']:
            if UserProfile.objects.filter(allow_certificate=False,
                user=student).exists():

                new_status = CertificateStatuses.restricted
                cert.status = new_status
                print ": Status {0}".format(new_status)
                if not self.noop:
                    cert.save()
            else:
                key = self._make_hashkey(random.random())
                cert.key = key

                if not self.noop:
                    response_json = create_cert_pdf(student.username,
                        self.course_id, cert.name, course_name,
                        grade['percent'], key)
                    response = json.loads(response_json)
                    self._dprint(": Response = %s" % response, newline=False)
                    cert.download_url = response.get(u'download_url', False)

                    if cert.download_url:
                        new_status = CertificateStatuses.downloadable
                        cert.status = new_status
                        cert.save()
                        print ": Status {0}".format(new_status)
                    else:
                        new_status = CertificateStatuses.error
                        cert.status = new_status
                        cert.save()
                        print ": Status {0}".format(new_status),
                        print ": Error {}".format(response.get('error'))
                else:
                    new_status = CertificateStatuses.downloadable
                    print ": Status {0}".format(new_status)
        else:
            new_status = CertificateStatuses.notpassing
            cert.status = new_status
            print ": Status {0}".format(new_status)
            if not self.noop:
                cert.save()

    def delete(self):
        """Delete pdf of certificate."""
        students = self._get_students()

        for student in students:
            cert, created = GeneratedCertificate.objects.get_or_create(
                user=student, course_id=self.course_id)

            if cert.status == CertificateStatuses.downloadable:
                print "Deleting {1}'s certification for {0}".format(
                    self.course_id, student.username),

                if not self.noop:
                    new_status = CertificateStatuses.deleted
                    cert.status = new_status
                    response_json = delete_cert_pdf(student.username,
                        self.course_id)
                    response = json.loads(response_json)
                    self._dprint(": Response = %s" % response, newline=False)
                    msg = response.get(u'error', False)
                    if msg:
                        new_status = CertificateStatuses.error
                        print ": Error {}".format(msg)
                    else:
                        cert.download_url = ''
                        cert.key = ''
                    cert.save()
                    print ": Status {0}".format(new_status)
                else:
                    print ": Status {0}({1})".format(cert.status,
                        "Status is not downloadable")

    def report(self):
        """Report course grade."""
        students = self._get_students()

        print "\nFetching course data for {0}".format(self.course_id)
        course = courses.get_course_by_id(self.course_id)
        request = self._create_request()
        total = {'users': 0, 'pass': 0, 'notpass': 0}

        print "Summary Report: Course Name [{0}]".format(
            course.display_name.encode('utf_8'))

        for student in students:
            request.user = student
            total['users'] += 1

            cert, created = GeneratedCertificate.objects.get_or_create(
                user=student, course_id=self.course_id)

            grade = grades.grade(cert.user, request, course)
            summary = grades.progress_summary(student, request, course)
            self._report_summary(summary)
            self._add_total(cert.user, grade, total)

        self._report_total(total)

    def _report_summary(self, summary):
        for section in summary:
            print "  Section Name [{0}] ".format(
                section['display_name'].encode('utf_8'))

            for subsec in section['sections']:
                subsec_name = subsec['display_name'].encode('utf_8')
                format_name = subsec['format'].encode('utf_8')
                earned = subsec['section_total'][0]
                possible = subsec['section_total'][1]
                print "    Sub Section Name [{0}] (Assignment Types [{1}], Score {2}/{3})".format(
                    subsec_name, format_name, earned, possible)

                for unit in subsec['scores']:
                    earned, possible, graded, unitname = unit
                    self._dprint("      Unit Name [{0}] (Score {2}/{3})\
                        ".format(unitname.encode('utf_8'),
                        graded, earned, possible))

    def _add_total(self, user, grade, total):
        print "  User Name [{0}] (Grade :{1}% - {2})\n".format(user,
            grade['percent'] * 100, grade['grade'])
        if grade['grade'] is not None:
            total['pass'] += 1
            if grade['grade'] in total:
                total[grade['grade'].encode('utf_8')] += 1
            else:
                total[grade['grade'].encode('utf_8')] = 1
        else:
            total['notpass'] += 1

    def _report_total(self, total):
        """"""
        print "\nTotal: Users {0}, Pass {1}(".format(
            total.pop('users'), total.pop('pass'), total.pop('notpass')),

        first = True
        if total:
            for key, value in sorted(total.items()):
                if first:
                    print "{0} {1}".format(key, value),
                    first = False
                else:
                    print ", {0} {1}".format(key, value),
            print ")"
        else:
            print "No grade.)"

    def _dprint(self, msg, newline=True):
        """"""
        if self.debug:
            if newline:
                print msg
            else:
                print msg,

    def _create_request(self):
        """"""
        factory = RequestFactory()
        request = factory.get('/')
        request.session = {}

        return request

    def _get_students(self):
        """"""
        students = []

        try:
            if not self.user:
                students = User.objects.filter(
                    courseenrollment__course_id__exact=self.course_id)
                if not students:
                    raise CertPDFException("user does not exists.")
            elif '@' in self.user:
                students.append(User.objects.get(email=self.user,
                    courseenrollment__course_id=self.course_id))
            else:
                students.append(User.objects.get(username=self.user,
                    courseenrollment__course_id=self.course_id))
        except User.DoesNotExist, err:
            raise CertPDFException("{}".format(err))

        return students

    def _make_hashkey(self, seed):
        """
        Generate a string key by hashing
        """
        md5 = hashlib.md5()
        md5.update(str(seed))
        return md5.hexdigest()

    """
    def _send_to_pdfgen(self, contents, key, use_https=False):
        #This method is not Test
        #e.g.
        #contents = {
        #    'username': profile.name,
        #    'display_name': student.username,
        #    'course_id': course_id,
        #    'course_name': course_name,
        #    'grade': grade['grade'],
        #}
        #response = _send_to_pdfgen(contents, key)
        if use_https:
            proto = "https"
        else:
            proto = "http"

        #url = unicode('{0}://{1}:{2}/pdfgen?{3}'.format(
        #    proto, settings.PDFGEN_HOST, settings.PDFGEN_PORT, key))
        url = unicode('{0}://{1}:{2}/pdfgen'.format(
            proto, settings.PDFGEN_HOST, settings.PDFGEN_PORT))
        self._dprint(debug, "### url = %s" % url)

        session = requests.Session()
        #session.auth = requests_auth

        try:
            r = session.post(url, data=contents)
            self._dprint(debug, "### header = %s" % r.text)
        except requests.exceptions.ConnectionError, err:
            log.error(err)
            return {"error": 'cannot connect to server'}

        if r.status_code not in [200]:
            return {"error":
                'unexpected HTTP status code [%d]' % r.status_code}

        return json.loads(r.text)
    """

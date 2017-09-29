# -*- coding: utf-8 -*-
from datetime import date, datetime, time
import logging
import os
import pytz

from boto import connect_s3
from boto.s3.key import Key
from django.contrib.auth.models import User
from django.core.management import call_command
from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.test.client import RequestFactory

from pdfgen.certificate import CertPDFException, CertPDFUserNotFoundException
from pdfgen.views import CertException
from lms import CELERY_APP
from opaque_keys.edx.keys import CourseKey
from certificates.models import CertificateStatuses, GeneratedCertificate
from courseware.courses import get_course_by_id
from courseware.views import is_course_passed
from openedx.core.djangoapps.ga_operation.task_base import TaskBase
from openedx.core.djangoapps.ga_operation.utils import (
    change_behavior_sys, delete_files, get_dummy_raw_input, get_std_info_from_local_storage,
    handle_uploaded_generated_file_to_s3
)
from student.models import CourseEnrollment, UserStanding
from xmodule.modulestore.django import modulestore

log = logging.getLogger(__name__)


@CELERY_APP.task
def create_certs_task(course_id, email, student_ids, prefix=""):
    """create_certs_task main."""
    CreateCerts(course_id, email, student_ids, prefix).run()


class CreateCerts(TaskBase):
    """Generate certificate class"""

    def __init__(self, course_id, email, student_ids, prefix):
        super(CreateCerts, self).__init__(email)
        self.student_ids = student_ids
        self.prefix = prefix
        self.course_id = course_id
        self.operation = "create"

    def run(self):
        try:
            if self.student_ids:
                for student in self.student_ids:
                    try:
                        call_command(
                            self.get_command_name(), self.operation, self.course_id,
                            username=student, debug=False, noop=False, prefix=self.prefix
                        )
                    except CertPDFUserNotFoundException:
                        # continue the process when got error that not found certificate user.
                        log.warning("User({}) was not found".format(student))
                        continue
            else:
                call_command(self.get_command_name(),
                             self.operation, self.course_id,
                             username=False, debug=False, noop=False, prefix=self.prefix)
        except (CertException, CertPDFException) as e:
            msg = 'Failure to generate the PDF files from create_certs command.'
            log.exception(msg)
            self.err_msg = "{} {}".format(msg, e)
        except Exception as e:
            msg = 'Caught the exception: ' + type(e).__name__
            log.exception(msg)
            self.err_msg = "{} {}".format(msg, e)
        finally:
            self._send_email()

    def _get_email_body(self):
        if self.err_msg:
            return "{}({}) was failed.\n\n{}".format(self.get_command_name(),
                                                     self.operation,
                                                     self.err_msg)
        else:
            all_certs = GeneratedCertificate.objects.filter(
                course_id=CourseKey.from_string(self.course_id),
                status=CertificateStatuses.generating).order_by('id')
            if self.student_ids:
                # When specifying a target, separate the URL we created now and all the already created URLs.
                created_certs = GeneratedCertificate.objects.filter(
                    Q(course_id=CourseKey.from_string(self.course_id)),
                    Q(user__email__in=self.student_ids) | Q(user__username__in=self.student_ids),
                    Q(status=CertificateStatuses.generating)).order_by('id')

                created_message = u"{}件の修了証を発行しました\n{}\n\n".format(
                    len(created_certs), "\n".join([gc.download_url for gc in created_certs]))
                all_message = u"{}件の修了証はまだ公開されていません\n{}".format(
                    len(all_certs), "\n".join([gc.download_url for gc in all_certs]))
                return created_message + all_message
            else:
                return self._get_email_body_for_all_certs(all_certs)

    def _get_email_body_for_all_certs(self, all_certs):
        def _get_disabled_account_and_course_passed_username_list(_course):
            return [
                userstanding.user.username for userstanding in UserStanding.objects.filter(
                    user__in=[c.user for c in CourseEnrollment.objects.filter(course_id=_course.id)],
                    account_status=UserStanding.ACCOUNT_DISABLED
                )
                if is_course_passed(
                    course=_course,
                    student=userstanding.user,
                    request=RequestFactory().request()
                )
            ]

        def _get_not_activate_and_course_passed_username_list(_course):
            return [
                enrollment.user.username for enrollment in CourseEnrollment.objects.filter(course_id=_course.id)
                if not enrollment.user.is_active and is_course_passed(
                    course=_course,
                    student=enrollment.user,
                    request=RequestFactory().request()
                )
            ]

        def _get_unenroll_and_course_passed_username_list(_course, _disabled_username_list,
                                                          _not_activate_username_list):
            return [
                enrollment.user.username for enrollment in CourseEnrollment.objects.filter(
                    course_id=_course.id, is_active=False)
                if is_course_passed(
                    course=_course,
                    student=enrollment.user,
                    request=RequestFactory().request()
                )
                # The following user's counts are not included in the number of unenroll user's count
                # * disabled and course passed user's count(_disabled_username_list)
                # * not activate and course passed user's count(_not_activate_username_list)
                and enrollment.user.username not in _disabled_username_list
                and enrollment.user.username not in _not_activate_username_list
            ]

        course = get_course_by_id(course_key=CourseKey.from_string(self.course_id))
        not_activate_username_list = _get_not_activate_and_course_passed_username_list(course)
        disabled_username_list = _get_disabled_account_and_course_passed_username_list(course)
        unenroll_username_list = _get_unenroll_and_course_passed_username_list(course,
                                                                               disabled_username_list,
                                                                               not_activate_username_list)

        return (
            u"修了証発行数： {all_certs_count}\n"
            u"※受講解除者{unenroll_count}人を含みます（受講解除ユーザー名：{unenroll_username_list}）\n"
            u"---\n"
            u"修了判定データに含まれる\n"
            u"　* 合格かつ未アクティベート者数：{not_activate_username_count}（未アクティベートユーザー名：{not_activate_username_list}）\n"
            u"　* 合格かつ退会者数：{disabled_account_count}（退会ユーザー名：{disabled_username_list}）\n"
            u"\n"
            u"---\n{cert_list}"
        ).format(
            all_certs_count=len(all_certs),
            unenroll_count=len(unenroll_username_list),
            unenroll_username_list=", ".join(unenroll_username_list),
            disabled_account_count=len(disabled_username_list),
            disabled_username_list=", ".join(disabled_username_list),
            not_activate_username_count=len(not_activate_username_list),
            not_activate_username_list=", ".join(not_activate_username_list),
            cert_list="\n".join([gc.download_url for gc in all_certs]),
        )

    def _get_email_subject(self):
        if self.err_msg:
            return "{} was failure ({})".format(self.get_command_name(), self.course_id)
        else:
            return "{} was completed. ({})".format(self.get_command_name(), self.course_id)

    @staticmethod
    def get_command_name():
        return "create_certs"


@CELERY_APP.task
def dump_oa_scores_task(course_id, email):
    """dump_oa_scores_task main."""
    DumpOaScores(course_id, email).run()


class DumpOaScores(TaskBase):
    """DumpOaScores class."""

    def __init__(self, course_id, email):
        super(DumpOaScores, self).__init__(email)
        self.course_id = course_id

    def run(self):
        oa_items = None
        try:
            course_key = CourseKey.from_string(self.course_id)
            oa_items = modulestore().get_items(course_key, qualifiers={'category': 'openassessment'})
            with change_behavior_sys(get_dummy_raw_input):
                # Change behavior raw_input method while take the all dump files
                # The raw_input's behavior has been changed and if call it, return the increment value.
                for _ in range(0, len(oa_items)):
                    call_command(self.get_command_name(), self.course_id, dump_dir=self._get_dump_dir())
        except Exception as e:
            log.exception('Caught the exception: ' + type(e).__name__)
        finally:
            if oa_items:
                self.err_msg, self.out_msg = get_std_info_from_local_storage()
                self._send_email()

    @staticmethod
    def _get_dump_dir():
        return settings.GA_OPERATION_WORK_DIR + "/" + DumpOaScores.get_command_name()

    @staticmethod
    def get_command_name():
        return "dump_oa_scores"


@CELERY_APP.task
def ga_get_grades_g1528_task(course_list, email):
    """ga_get_grades_g1528_task main."""
    GaGetGradesG1528(course_list, email).run()


class GaGetGradesG1528(TaskBase):
    """GaGetGradesG1528 class."""
    def __init__(self, course_list, email):
        super(GaGetGradesG1528, self).__init__(email)
        self.course_list = course_list

    def run(self):
        file_path_list = []
        try:
            file_path = self._get_output_file_path()
            with change_behavior_sys(get_dummy_raw_input):
                call_command(self.get_command_name(), *self.course_list,
                             output=file_path,
                             sitename=self._get_company_key()["site_name"])
            file_path_list = handle_uploaded_generated_file_to_s3(
                [file_path],
                self._get_company_key()["bucket_name"]
            )
        except Exception as e:
            log.exception('Caught the exception: ' + type(e).__name__)
            self.err_msg = "{}".format(e)
        finally:
            if not self.err_msg:
                self.err_msg, self.out_msg = get_std_info_from_local_storage()
            self.out_msg += '\n'.join(file_path_list)
            self._send_email()
            delete_files([self._get_company_key()["output_file_name"]], settings.GA_OPERATION_WORK_DIR)

    def _get_output_file_path(self):
        return settings.GA_OPERATION_WORK_DIR + '/' + self._get_company_key()["output_file_name"]

    @staticmethod
    def _get_company_key():
        return settings.GA_OPERATION_SPECIFIC_COMPANY_KEYS["g1528"]

    @staticmethod
    def get_command_name():
        return "ga_get_grades"


class AggregateInHouseOperationTaskBase(TaskBase):
    """AggregateInHouseOperationTaskBase class."""
    def __init__(self, start_date, end_date, email):
        """
        :param start_date: YYYY-MM-DD
        :param end_date: YYYY-MM-DD
        :param email: user@domain
        """
        super(AggregateInHouseOperationTaskBase, self).__init__(email)
        self.start_date = date(*[int(num) for num in start_date.split("-")])
        self.end_date = date(*[int(num) for num in end_date.split("-")])
        self.download_url = None

    def run(self):
        try:
            # Fetch data
            data = self._fetch_data()

            # Dump directory
            dump_dir = self._get_dump_dir()
            if not os.path.exists(dump_dir):
                os.makedirs(dump_dir)

            # Create csv file
            csv_filepath = os.path.join(dump_dir, self._csv_filename())
            self._write_csv(csv_filepath, self._csv_header(), data)

            # Upload to S3
            conn = connect_s3(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
            bucket = conn.get_bucket(settings.GA_OPERATION_ANALYZE_UPLOAD_BUCKET_NAME)
            self.download_url = self._upload_file_to_s3(bucket, csv_filepath)

            # Delete csv file
            os.remove(csv_filepath)
        except Exception as e:
            self.err_msg = "{}".format(e)
            raise e
        finally:
            self._send_email()

    # must be override by sub class
    def _fetch_data(self):
        raise NotImplementedError

    def query_beginning_of_day(self):
        d = datetime.combine(self.start_date, time.min)
        jst_date = d.replace(tzinfo=pytz.timezone("Asia/Tokyo"))
        return jst_date.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    def query_end_of_day(self):
        d = datetime.combine(self.end_date, time.max)
        jst_date = d.replace(tzinfo=pytz.timezone("Asia/Tokyo"))
        return jst_date.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    @staticmethod
    def remove_tz(col_date):
        if col_date is None:
            return 'NULL'
        return col_date.strftime("%Y-%m-%d %H:%M:%S.%f") if type(col_date) == datetime else col_date

    @staticmethod
    def remove_tz_microsecond(col_date):
        if col_date is None:
            return 'NULL'
        return col_date.strftime("%Y-%m-%d %H:%M:%S") if type(col_date) == datetime else col_date

    @staticmethod
    def null_to_string(str_or_null):
        if str_or_null is None:
            return 'NULL'
        return str_or_null

    def _csv_filename(self):
        start = self.start_date.strftime("%Y%m%d")
        end = self.end_date.strftime("%Y%m%d")
        return "{}-{}-{}-{}.csv".format(self._get_subject_name(), datetime.now().strftime("%Y%m%d_%H%M%S"), start, end)

    # must be override by sub class
    def _csv_header(self):
        raise NotImplementedError

    def _get_email_subject(self):
        if self.err_msg:
            return "{} was failure.".format(self._get_subject_name())
        else:
            return "{} was completed.".format(self._get_subject_name())

    def _get_email_body(self):
        if self.err_msg:
            return "{} was failed.\n\nError reason\n{}".format(self._get_subject_name(), self.err_msg)
        else:
            return "Successfully created csv file: {}".format(self.download_url)

    def _upload_file_to_s3(self, bucket, filepath):
        s3key = None
        try:
            s3key = Key(bucket)
            s3key.key = "{}/{}/{}".format(
                settings.GA_OPERATION_ANALYZE_UPLOAD_PREFIX, self.get_command_name(), self._csv_filename())
            s3key.set_contents_from_filename(filepath)
            download_url = s3key.generate_url(expires_in=0, query_auth=False, force_http=True)

            log.info("Successfully uploaded file to S3: {}/{}".format(bucket.name, s3key.key))
            return download_url
        except Exception as e:
            raise e
        finally:
            if s3key:
                s3key.close()

    @staticmethod
    def _write_csv(filepath, header, rows):
        try:
            # format without quotation to handle with macros
            with open(filepath, 'w') as output_file:
                output_file.write(",".join(header))
                output_file.write("\n")
                for row in rows:
                    output_file.write(",".join(str(col) for col in row))
                    output_file.write("\n")
        except IOError:
            raise IOError("Error writing to file: %s" % filepath)
        except Exception as e:
            raise e
        print "Successfully created csv file: %s" % filepath

    @classmethod
    def _get_dump_dir(cls):
        return os.path.join(settings.GA_OPERATION_WORK_DIR, cls.get_command_name())

    @staticmethod
    def get_command_name():
        raise NotImplementedError

    @staticmethod
    def _get_subject_name():
        raise NotImplementedError


@CELERY_APP.task
def all_users_info_task(start_date, end_date, email):
    """all_usrs_info_task main."""
    AllUsersInfo(start_date, end_date, email).run()


class AllUsersInfo(AggregateInHouseOperationTaskBase):
    """AllUsersInfo class."""
    def __init__(self, start_date, end_date, email):
        super(AllUsersInfo, self).__init__(start_date, end_date, email)

    def _csv_header(self):
        return [
            "id",
            "username",
            "email",
            "is_active",
            "last_login",
            "date_joined",
            "gender",
            "year_of_birth",
            "level_of_education"
        ]

    def _fetch_data(self):
        sql = """
            SELECT a.id, a.username, a.email, a.is_active, a.last_login, a.date_joined,
                    b.gender, b.year_of_birth, b.level_of_education
            FROM auth_user a
                INNER JOIN auth_userprofile b ON a.id=b.user_id
            WHERE
                a.date_joined BETWEEN '{}' AND '{}'
            ORDER BY a.date_joined, a.id
        """.format(self.query_beginning_of_day(), self.query_end_of_day())

        users = []
        for user in User.objects.raw(sql):
            try:
                str(user.email)
            except UnicodeEncodeError:
                # Ignore to email address including multi-byte characters
                log.warning("Email is invalid(user={})".format(user.id))
                continue

            users.append([user.id, user.username, user.email, 1 if user.is_active else 0,
                          self.remove_tz(user.last_login),
                          self.remove_tz_microsecond(user.date_joined),
                          self.null_to_string(user.gender),
                          self.null_to_string(user.year_of_birth),
                          self.null_to_string(user.level_of_education)])
        return users

    @staticmethod
    def get_command_name():
        return "all_users_info"

    @staticmethod
    def _get_subject_name():
        return "auth_userprofile"


@CELERY_APP.task
def create_certs_status_task(start_date, end_date, email):
    """create_certs_status_task main."""
    CreateCertsStatus(start_date, end_date, email).run()


class CreateCertsStatus(AggregateInHouseOperationTaskBase):
    """CreateCertsStatus class."""
    def __init__(self, start_date, end_date, email):
        super(CreateCertsStatus, self).__init__(start_date, end_date, email)

    def _csv_header(self):
        return [
            "user_id",
            "course_id",
            "grade",
            "status",
            "created_date"
        ]

    def _fetch_data(self):
        sql = """
            SELECT id, user_id, course_id, grade, status, created_date
            FROM certificates_generatedcertificate
            WHERE
                created_date BETWEEN '{}' AND '{}'
            ORDER BY created_date, id
        """.format(self.query_beginning_of_day(), self.query_end_of_day())

        certs = []
        for cert in GeneratedCertificate.objects.raw(sql):
            certs.append([cert.user_id, cert.course_id, cert.grade, cert.status,
                          self.remove_tz_microsecond(cert.created_date)])
        return certs

    @staticmethod
    def get_command_name():
        return "create_certs_status"

    @staticmethod
    def _get_subject_name():
        return "certificates_generatedcertificate"


@CELERY_APP.task
def enrollment_status_task(start_date, end_date, email):
    """enrollment_status_task main."""
    EnrollmentStatus(start_date, end_date, email).run()


class EnrollmentStatus(AggregateInHouseOperationTaskBase):
    """EnrollmentStatus class."""
    def __init__(self, start_date, end_date, email):
        super(EnrollmentStatus, self).__init__(start_date, end_date, email)

    def _csv_header(self):
        return [
            "id",
            "user_id",
            "course_id",
            "created",
            "is_active",
            "mode"
        ]

    def _fetch_data(self):
        sql = """
            SELECT id, user_id, course_id, created, is_active, mode
            FROM student_courseenrollment
            WHERE
                created BETWEEN '{}' AND '{}'
            ORDER BY created, id
        """.format(self.query_beginning_of_day(), self.query_end_of_day())

        # Do not use CourseEnrollment.objects.raw() method
        # CourseLocator sometimes throw InvalidKeyError exception when to use the method
        ces = []
        cursor = connection.cursor()
        cursor.execute(sql)
        for c in cursor.fetchall():
            ces.append([c[0], c[1], c[2],
                        self.remove_tz_microsecond(c[3]),
                        1 if c[4] else 0, c[5]])
        return ces

    @staticmethod
    def get_command_name():
        return "enrollment_status"

    @staticmethod
    def _get_subject_name():
        return "student_courseenrollment"


@CELERY_APP.task
def disabled_account_info_task(start_date, end_date, email):
    """disabled_account_info_task main."""
    DisabledAccountInfo(start_date, end_date, email).run()


class DisabledAccountInfo(AggregateInHouseOperationTaskBase):
    """DisabledAccountInfo class."""
    def __init__(self, start_date, end_date, email):
        super(DisabledAccountInfo, self).__init__(start_date, end_date, email)

    def _csv_header(self):
        return [
            "id",
            "user_id",
            "account_status",
            "changed_by_id",
            "standing_last_changed_at",
            "replace(resign_reason, '\\r\\n', '')"
        ]

    def _fetch_data(self):
        sql = """
            SELECT id, user_id, account_status, changed_by_id, standing_last_changed_at,
                replace(resign_reason, '\r\n', '') AS reason
            FROM student_userstanding
            WHERE
                standing_last_changed_at BETWEEN '{}' AND '{}'
            ORDER BY standing_last_changed_at, id
        """.format(self.query_beginning_of_day(), self.query_end_of_day())

        uss = []
        for u in UserStanding.objects.raw(sql):
            uss.append([u.id, u.user_id, u.account_status, u.changed_by_id,
                        self.remove_tz_microsecond(u.standing_last_changed_at),
                        self.null_to_string(u.reason)])
        return uss

    @staticmethod
    def get_command_name():
        return "disabled_account_info"

    @staticmethod
    def _get_subject_name():
        return "student_userstanding"

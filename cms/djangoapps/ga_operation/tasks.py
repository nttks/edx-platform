import logging

from django.core.management import call_command

from cms import CELERY_APP
from openedx.core.djangoapps.ga_operation.task_base import TaskBase
from openedx.core.djangoapps.ga_operation.utils import change_behavior_sys, get_dummy_raw_input_list

log = logging.getLogger(__name__)


@CELERY_APP.task
def delete_course_task(course_id, email):
    """delete_course_task main."""
    DeleteCourse(course_id, email).run()


class DeleteCourse(TaskBase):
    def __init__(self, course_id, email):
        super(DeleteCourse, self).__init__(email)
        self.course_id = course_id

    def run(self):
        try:
            with change_behavior_sys(get_dummy_raw_input_list(["y"])):
                call_command(self.get_command_name(), self.course_id, "--purge")
        except Exception as e:
            msg = 'Caught the exception: ' + type(e).__name__
            log.exception(msg)
            self.err_msg = "{} {}".format(msg, e)
        finally:
            self._send_email()

    def _get_email_subject(self):
        if self.err_msg:
            return "{} was failure ({})".format(self.get_command_name(), self.course_id)
        else:
            return "{} was completed. ({})".format(self.get_command_name(), self.course_id)

    @staticmethod
    def get_command_name():
        return "delete_course"


@CELERY_APP.task
def delete_library_task(library_id, email):
    """delete_library_task main."""
    DeleteLibrary(library_id, email).run()


class DeleteLibrary(TaskBase):
    def __init__(self, library_id, email):
        super(DeleteLibrary, self).__init__(email)
        self.library_id = library_id

    def run(self):
        try:
            with change_behavior_sys(get_dummy_raw_input_list(["y"])):
                call_command(self.get_command_name(), self.library_id, "--purge")
        except Exception as e:
            msg = 'Caught the exception: ' + type(e).__name__
            log.exception(msg)
            self.err_msg = "{} {}".format(msg, e)
        finally:
            self._send_email()

    def _get_email_subject(self):
        if self.err_msg:
            return "{} was failure ({})".format(self.get_command_name(), self.library_id)
        else:
            return "{} was completed. ({})".format(self.get_command_name(), self.library_id)

    @staticmethod
    def get_command_name():
        return "delete_library"

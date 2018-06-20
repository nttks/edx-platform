#!/usr/bin/env bash

cd /edx/app/edxapp/edx-platform
source ../venvs/edxapp/bin/activate
python manage.py lms --settings=aws send_self_paced_course_closure_reminder_email

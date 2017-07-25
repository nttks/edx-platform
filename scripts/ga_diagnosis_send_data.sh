#!/usr/bin/env bash

cd /edx/app/edxapp/edx-platform
source ../venvs/edxapp/bin/activate

python manage.py lms --settings=aws ga_diagnosis_send_data course-v1:gacco+pt014+2017_07

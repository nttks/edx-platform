#!/usr/bin/env bash
cd /edx/app/edxapp/edx-platform
source ../venvs/edxapp/bin/activate

python manage.py lms --settings aws reservation_mail

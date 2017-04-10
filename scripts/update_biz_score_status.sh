#!/usr/bin/env bash

cd /edx/app/edxapp/edx-platform
source ../venvs/edxapp/bin/activate
python manage.py lms --settings=aws update_biz_score_status --excludes=72,73,74,75,76,77,78,79,80,81,82,83,86

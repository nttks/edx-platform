#!/usr/bin/env bash

cd /edx/app/edxapp/edx-platform
source ../venvs/edxapp/bin/activate
python manage.py lms --settings=aws update_biz_score_status 72
sleep 60
python manage.py lms --settings=aws update_biz_score_status 73
sleep 60
python manage.py lms --settings=aws update_biz_score_status 74
sleep 60
python manage.py lms --settings=aws update_biz_score_status 75
sleep 60
python manage.py lms --settings=aws update_biz_score_status 76
sleep 60
python manage.py lms --settings=aws update_biz_score_status 77
sleep 60
python manage.py lms --settings=aws update_biz_score_status 78
sleep 60
python manage.py lms --settings=aws update_biz_score_status 79
sleep 60
python manage.py lms --settings=aws update_biz_score_status 80
sleep 60
python manage.py lms --settings=aws update_biz_score_status 81
sleep 60
python manage.py lms --settings=aws update_biz_score_status 82
sleep 60
python manage.py lms --settings=aws update_biz_score_status 83
sleep 60
python manage.py lms --settings=aws update_biz_score_status 86

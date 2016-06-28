#!/usr/bin/env bash

#
# Attention!!
# This script must run on 1st day of each month. Be care!!
#

cd /edx/app/edxapp/edx-platform
source ../venvs/edxapp/bin/activate
python manage.py lms --settings=aws monthly_report_biz_register_user `date -d "1 month ago" "+%Y %m"`

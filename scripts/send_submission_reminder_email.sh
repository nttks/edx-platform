#!/usr/bin/env bash

db_con="${1}"
sql="\"${2}\""
ContractId=`echo "$(eval ${db_con} -e ${sql} )" | sed 1d  `
cd /edx/app/edxapp/edx-platform
source ../venvs/edxapp/bin/activate
for i in `echo ${ContractId} | tr ',' ' '`; do
    python manage.py lms --settings=aws send_submission_reminder_email ${i}
    sleep 60
done

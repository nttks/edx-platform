"""
URLconf for contract_operation views
"""
from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.ga_contract_operation.views',

    url(r'^students$', 'students', name='students'),
    url(r'^register_students$', 'register_students', name='register_students'),
    url(r'^register_students/register_additional_info$', 'register_additional_info_ajax', name='register_additional_info_ajax'),
    url(r'^register_students/edit_additional_info$', 'edit_additional_info_ajax', name='edit_additional_info_ajax'),
    url(r'^register_students/delete_additional_info$', 'delete_additional_info_ajax', name='delete_additional_info_ajax'),
    url(r'^register_students/update_additional_info$', 'update_additional_info_ajax', name='update_additional_info_ajax'),
    url(r'^bulk_students$', 'bulk_students', name='bulk_students'),
    url(r'^register_students_ajax$', 'register_students_ajax', name='register_students_ajax'),
    url(r'^unregister_students_ajax$', 'unregister_students_ajax', name='unregister_students_ajax'),
    url(r'^personalinfo_mask$', 'submit_personalinfo_mask', name='personalinfo_mask'),
    url(r'^bulk_unregister_students_ajax$', 'bulk_unregister_students_ajax', name='bulk_unregister_students_ajax'),
    url(r'^bulk_personalinfo_mask_ajax$', 'bulk_personalinfo_mask_ajax', name='bulk_personalinfo_mask_ajax'),
    url(r'^task_history_ajax', 'task_history_ajax', name='task_history'),
    url(r'^register_mail$', 'register_mail', name='register_mail'),
    url(r'^register_mail_ajax$', 'register_mail_ajax', name='register_mail_ajax'),
    url(r'^send_mail_ajax$', 'send_mail_ajax', name='send_mail_ajax'),
    url(r'^reminder_mail$', 'reminder_mail', name='reminder_mail'),
    url(r'^reminder_mail_save_ajax$', 'reminder_mail_save_ajax', name='reminder_mail_save_ajax'),
    url(r'^reminder_mail_send_ajax$', 'reminder_mail_send_ajax', name='reminder_mail_send_ajax'),
)

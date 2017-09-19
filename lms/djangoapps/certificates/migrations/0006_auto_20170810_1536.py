# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import xmodule_django.models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('certificates', '0005_auto_20151208_0801'),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificatesOnUserProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, serialize=False, editable=False, primary_key=True)),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255)),
                ('is_visible_to_public', models.BooleanField(default=0)),
                ('created', models.DateTimeField(db_index=True, auto_now_add=True, null=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='certificatesonuserprofile',
            unique_together=set([('user', 'course_id')]),
        ),
    ]

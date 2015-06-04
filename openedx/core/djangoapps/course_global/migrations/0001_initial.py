# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'CourseGlobalSetting'
        db.create_table('course_global_courseglobalsetting', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('course_id', self.gf('xmodule_django.models.CourseKeyField')(unique=True, max_length=255, db_index=True)),
            ('global_enabled', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('course_global', ['CourseGlobalSetting'])


    def backwards(self, orm):
        # Deleting model 'CourseGlobalSetting'
        db.delete_table('course_global_courseglobalsetting')


    models = {
        'course_global.courseglobalsetting': {
            'Meta': {'object_name': 'CourseGlobalSetting'},
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'unique': 'True', 'max_length': '255', 'db_index': 'True'}),
            'global_enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['course_global']

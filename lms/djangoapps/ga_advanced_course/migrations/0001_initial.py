# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'AdvancedCourse'
        db.create_table('ga_advanced_course_advancedcourse', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('course_id', self.gf('xmodule_django.models.CourseKeyField')(max_length=255, db_index=True)),
            ('display_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('start_date', self.gf('django.db.models.fields.DateField')()),
            ('start_time', self.gf('django.db.models.fields.TimeField')()),
            ('end_time', self.gf('django.db.models.fields.TimeField')()),
            ('capacity', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=1000)),
            ('content', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('ga_advanced_course', ['AdvancedCourse'])

        # Adding model 'AdvancedCourseTicket'
        db.create_table('ga_advanced_course_advancedcourseticket', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('advanced_course', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ga_advanced_course.AdvancedCourse'])),
            ('display_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('price', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('sell_by_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('display_order', self.gf('django.db.models.fields.IntegerField')(default=99)),
        ))
        db.send_create_signal('ga_advanced_course', ['AdvancedCourseTicket'])

        # Adding model 'AdvancedF2FCourse'
        db.create_table('ga_advanced_course_advancedf2fcourse', (
            ('advancedcourse_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['ga_advanced_course.AdvancedCourse'], unique=True, primary_key=True)),
            ('place_name', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
            ('place_link', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
            ('place_address', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('place_access', self.gf('django.db.models.fields.CharField')(max_length=1000, blank=True)),
        ))
        db.send_create_signal('ga_advanced_course', ['AdvancedF2FCourse'])


    def backwards(self, orm):
        # Deleting model 'AdvancedCourse'
        db.delete_table('ga_advanced_course_advancedcourse')

        # Deleting model 'AdvancedCourseTicket'
        db.delete_table('ga_advanced_course_advancedcourseticket')

        # Deleting model 'AdvancedF2FCourse'
        db.delete_table('ga_advanced_course_advancedf2fcourse')


    models = {
        'ga_advanced_course.advancedcourse': {
            'Meta': {'object_name': 'AdvancedCourse'},
            'capacity': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'content': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1000'}),
            'display_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'end_time': ('django.db.models.fields.TimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'start_date': ('django.db.models.fields.DateField', [], {}),
            'start_time': ('django.db.models.fields.TimeField', [], {})
        },
        'ga_advanced_course.advancedcourseticket': {
            'Meta': {'object_name': 'AdvancedCourseTicket'},
            'advanced_course': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['ga_advanced_course.AdvancedCourse']"}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'display_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'display_order': ('django.db.models.fields.IntegerField', [], {'default': '99'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'price': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'sell_by_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        'ga_advanced_course.advancedf2fcourse': {
            'Meta': {'object_name': 'AdvancedF2FCourse', '_ormbases': ['ga_advanced_course.AdvancedCourse']},
            'advancedcourse_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['ga_advanced_course.AdvancedCourse']", 'unique': 'True', 'primary_key': 'True'}),
            'place_access': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'blank': 'True'}),
            'place_address': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'place_link': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'place_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        }
    }

    complete_apps = ['ga_advanced_course']
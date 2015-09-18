# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'MaintenanceMessage'
        db.create_table('ga_maintenance_cms_maintenancemessage', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('message', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('display_order', self.gf('django.db.models.fields.IntegerField')(default=1)),
            ('display_flg', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('ga_maintenance_cms', ['MaintenanceMessage'])


    def backwards(self, orm):
        # Deleting model 'MaintenanceMessage'
        db.delete_table('ga_maintenance_cms_maintenancemessage')


    models = {
        'ga_maintenance_cms.maintenancemessage': {
            'Meta': {'ordering': "['-display_order']", 'object_name': 'MaintenanceMessage'},
            'display_flg': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'display_order': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['ga_maintenance_cms']
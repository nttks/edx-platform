# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'TrustedClient'
        db.create_table('ga_ratelimitbackend_trustedclient', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ip_address', self.gf('django.db.models.fields.GenericIPAddressField')(unique=True, max_length=39, db_index=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100, blank=True)),
        ))
        db.send_create_signal('ga_ratelimitbackend', ['TrustedClient'])


    def backwards(self, orm):
        # Deleting model 'TrustedClient'
        db.delete_table('ga_ratelimitbackend_trustedclient')


    models = {
        'ga_ratelimitbackend.trustedclient': {
            'Meta': {'object_name': 'TrustedClient'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_address': ('django.db.models.fields.GenericIPAddressField', [], {'unique': 'True', 'max_length': '39', 'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        }
    }

    complete_apps = ['ga_ratelimitbackend']
# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Contract'
        db.create_table('ga_contract_contract', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('contract_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('contract_type', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('invitation_code', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('contractor_organization', self.gf('django.db.models.fields.related.ForeignKey')(related_name='org_contractor_contracts', to=orm['ga_organization.Organization'])),
            ('owner_organization', self.gf('django.db.models.fields.related.ForeignKey')(related_name='org_owner_contracts', to=orm['ga_organization.Organization'])),
            ('start_date', self.gf('django.db.models.fields.DateField')()),
            ('end_date', self.gf('django.db.models.fields.DateField')()),
            ('created_by', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
        ))
        db.send_create_signal('ga_contract', ['Contract'])

        # Adding model 'ContractDetail'
        db.create_table('ga_contract_contractdetail', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('contract', self.gf('django.db.models.fields.related.ForeignKey')(related_name='details', to=orm['ga_contract.Contract'])),
            ('course_id', self.gf('xmodule_django.models.CourseKeyField')(max_length=255, db_index=True)),
        ))
        db.send_create_signal('ga_contract', ['ContractDetail'])

        # Adding model 'AdditionalInfo'
        db.create_table('ga_contract_additionalinfo', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('contract', self.gf('django.db.models.fields.related.ForeignKey')(related_name='additional_info', to=orm['ga_contract.Contract'])),
            ('display_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('ga_contract', ['AdditionalInfo'])

        # Adding unique constraint on 'AdditionalInfo', fields ['contract', 'display_name']
        db.create_unique('ga_contract_additionalinfo', ['contract_id', 'display_name'])


    def backwards(self, orm):
        # Removing unique constraint on 'AdditionalInfo', fields ['contract', 'display_name']
        db.delete_unique('ga_contract_additionalinfo', ['contract_id', 'display_name'])

        # Deleting model 'Contract'
        db.delete_table('ga_contract_contract')

        # Deleting model 'ContractDetail'
        db.delete_table('ga_contract_contractdetail')

        # Deleting model 'AdditionalInfo'
        db.delete_table('ga_contract_additionalinfo')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'ga_contract.additionalinfo': {
            'Meta': {'unique_together': "(('contract', 'display_name'),)", 'object_name': 'AdditionalInfo'},
            'contract': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'additional_info'", 'to': "orm['ga_contract.Contract']"}),
            'display_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'ga_contract.contract': {
            'Meta': {'object_name': 'Contract'},
            'contract_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'contract_type': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'contractor_organization': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'org_contractor_contracts'", 'to': "orm['ga_organization.Organization']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'end_date': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'invitation_code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'owner_organization': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'org_owner_contracts'", 'to': "orm['ga_organization.Organization']"}),
            'start_date': ('django.db.models.fields.DateField', [], {})
        },
        'ga_contract.contractdetail': {
            'Meta': {'object_name': 'ContractDetail'},
            'contract': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'details'", 'to': "orm['ga_contract.Contract']"}),
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '255', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'ga_organization.organization': {
            'Meta': {'object_name': 'Organization'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'creator_org': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'creator_orgs'", 'to': "orm['ga_organization.Organization']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'org_code': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'org_name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['ga_contract']
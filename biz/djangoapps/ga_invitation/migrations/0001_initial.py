# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'AdditionalInfoSetting'
        db.create_table('ga_invitation_additionalinfosetting', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('contract', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ga_contract.Contract'])),
            ('display_name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('value', self.gf('django.db.models.fields.CharField')(default='', max_length=255)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('ga_invitation', ['AdditionalInfoSetting'])

        # Adding unique constraint on 'AdditionalInfoSetting', fields ['contract', 'user', 'display_name']
        db.create_unique('ga_invitation_additionalinfosetting', ['contract_id', 'user_id', 'display_name'])

        # Adding model 'ContractRegister'
        db.create_table('ga_invitation_contractregister', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('contract', self.gf('django.db.models.fields.related.ForeignKey')(related_name='contract_register', to=orm['ga_contract.Contract'])),
            ('status', self.gf('django.db.models.fields.CharField')(default='Input', max_length=255)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('ga_invitation', ['ContractRegister'])

        # Adding unique constraint on 'ContractRegister', fields ['contract', 'user']
        db.create_unique('ga_invitation_contractregister', ['contract_id', 'user_id'])

        # Adding model 'ContractRegisterHistory'
        db.create_table('ga_invitation_contractregisterhistory', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('contract', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ga_contract.Contract'])),
            ('status', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('created', self.gf('django.db.models.fields.DateTimeField')()),
            ('modified', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal('ga_invitation', ['ContractRegisterHistory'])


    def backwards(self, orm):
        # Removing unique constraint on 'ContractRegister', fields ['contract', 'user']
        db.delete_unique('ga_invitation_contractregister', ['contract_id', 'user_id'])

        # Removing unique constraint on 'AdditionalInfoSetting', fields ['contract', 'user', 'display_name']
        db.delete_unique('ga_invitation_additionalinfosetting', ['contract_id', 'user_id', 'display_name'])

        # Deleting model 'AdditionalInfoSetting'
        db.delete_table('ga_invitation_additionalinfosetting')

        # Deleting model 'ContractRegister'
        db.delete_table('ga_invitation_contractregister')

        # Deleting model 'ContractRegisterHistory'
        db.delete_table('ga_invitation_contractregisterhistory')


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
        'ga_invitation.additionalinfosetting': {
            'Meta': {'unique_together': "(('contract', 'user', 'display_name'),)", 'object_name': 'AdditionalInfoSetting'},
            'contract': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['ga_contract.Contract']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'display_name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'value': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255'})
        },
        'ga_invitation.contractregister': {
            'Meta': {'unique_together': "(('contract', 'user'),)", 'object_name': 'ContractRegister'},
            'contract': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'contract_register'", 'to': "orm['ga_contract.Contract']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'Input'", 'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'ga_invitation.contractregisterhistory': {
            'Meta': {'object_name': 'ContractRegisterHistory'},
            'contract': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['ga_contract.Contract']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
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

    complete_apps = ['ga_invitation']
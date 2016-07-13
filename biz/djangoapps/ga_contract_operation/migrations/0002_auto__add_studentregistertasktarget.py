# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'StudentRegisterTaskTarget'
        db.create_table('ga_contract_operation_studentregistertasktarget', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('history', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ga_contract_operation.ContractTaskHistory'])),
            ('student', self.gf('django.db.models.fields.CharField')(max_length=1024)),
            ('message', self.gf('django.db.models.fields.CharField')(max_length=1024, null=True)),
            ('completed', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('modified', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
        ))
        db.send_create_signal('ga_contract_operation', ['StudentRegisterTaskTarget'])


    def backwards(self, orm):
        # Deleting model 'StudentRegisterTaskTarget'
        db.delete_table('ga_contract_operation_studentregistertasktarget')


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
        'ga_contract_operation.contracttaskhistory': {
            'Meta': {'object_name': 'ContractTaskHistory'},
            'contract': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['ga_contract.Contract']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'requester': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"}),
            'task_id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'db_index': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        'ga_contract_operation.contracttasktarget': {
            'Meta': {'unique_together': "(('history', 'register'),)", 'object_name': 'ContractTaskTarget'},
            'completed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'history': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['ga_contract_operation.ContractTaskHistory']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'register': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['ga_invitation.ContractRegister']"})
        },
        'ga_contract_operation.studentregistertasktarget': {
            'Meta': {'object_name': 'StudentRegisterTaskTarget'},
            'completed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'history': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['ga_contract_operation.ContractTaskHistory']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'student': ('django.db.models.fields.CharField', [], {'max_length': '1024'})
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

    complete_apps = ['ga_contract_operation']
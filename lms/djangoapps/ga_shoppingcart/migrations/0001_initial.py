# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'AdvancedCourseItem'
        db.create_table('ga_shoppingcart_advancedcourseitem', (
            ('orderitem_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['shoppingcart.OrderItem'], unique=True, primary_key=True)),
            ('course_id', self.gf('xmodule_django.models.CourseKeyField')(max_length=128, db_index=True)),
            ('advanced_course_ticket', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['ga_advanced_course.AdvancedCourseTicket'])),
            ('tax', self.gf('django.db.models.fields.DecimalField')(default=0.0, max_digits=30, decimal_places=2)),
        ))
        db.send_create_signal('ga_shoppingcart', ['AdvancedCourseItem'])


    def backwards(self, orm):
        # Deleting model 'AdvancedCourseItem'
        db.delete_table('ga_shoppingcart_advancedcourseitem')


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
        'ga_shoppingcart.advancedcourseitem': {
            'Meta': {'object_name': 'AdvancedCourseItem', '_ormbases': ['shoppingcart.OrderItem']},
            'advanced_course_ticket': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['ga_advanced_course.AdvancedCourseTicket']"}),
            'course_id': ('xmodule_django.models.CourseKeyField', [], {'max_length': '128', 'db_index': 'True'}),
            'orderitem_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['shoppingcart.OrderItem']", 'unique': 'True', 'primary_key': 'True'}),
            'tax': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '30', 'decimal_places': '2'})
        },
        'shoppingcart.order': {
            'Meta': {'object_name': 'Order'},
            'bill_to_cardtype': ('django.db.models.fields.CharField', [], {'max_length': '32', 'blank': 'True'}),
            'bill_to_ccnum': ('django.db.models.fields.CharField', [], {'max_length': '8', 'blank': 'True'}),
            'bill_to_city': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'bill_to_country': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'bill_to_first': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'bill_to_last': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'bill_to_postalcode': ('django.db.models.fields.CharField', [], {'max_length': '16', 'blank': 'True'}),
            'bill_to_state': ('django.db.models.fields.CharField', [], {'max_length': '8', 'blank': 'True'}),
            'bill_to_street1': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'bill_to_street2': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'company_contact_email': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'company_contact_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'company_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'currency': ('django.db.models.fields.CharField', [], {'default': "'usd'", 'max_length': '8'}),
            'customer_reference_number': ('django.db.models.fields.CharField', [], {'max_length': '63', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'order_type': ('django.db.models.fields.CharField', [], {'default': "'personal'", 'max_length': '32'}),
            'processor_reply_dump': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'purchase_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'recipient_email': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'recipient_name': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'refunded_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'cart'", 'max_length': '32'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'shoppingcart.orderitem': {
            'Meta': {'object_name': 'OrderItem'},
            'created': ('model_utils.fields.AutoCreatedField', [], {'default': 'datetime.datetime.now'}),
            'currency': ('django.db.models.fields.CharField', [], {'default': "'usd'", 'max_length': '8'}),
            'fulfilled_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'line_desc': ('django.db.models.fields.CharField', [], {'default': "'Misc. Item'", 'max_length': '1024'}),
            'list_price': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '30', 'decimal_places': '2'}),
            'modified': ('model_utils.fields.AutoLastModifiedField', [], {'default': 'datetime.datetime.now'}),
            'order': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['shoppingcart.Order']"}),
            'qty': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'refund_requested_time': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'db_index': 'True'}),
            'report_comments': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'service_fee': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '30', 'decimal_places': '2'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'cart'", 'max_length': '32', 'db_index': 'True'}),
            'unit_cost': ('django.db.models.fields.DecimalField', [], {'default': '0.0', 'max_digits': '30', 'decimal_places': '2'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        }
    }

    complete_apps = ['ga_shoppingcart']
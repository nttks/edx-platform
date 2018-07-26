# -*- coding: utf-8 -*-
from django import forms
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_login.models import LOGIN_CODE_MIN_LENGTH, LOGIN_CODE_MAX_LENGTH
from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_org_group.models import Group


class MemberUserCreateForm(forms.Form):
    group_code = forms.CharField(max_length=Group._meta.get_field('group_code').max_length, required=False)
    code = forms.CharField(max_length=Member._meta.get_field('code').max_length, required=True)
    login_code = forms.CharField(
        min_length=LOGIN_CODE_MIN_LENGTH, max_length=LOGIN_CODE_MAX_LENGTH, required=False,
        validators=[RegexValidator(regex=r'^[-\w]*$', code='invalid')])
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=User._meta.get_field('first_name').max_length, required=False)
    last_name = forms.CharField(max_length=User._meta.get_field('last_name').max_length, required=False)
    password = forms.CharField(max_length=User._meta.get_field('password').max_length, required=False)
    username = forms.CharField(max_length=User._meta.get_field('username').max_length, required=True)
    org1 = forms.CharField(max_length=Member._meta.get_field('org1').max_length, required=False)
    org2 = forms.CharField(max_length=Member._meta.get_field('org2').max_length, required=False)
    org3 = forms.CharField(max_length=Member._meta.get_field('org3').max_length, required=False)
    org4 = forms.CharField(max_length=Member._meta.get_field('org4').max_length, required=False)
    org5 = forms.CharField(max_length=Member._meta.get_field('org5').max_length, required=False)
    org6 = forms.CharField(max_length=Member._meta.get_field('org6').max_length, required=False)
    org7 = forms.CharField(max_length=Member._meta.get_field('org7').max_length, required=False)
    org8 = forms.CharField(max_length=Member._meta.get_field('org8').max_length, required=False)
    org9 = forms.CharField(max_length=Member._meta.get_field('org9').max_length, required=False)
    org10 = forms.CharField(max_length=Member._meta.get_field('org10').max_length, required=False)
    item1 = forms.CharField(max_length=Member._meta.get_field('item1').max_length, required=False)
    item2 = forms.CharField(max_length=Member._meta.get_field('item2').max_length, required=False)
    item3 = forms.CharField(max_length=Member._meta.get_field('item3').max_length, required=False)
    item4 = forms.CharField(max_length=Member._meta.get_field('item4').max_length, required=False)
    item5 = forms.CharField(max_length=Member._meta.get_field('item5').max_length, required=False)
    item6 = forms.CharField(max_length=Member._meta.get_field('item6').max_length, required=False)
    item7 = forms.CharField(max_length=Member._meta.get_field('item7').max_length, required=False)
    item8 = forms.CharField(max_length=Member._meta.get_field('item8').max_length, required=False)
    item9 = forms.CharField(max_length=Member._meta.get_field('item9').max_length, required=False)
    item10 = forms.CharField(max_length=Member._meta.get_field('item10').max_length, required=False)

    def __init__(self, *args, **kwargs):
        super(MemberUserCreateForm, self).__init__(*args, **kwargs)
        self.fields['group_code'].label = 'Organization'
        self.fields['code'].label = 'Member Code'
        self.fields['first_name'].label = 'First Name'
        self.fields['last_name'].label = 'Last Name'
        self.fields['email'].label = 'Email Address'
        self.fields['username'].label = 'Username'
        self.fields['login_code'].label = 'Login Code'
        self.fields['password'].label = 'Password'

        for i in range(1, 11):
            num = str(i)
            field = self.fields['org' + num]
            field.label = 'Organization'
            field.sequence = num

            field = self.fields['item' + num]
            field.label = 'Item'
            field.sequence = num

    def format_errors(self, line_error=True, line_number="0"):
        """
        Format error messages for display
        :return:
        """
        errors = []
        for key in self.errors:
            field = self.fields[key]
            if hasattr(field, 'sequence'):
                label = _(field.label) + " " + str(field.sequence)
            else:
                label = _(field.label)

            for data in self.errors[key].data:
                if data.code == 'required':
                    message = _('The {0} is required.').format(label)
                elif data.code == 'max_length':
                    message = _('Please enter of {0} within {1} characters.').format(label, field.max_length)
                elif data.code == 'min_length':
                    message = _('Please enter of {0} within {1} characters.').format(label, field.min_length)
                elif data.code == 'invalid':
                    message = _('Illegal format on {0}.').format(label)

                errors.append(_("Line {line_number}:{message}").format(
                    line_number=line_number, message=message) if line_error else message)

        return errors

"""
Django admin page for ga_login models
"""
import re

from django import forms
from django.contrib import admin
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract.models import ContractAuth, ContractOption, URL_CODE_PATTERN, URL_CODE_MIN_LENGTH, URL_CODE_MAX_LENGTH


class ContractAuthForm(forms.ModelForm):

    def __init__(self, *args, **kargs):
        if not kargs.has_key('instance'):
            if not kargs.has_key('initial'):
                kargs['initial'] = {}
            kargs['initial']['url_code'] = get_random_string(16)
        super(ContractAuthForm, self).__init__(*args, **kargs)

    def clean(self):
        url_code = self.cleaned_data['url_code'] if 'url_code' in self.cleaned_data else None
        if url_code is None or not re.match(r'^{url_code}$'.format(url_code=URL_CODE_PATTERN), url_code):
            raise forms.ValidationError(
                _("Url code is invalid. Please enter alphanumeric {min_length}-{max_length} characters.").format(
                    min_length=URL_CODE_MIN_LENGTH, max_length=URL_CODE_MAX_LENGTH))

        if 'contract' in self.cleaned_data and ContractAuth.objects.filter(url_code=url_code).exclude(contract=self.cleaned_data['contract']).exists():
            raise forms.ValidationError(_("Url code is duplicated. Please change url code."))

        return self.cleaned_data

    class Meta:
        model = ContractAuth
        fields = ['contract', 'url_code', 'send_mail']


class ContractAuthAdmin(admin.ModelAdmin):

    form = ContractAuthForm

    def save_model(self, request, obj, form, change):
        obj.modified_by = request.user
        obj.save()


class ContractOptionAdmin(admin.ModelAdmin):

    exclude = ('modified_by',)

    def save_model(self, request, obj, form, change):
        obj.modified_by = request.user
        obj.save()


admin.site.register(ContractAuth, ContractAuthAdmin)
admin.site.register(ContractOption, ContractOptionAdmin)

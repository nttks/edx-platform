from django import forms
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_organization.models import Organization


class OrganizationForm(forms.ModelForm):
    org_code = forms.RegexField(label='Organization Code', regex=r'^[0-9A-Za-z_-]+$', max_length=255)

    class Meta:
        model = Organization
        fields = ('org_name', 'org_code',)

    def __init__(self, *args, **kwargs):
        super(OrganizationForm, self).__init__(*args, **kwargs)
        org_name_field = self.fields['org_name']
        org_name_field.label = 'Organization Name'
        org_name_field.widget = forms.TextInput(
                attrs={'placeholder': _('max {0} character').format(org_name_field.max_length)})

        org_code_field = self.fields['org_code']
        org_code_field.widget = forms.TextInput(attrs={
            'placeholder': _('max {0} character harf-width alphanumeric or _-').format(org_code_field.max_length)})

        # overwrite django default messages
        for field in self.fields.values():
            field.error_messages = {'required': _("The field is required."), 'invalid': _("Enter a valid value.")}

from django import forms
from django.forms.util import ErrorList
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_contract.models import (
    CONTRACT_TYPE_PF, CONTRACT_TYPE_OWNER_SERVICE, CONTRACT_TYPE_OWNERS, CONTRACT_TYPE_GACCO_SERVICE,
    REGISTER_TYPE,
)
from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.ga_organization.models import Organization

DATE_FORMAT = '%Y/%m/%d'


class ContractForm(forms.ModelForm):
    invitation_code = forms.RegexField(label='Invitation Code', regex=r'^[0-9A-Za-z]+$', min_length=8, max_length=255)
    start_date = forms.DateField(widget=forms.DateInput(format=DATE_FORMAT, attrs={'placeholder': 'YYYY/MM/DD'}))
    end_date = forms.DateField(widget=forms.DateInput(format=DATE_FORMAT, attrs={'placeholder': 'YYYY/MM/DD'}))

    class Meta:
        model = Contract
        fields = (
            'contract_name', 'contract_type', 'register_type', 'invitation_code', 'contractor_organization', 'start_date', 'end_date'
        )

    def __init__(self, org, *args, **kwargs):
        super(ContractForm, self).__init__(*args, **kwargs)
        self.fields['contract_name'].label = 'Contract Name'
        self.fields['contract_name'].widget = forms.TextInput(
                attrs={'placeholder': _('max {0} character').format(self.fields['contract_name'].max_length)})
        self.fields['invitation_code'].widget = forms.TextInput(
                attrs={'placeholder': _('min {0} max {1} character harf-width alphanumeric').format(
                        self.fields['invitation_code'].min_length,
                        self.fields['invitation_code'].max_length)})
        self.fields['contract_type'].label = 'Contract Type'
        self.fields['register_type'].label = 'Register Type'
        self.fields['contractor_organization'].label = 'Contractor Organization Name'
        self.fields['contractor_organization'].empty_label = None
        self.fields['start_date'].label = 'Contract Start Date'
        self.fields['start_date'].input_formats = [DATE_FORMAT]
        self.fields['end_date'].label = 'Contract End Date'
        self.fields['end_date'].input_formats = [DATE_FORMAT]

        # init contract type select list
        if org.id == org.creator_org_id:
            # if platformer
            self.fields['contract_type'].choices = (CONTRACT_TYPE_PF, CONTRACT_TYPE_OWNERS, CONTRACT_TYPE_GACCO_SERVICE)
        else:
            self.fields['contract_type'].choices = (CONTRACT_TYPE_OWNER_SERVICE,)

        self.fields['register_type'].choices = REGISTER_TYPE

        # init contractor select list
        self.fields['contractor_organization'].queryset = Organization.find_by_creator_org_without_itself(org)

        # overwrite django default messages
        for field in self.fields.values():
            field.error_messages = {'required': _("The field is required."), 'invalid': _("Enter a valid value.")}

    def clean_invitation_code(self):
        """
        Checks invitation code can use

        :return: invitation code
        :raise: ValidationError if the invitation code has been used
        """
        invitation_code = self.cleaned_data['invitation_code']
        search_contract = Contract.get_by_invitation_code(invitation_code)
        if search_contract:
            if not self.instance.id or self.instance.id != search_contract.id:
                raise forms.ValidationError(_("The invitation code has been used."))
        return invitation_code

    def clean(self):
        """
        Checks multi fields correlation

        :return: clean data
        """
        cleaned_data = super(ContractForm, self).clean()

        # check contract inputs
        start_date = self.data['start_date']
        end_date = self.data['end_date']
        if start_date > end_date:
            self.errors["contract"] = ErrorList([_("Contract end date is before contract start date.")])

        # check contract detail inputs
        course_id_list = self.data.getlist('detail_course')
        detail_delete_list = self.data.getlist('detail_delete')
        valid_course_id_list = [v for i, v in enumerate(course_id_list) if not detail_delete_list[i]]
        if len(valid_course_id_list) != len(set(valid_course_id_list)):
            self.errors["contract_detail"] = ErrorList(
                    [_("You can not enter duplicate values in {0}.").format(_('Contract Detail Info'))])

        # check contract detail inputs
        display_name_list = self.data.getlist('additional_info_display_name')
        additional_info_delete_list = self.data.getlist('additional_info_delete')
        valid_display_name_list = [v for i, v in enumerate(display_name_list) if not additional_info_delete_list[i]]
        if len(valid_display_name_list) != len(set(valid_display_name_list)):
            self.errors["additional_info"] = ErrorList(
                    [_("You can not enter duplicate values in {0}.").format(_('Additional Info'))])

        return cleaned_data

# -*- coding: utf-8 -*-
import re

from django import forms
from django.conf import settings
from django.forms import CheckboxSelectMultiple, RadioSelect
from django.utils.encoding import force_unicode
from django.utils.html import conditional_escape, escape
from django.utils.translation import ugettext as _

from .models import DiagnosisInfo


class SelectWithDataString(forms.Select):
    def __init__(self, *args, **kwargs):
        super(SelectWithDataString, self).__init__(*args, **kwargs)
        self.data_vals = {}

    def render_option(self, selected_choices, option_value, option_label):
        title_html = (option_label in self.data_vals) and u' data-str="{}" '.format(
            escape(force_unicode(self.data_vals[option_label])) or ''
        )
        option_value = force_unicode(option_value)
        selected_html = (option_value in selected_choices) and u' selected="selected"' or ''
        return u'<option value="{}"{}{}>{}</option>'.format(
            escape(option_value),
            title_html,
            selected_html,
            conditional_escape(force_unicode(option_label))
        )


class ChoiceFieldWithDataVals(forms.ChoiceField):
    def __init__(self, choices=(), *args, **kwargs):
        choice_pairs = [(c[0], c[1]) for c in choices]
        super(ChoiceFieldWithDataVals, self).__init__(choices=choice_pairs, *args, **kwargs)
        self.widget.data_vals = dict([(c[1], c[2]) for c in choices])


class DiagnosisFormMixin(object):
    @staticmethod
    def _check_kana(value):
        if not re.search(u'^[ァ-ヴ][ァ-ヴー・]*$', value):
            raise forms.ValidationError(u'全角カナ以外の文字が含まれています')
        return value

    @staticmethod
    def _check_number(value):
        if not re.match('^[0-9]*$', value):
            raise forms.ValidationError(u'半角数字で入力してください')
        return value

    def _check_block3_09(self, value):
        block3_07_value = self.cleaned_data.get('block3_07')
        if block3_07_value == settings.GA_DIAGNOSIS_CHOICE11[1][0]:
            if value:
                raise forms.ValidationError(settings.GA_DIAGNOSIS_FORM_ERROR_REASON['block3_09'])
            else:
                return ''
        else:
            if value:
                return self._check_number(value)
            else:
                raise forms.ValidationError(u'このフィールドは必須です')


class RegulationChoiceForm(forms.ModelForm):
    regulation_state = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE01, widget=RadioSelect, label='')

    class Meta:
        model = DiagnosisInfo
        fields = ('regulation_state',)


class DiagnosisBlockA1Form(forms.ModelForm, DiagnosisFormMixin):
    block1_01_1 = forms.CharField(max_length=255, label=settings.GA_DIAGNOSIS_BLOCK_A1_LABEL['0101'])
    block1_01_2 = forms.CharField(max_length=255, label=settings.GA_DIAGNOSIS_BLOCK_A1_LABEL['0102'])
    block1_02_1 = forms.CharField(max_length=255, label=settings.GA_DIAGNOSIS_BLOCK_A1_LABEL['0201'])
    block1_02_2 = forms.CharField(max_length=255, label=settings.GA_DIAGNOSIS_BLOCK_A1_LABEL['0202'])
    block1_03 = forms.ChoiceField(label=settings.GA_DIAGNOSIS_BLOCK_A1_LABEL['0300'],
                                  widget=RadioSelect,
                                  choices=settings.GA_DIAGNOSIS_CHOICE02)
    block1_04_1 = forms.ChoiceField(label=settings.GA_DIAGNOSIS_BLOCK_A1_LABEL['0401'],
                                    choices=settings.GA_DIAGNOSIS_CHOICE17)
    block1_04_2 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE18,
                                    label=settings.GA_DIAGNOSIS_BLOCK_A1_LABEL['0402'])
    block1_04_3 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE19,
                                    label=settings.GA_DIAGNOSIS_BLOCK_A1_LABEL['0403'])
    block1_05 = forms.EmailField(max_length=75, label=settings.GA_DIAGNOSIS_BLOCK_A1_LABEL['0500'])
    block1_05_ = forms.EmailField(max_length=75)

    class Meta:
        model = DiagnosisInfo
        fields = (
            'block1_01_1', 'block1_01_2', 'block1_02_1', 'block1_02_2', 'block1_03', 'block1_04_1', 'block1_04_2',
            'block1_04_3', 'block1_05'
        )
        exclude = ('block1_05_',)

    def clean_block1_02_1(self):
        value = self.cleaned_data['block1_02_1']
        return self._check_kana(value)

    def clean_block1_02_2(self):
        value = self.cleaned_data['block1_02_2']
        return self._check_kana(value)

    def clean_block1_04_1(self):
        value = self.cleaned_data['block1_04_1']
        return self._check_number(value)

    def clean_block1_04_2(self):
        value = self.cleaned_data['block1_04_2']
        return self._check_number(value)

    def clean_block1_04_3(self):
        value = self.cleaned_data['block1_04_3']
        return self._check_number(value)

    def clean_block1_05(self):
        value = self.cleaned_data['block1_05']
        if value != self.data['block1_05_']:
            raise forms.ValidationError(u'入力したEメールの値が違います。')
        return value


class DiagnosisBlockA2B1FormBase(forms.ModelForm, DiagnosisFormMixin):
    block2_01 = forms.CharField(max_length=16, label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['01'])
    block2_02 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['02'])
    block2_03 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['03'])
    block2_04 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['04'])
    block2_05 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['05'])
    block2_06 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['06'])
    block2_07 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['07'])
    block2_08 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['08'])
    block2_09 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['09'])
    block2_10 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['10'])
    block2_11 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['11'])
    block2_12 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['12'])
    block2_13 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['13'])
    block2_14 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['14'])
    block2_15 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['15'])
    block2_16 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['16'])
    block2_17 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['17'])
    block2_18 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['18'])
    block2_19 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['19'])
    block2_20 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['20'])
    block2_21 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['21'])
    block2_22 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['22'])
    block2_23 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['23'])
    block2_24 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['24'])
    block2_25 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['25'])
    block2_26 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['26'])
    block2_27 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE08, widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A2_AND_B1_LABEL['27'])

    def clean_block2_01(self):
        value = self.cleaned_data['block2_01']
        return self._check_number(value)

    class Meta:
        model = DiagnosisInfo
        fields = (
            'block2_01', 'block2_02', 'block2_03', 'block2_04', 'block2_05', 'block2_06', 'block2_07', 'block2_08',
            'block2_09', 'block2_10', 'block2_11', 'block2_12', 'block2_13', 'block2_14', 'block2_15', 'block2_16',
            'block2_17', 'block2_18', 'block2_19', 'block2_20', 'block2_21', 'block2_22', 'block2_23', 'block2_24',
            'block2_25', 'block2_26', 'block2_27',
        )


class DiagnosisBlockA2Form(DiagnosisBlockA2B1FormBase):
    pass


class DiagnosisBlockB1Form(DiagnosisBlockA2B1FormBase):
    pass


class DiagnosisBlockA3Form(forms.ModelForm, DiagnosisFormMixin):
    block3_01 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE03,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['01'])
    block3_02 = forms.CharField(max_length=255, label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['02'])
    block3_03_1 = forms.CharField(max_length=5, label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['03'])
    block3_03_2 = forms.CharField(max_length=5)
    block3_03_3 = forms.CharField(max_length=5)
    block3_04 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE06,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['04'])
    block3_05 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE05,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['05'])
    block3_06 = forms.CharField(max_length=255, label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['06'])
    block3_07 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE11,
                                  widget=RadioSelect,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['07'])
    block3_08 = forms.CharField(max_length=255, label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['08'])
    block3_09_1 = forms.ChoiceField(label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['09'],
                                    choices=settings.GA_DIAGNOSIS_CHOICE17)
    block3_09_2 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE18)
    block3_09_3 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE17, required=False)
    block3_09_4 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE18, required=False)
    block3_10 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE09,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['10'])
    block3_11 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE10,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['11'])
    block3_12_ = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE15,
                                   label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['12'],
                                   widget=forms.Select(attrs={'class': 'block3_12'}))
    block3_12 = ChoiceFieldWithDataVals(choices=settings.GA_DIAGNOSIS_CHOICE16,
                                        widget=SelectWithDataString())
    block3_13_ = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE13,
                                   label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['13'],
                                   widget=forms.Select(attrs={'class': 'block3_13'}))
    block3_13 = ChoiceFieldWithDataVals(choices=settings.GA_DIAGNOSIS_CHOICE14,
                                        widget=SelectWithDataString())
    block3_14 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE12,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['14'])
    block3_15 = forms.CharField(max_length=16, label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['15'])
    block3_16 = forms.MultipleChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE04,
                                          label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['16'],
                                          widget=CheckboxSelectMultiple)
    block3_17 = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE07,
                                  label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['17'])
    block3_18_ = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE15,
                                   label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['18'],
                                   widget=forms.Select(attrs={'class': 'block3_18'}))
    block3_18 = ChoiceFieldWithDataVals(choices=settings.GA_DIAGNOSIS_CHOICE16,
                                        widget=SelectWithDataString())
    block3_19 = forms.CharField(max_length=4, label=settings.GA_DIAGNOSIS_BLOCK_A3_LABEL['19'])

    def clean_block3_03_1(self):
        value = self.cleaned_data['block3_03_1']
        return self._check_number(value)

    def clean_block3_03_2(self):
        value = self.cleaned_data['block3_03_2']
        return self._check_number(value)

    def clean_block3_03_3(self):
        value = self.cleaned_data['block3_03_3']
        return self._check_number(value)

    def clean_block3_09_1(self):
        value = self.cleaned_data['block3_09_1']
        return self._check_number(value)

    def clean_block3_09_2(self):
        value = self.cleaned_data['block3_09_2']
        return self._check_number(value)

    def clean_block3_09_3(self):
        value = self.cleaned_data['block3_09_3']
        return self._check_block3_09(value)

    def clean_block3_09_4(self):
        value = self.cleaned_data['block3_09_4']
        return self._check_block3_09(value)

    def clean_block3_12_(self):
        value = self.data.get('block3_12')
        if not value:
            self.data['block3_12_'] = ''
        return self.cleaned_data['block3_12_']

    def clean_block3_13_(self):
        value = self.data.get('block3_13')
        if not value:
            self.data['block3_13_'] = ''
        return self.cleaned_data['block3_13_']

    def clean_block3_18_(self):
        value = self.data.get('block3_18')
        if not value:
            self.data['block3_18_'] = ''
        return self.cleaned_data['block3_18_']

    def clean_block3_15(self):
        value = self.cleaned_data['block3_15']
        return self._check_number(value)

    def clean_block3_16(self):
        value = self.cleaned_data['block3_16']
        return '\n'.join(value)

    def clean_block3_19(self):
        value = self.cleaned_data['block3_19']
        return self._check_number(value)

    class Meta:
        model = DiagnosisInfo
        fields = (
            'block3_01', 'block3_02', 'block3_03_1', 'block3_03_2', 'block3_03_3', 'block3_04', 'block3_05',
            'block3_06', 'block3_07', 'block3_08', 'block3_09_1', 'block3_09_2', 'block3_09_3', 'block3_09_4',
            'block3_10', 'block3_11', 'block3_12_', 'block3_12', 'block3_13_', 'block3_13', 'block3_14', 'block3_15',
            'block3_16', 'block3_17', 'block3_18_', 'block3_18', 'block3_19',
        )
        exclude = ('block3_12_', 'block3_13_', 'block3_18_',)


class DiagnosisBlockB2Form(forms.ModelForm, DiagnosisFormMixin):
    block3_18_ = forms.ChoiceField(choices=settings.GA_DIAGNOSIS_CHOICE15,
                                   label=settings.GA_DIAGNOSIS_BLOCK_B2_LABEL['01'],
                                   widget=forms.Select(attrs={'class': 'block3_18'}))
    block3_18 = ChoiceFieldWithDataVals(choices=settings.GA_DIAGNOSIS_CHOICE16, widget=SelectWithDataString())
    block3_19 = forms.CharField(max_length=4, label=settings.GA_DIAGNOSIS_BLOCK_B2_LABEL['02'])
    block2b_3 = forms.CharField(max_length=3, label=settings.GA_DIAGNOSIS_BLOCK_B2_LABEL['03'])

    def clean_block3_18_(self):
        value = self.data.get('block3_18')
        if not value:
            self.data['block3_18_'] = ''
        return self.cleaned_data['block3_18_']

    def clean_block3_19(self):
        value = self.cleaned_data['block3_19']
        return self._check_number(value)

    def clean_block2b_3(self):
        value = self.cleaned_data['block2b_3']
        return self._check_number(value)

    class Meta:
        model = DiagnosisInfo
        fields = ('block3_18', 'block3_19', 'block2b_3',)
        exclude = ('block3_18_',)

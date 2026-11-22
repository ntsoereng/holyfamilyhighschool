from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model

from .models import (AcademicSubject, Enrollment, FamilyAccess, FeeClearance, Mark,
                     PortalAccount, ReportingPeriod, ReportDetails, ReportPolicy, SchoolClass, Student, TeachingAssignment)
from .permissions import is_manager


class PortalAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not is_manager(user) and not PortalAccount.objects.filter(user=user).exists():
            raise forms.ValidationError('This account does not have school portal access.', code='no_portal_access')


class AccountCreationForm(UserCreationForm):
    role = forms.ChoiceField(choices=PortalAccount.Role.choices)
    first_name = forms.CharField(max_length=150, label='Given names')
    last_name = forms.CharField(max_length=150, label='Surname')
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email')


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['admission_number', 'student_number', 'full_name', 'active']


class ClassForm(forms.ModelForm):
    class Meta:
        model = SchoolClass
        fields = ['name', 'year', 'stream', 'class_teacher_name']


class PeriodForm(forms.ModelForm):
    class Meta:
        model = ReportingPeriod
        fields = ['year', 'quarter', 'is_open', 'reopens_on']
        widgets = {'reopens_on': forms.DateInput(attrs={'type': 'date'})}


class SubjectForm(forms.ModelForm):
    class Meta:
        model = AcademicSubject
        fields = ['name', 'code', 'include_in_summary']


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['student', 'classroom']


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = TeachingAssignment
        fields = ['teacher', 'classroom', 'period', 'subject']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].queryset = PortalAccount.objects.filter(role=PortalAccount.Role.TEACHER, user__is_active=True).select_related('user')


class AssignmentAccessForm(forms.ModelForm):
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={'rows': 2}))
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    class Meta:
        model = TeachingAssignment
        fields = ['teacher', 'active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].queryset = PortalAccount.objects.filter(role=PortalAccount.Role.TEACHER, user__is_active=True).select_related('user')


class FamilyAccessForm(forms.ModelForm):
    verification_note = forms.CharField(max_length=500, help_text='Record how the identity and relationship were verified.', widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = FamilyAccess
        fields = ['account', 'student', 'relationship']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = PortalAccount.objects.filter(role=PortalAccount.Role.FAMILY, user__is_active=True).select_related('user')


class FeeForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    class Meta:
        model = FeeClearance
        fields = ['outstanding', 'cleared', 'note']
        widgets = {'note': forms.Textarea(attrs={'rows': 3})}


class ReasonForm(forms.Form):
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={'rows': 2}))


class RevisionActionForm(ReasonForm):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class MarkRowForm(forms.Form):
    enrollment = forms.IntegerField(widget=forms.HiddenInput)
    status = forms.ChoiceField(choices=[('', 'Not entered')] + list(Mark.Status.choices), required=False)
    score = forms.DecimalField(min_value=0, max_value=100, max_digits=5, decimal_places=2, required=False,
                               widget=forms.NumberInput(attrs={'step': '0.01', 'min': 0, 'max': 100, 'aria-label': 'Mark out of 100'}))
    comment = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={'rows': 2, 'aria-label': 'Subject comment'}))

    teacher_remark = forms.ChoiceField(required=False, label="Teacher's remarks")

    def __init__(self, *args, bands=None, **kwargs):
        super().__init__(*args, **kwargs)
        bands = bands if bands is not None else (ReportPolicy.objects.filter(pk=1).first() or ReportPolicy()).bands
        descriptions = list(dict.fromkeys(b['description'] for b in bands))
        self.fields['teacher_remark'].choices = [('', 'Automatic from final mark')] + [(d, d) for d in descriptions]

    def clean(self):
        data = super().clean()
        status, score, comment = data.get('status'), data.get('score'), data.get('comment', '')
        if not status:
            if score is not None or comment or data.get('teacher_remark'):
                raise forms.ValidationError('Choose a mark status, or leave all fields blank.')
        elif status == Mark.Status.SCORED:
            if score is None:
                self.add_error('score', 'Enter a mark out of 100.')
        elif data.get('teacher_remark'):
            self.add_error('teacher_remark', 'Remarks from the grading scale apply only to numeric marks.')
        elif score is not None or not comment:
            raise forms.ValidationError('Absence or exemption requires a comment and no numeric mark.')
        return data


MarkFormSet = forms.formset_factory(MarkRowForm, extra=0, max_num=200, absolute_max=200, validate_max=True)


class SheetActionForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=[('save', 'Save draft'), ('submit', 'Submit for review')])


class ReportBatchForm(forms.Form):
    classroom = forms.ModelChoiceField(queryset=SchoolClass.objects.all())
    period = forms.ModelChoiceField(queryset=ReportingPeriod.objects.all())

    def clean(self):
        data = super().clean()
        if data.get('classroom') and data.get('period') and data['classroom'].year != data['period'].year:
            raise forms.ValidationError('Choose a class and quarter from the same academic year.')
        return data


class PolicyForm(forms.ModelForm):
    grading_bands = forms.CharField(widget=forms.Textarea(attrs={'rows': 14}),
        help_text='One band per line: minimum percentage | grade | description. Include a band starting at 0. Example: 80 | A | Excellent.')
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    class Meta:
        model = ReportPolicy
        fields = ['heading', 'closing_note', 'show_average', 'pass_mark', 'result_basis', 'principal_name', 'report_footer']
        widgets = {'closing_note': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['grading_bands'] = '\n'.join(f"{b['minimum']} | {b['grade']} | {b['description']}" for b in self.instance.bands)
        self.initial['revision'] = self.instance.revision

    def clean_grading_bands(self):
        bands = []
        try:
            for line in self.cleaned_data['grading_bands'].splitlines():
                if not line.strip():
                    continue
                minimum, grade, description = (part.strip() for part in line.split('|'))
                value = Decimal(minimum)
                if (not value.is_finite() or value < 0 or value > 100 or value.as_tuple().exponent < -2
                        or not 1 <= len(grade) <= 12 or not 1 <= len(description) <= 100):
                    raise ValueError
                bands.append({'minimum': str(value), 'grade': grade, 'description': description})
            minima = [Decimal(b['minimum']) for b in bands]
            if not 1 <= len(bands) <= 20 or min(minima) != 0 or len(set(minima)) != len(minima):
                raise ValueError
        except (ValueError, InvalidOperation):
            raise forms.ValidationError('Use unique minimum percentages from 0 to 100 (up to 2 decimal places), a grade (1–12 characters) and a description (1–100 characters), separated by |. Include 0 and at most 20 bands.')
        return sorted(bands, key=lambda b: Decimal(b['minimum']), reverse=True)


class ReportDetailsForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    class Meta:
        model = ReportDetails
        fields = ['days_absent', 'class_teacher_remark', 'principal_remark']
        widgets = {name: forms.Textarea(attrs={'rows': 3}) for name in ['class_teacher_remark', 'principal_remark']}

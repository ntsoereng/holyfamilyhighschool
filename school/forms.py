from django import forms
from datetime import date
from django.utils import timezone
from .models import Application, SiteSettings, DISTRICT_CHOICES

class ApplicationForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    surname = forms.CharField(label='Your surname', max_length=80,
        widget=forms.TextInput(attrs={'autocomplete': 'family-name'}))
    given_name = forms.CharField(label='Your name', max_length=80,
        widget=forms.TextInput(attrs={'autocomplete': 'given-name'}))
    district = forms.ChoiceField(label='Your district', choices=[('', 'Select your district'), *DISTRICT_CHOICES])
    current_school = forms.CharField(label='Your primary school', max_length=180)
    boarding_required = forms.TypedChoiceField(label='Would you like to apply for boarding?',
        choices=[('yes', 'Yes'), ('no', 'No')], coerce=lambda value: value == 'yes',
        empty_value=None, widget=forms.RadioSelect)
    consent = forms.BooleanField(label='My parent or guardian agrees to the school using these details to process my application.')
    class Meta:
        model = Application
        fields = ['surname', 'given_name', 'date_of_birth', 'physical_address', 'district', 'district_other',
                  'current_school', 'guardian_name', 'phone', 'boarding_required', 'consent']
        widgets = {'date_of_birth': forms.DateInput(attrs={'type': 'date', 'min': '1900-01-01'}),
                   'physical_address': forms.Textarea(attrs={'rows': 3, 'autocomplete': 'street-address'}),
                   'guardian_name': forms.TextInput(attrs={'autocomplete': 'name'}),
                   'phone': forms.TextInput(attrs={'autocomplete': 'tel', 'inputmode': 'tel'})}
        labels = {'date_of_birth': 'Your date of birth', 'physical_address': 'Your physical address', 'guardian_name': 'Your parent or guardian’s full name',
                  'phone': 'Your parent or guardian’s contact number',
                  'consent': 'My parent or guardian agrees to the school using these details to process my application.'}
        help_texts = {'district_other': 'If you selected Other, enter your district or location.'}

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school or SiteSettings()

    def clean_date_of_birth(self):
        dob = self.cleaned_data['date_of_birth']
        if dob < date(1900, 1, 1):
            raise forms.ValidationError('Enter a date of birth on or after 1 January 1900.')
        if dob >= timezone.localdate():
            raise forms.ValidationError('Enter a date of birth in the past.')
        return dob

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('district') == 'Other':
            if not cleaned.get('district_other'):
                self.add_error('district_other', 'Enter your district or location.')
        else:
            cleaned['district_other'] = ''
        return cleaned

    def save(self, commit=True):
        application = super().save(commit=False)
        application.learner_name = f'{self.cleaned_data["given_name"]} {self.cleaned_data["surname"]}'
        application.entry_level = self.school.admissions_grade
        application.application_year = self.school.admissions_year
        if commit:
            application.save()
            self.save_m2m()
        return application
    def clean_consent(self):
        if not self.cleaned_data['consent']:
            raise forms.ValidationError('Parent or guardian consent is required.')
        return True
    def clean_website(self):
        if self.cleaned_data['website']:
            raise forms.ValidationError('Unable to submit this application.')
        return ''


class ContactForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    consent = forms.BooleanField(label='I agree that the school may use these details to respond to my enquiry.')

    class Meta:
        from .models import ContactMessage
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'subject', 'message', 'consent']
        labels = {'name': 'Your name', 'email': 'Email address', 'phone': 'Phone number'}
        widgets = {'message': forms.Textarea(attrs={'rows': 6}),
                   'name': forms.TextInput(attrs={'autocomplete': 'name'}),
                   'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
                   'phone': forms.TextInput(attrs={'autocomplete': 'tel'})}

    def clean_website(self):
        if self.cleaned_data['website']:
            raise forms.ValidationError('Unable to send this message.')
        return ''

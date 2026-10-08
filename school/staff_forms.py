from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from .models import Article, Event, SchoolValue, SiteSettings, Application, ContactMessage, Department, StaffMember, Subject, SchoolStatistic
from .security import normalize_google_maps_embed

ADMISSIONS_CYCLE_FIELDS = ['admissions_grade', 'admissions_year', 'admissions_fee',
    'admissions_payment_method', 'admissions_merchant_number', 'admissions_deadline',
    'admissions_interview_date', 'admissions_interview_time', 'admissions_interview_location',
    'admissions_interview_subjects', 'admissions_stationery_note']


class StaffAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError('This account does not have staff access.', code='not_staff')


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'slug', 'category', 'excerpt', 'body', 'image', 'image_alt', 'published', 'published_at']
        widgets = {'body': forms.Textarea(attrs={'class': 'rich-editor'}), 'published_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})}
        help_texts = {'slug': 'The unique address for this story, for example school-open-day.',
                      'published': 'Uncheck to keep this story as a draft.',
                      'published_at': 'Local Lesotho time. A future date schedules publication.'}


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'slug', 'description', 'image', 'image_alt', 'location', 'starts_at', 'ends_at', 'published']
        widgets = {field: forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})
                   for field in ['starts_at', 'ends_at']} | {'description': forms.Textarea(attrs={'class': 'rich-editor'})}
        help_texts = {'starts_at': 'Local Lesotho time.', 'ends_at': 'Optional. Local Lesotho time.'}


class ValueForm(forms.ModelForm):
    class Meta:
        model = SchoolValue
        fields = ['title', 'description', 'order']


class SettingsForm(forms.ModelForm):
    google_maps_embed_url = forms.CharField(label='Google Maps embed', required=False, max_length=10000,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='In Google Maps choose Share → Embed a map. Paste the embed URL or the complete iframe. Only the validated Google Maps URL is saved. Leave blank to hide the map.')

    class Meta:
        model = SiteSettings
        help_texts = {'hero_image': 'Homepage hero photograph. Leave empty or clear the image to use the Holy Family gradient and crest.',
                      'hero_image_alt': 'Describe the homepage photograph for visitors using a screen reader.'}
        fields = ['name', 'motto', 'logo', 'hero_eyebrow', 'hero_title', 'hero_text', 'hero_image', 'hero_image_alt',
                  'footer_text', 'contact_heading', 'contact_text', 'facebook_url', 'statistics_title', 'statistics_text', 'about_title', 'about_text', 'address', 'office_hours', 'email', 'phone', 'google_maps_embed_url', 'admissions_open',
                  'admissions_heading', 'admissions_text', 'admissions_requirements', 'privacy_text', 'demo_mode', 'about_heading', 'about_intro', 'about_history', 'about_mission', 'about_vision', 'curriculum_heading', 'curriculum_intro', 'curriculum_body', 'staff_heading', 'staff_intro', 'calendar_heading', 'calendar_intro', 'about_image', 'about_image_alt', 'curriculum_image', 'curriculum_image_alt', 'staff_image', 'staff_image_alt', 'calendar_image', 'calendar_image_alt', 'contact_image', 'contact_image_alt', 'admissions_image', 'admissions_image_alt'] + ADMISSIONS_CYCLE_FIELDS
        widgets = {name: forms.Textarea(attrs={'rows': 4}) for name in
                   ['hero_text', 'about_text', 'address', 'admissions_text', 'admissions_requirements', 'privacy_text', 'about_intro', 'about_mission', 'about_vision', 'curriculum_intro', 'staff_intro', 'calendar_intro', 'admissions_interview_subjects', 'admissions_stationery_note']} | {name: forms.Textarea(attrs={'class': 'rich-editor'}) for name in ['about_history', 'curriculum_body']} | {
                       name: forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})
                       for name in ['admissions_deadline', 'admissions_interview_date']} | {
                       'admissions_interview_time': forms.TimeInput(format='%H:%M', attrs={'type': 'time'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound:
            # An older workspace form may not contain these new cycle settings.
            for name in ADMISSIONS_CYCLE_FIELDS:
                if name not in self.data:
                    self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        # Preserve newly introduced content when an older settings form is submitted.
        for name in self._meta.fields:
            if name in ADMISSIONS_CYCLE_FIELDS or name.startswith(('about_', 'curriculum_', 'staff_', 'calendar_')) or name in {
                'contact_image', 'contact_image_alt', 'admissions_image', 'admissions_image_alt'}:
                if name not in self.data and name not in self.files and name + '-clear' not in self.data:
                    cleaned[name] = getattr(self.instance, name)
        return cleaned

    def clean_google_maps_embed_url(self):
        return normalize_google_maps_embed(self.cleaned_data['google_maps_embed_url'])

    @property
    def fieldsets(self):
        groups = [
            ('School identity & footer', ['name', 'motto', 'logo', 'footer_text', 'facebook_url']),
            ('Homepage introduction', ['hero_eyebrow', 'hero_title', 'hero_text', 'hero_image', 'hero_image_alt', 'about_title', 'about_text']),
            ('About — history, mission & vision', ['about_heading', 'about_intro', 'about_image', 'about_image_alt', 'about_history', 'about_mission', 'about_vision']),
            ('Curriculum', ['curriculum_heading', 'curriculum_intro', 'curriculum_image', 'curriculum_image_alt', 'curriculum_body']),
            ('Staff directory', ['staff_heading', 'staff_intro', 'staff_image', 'staff_image_alt']),
            ('School calendar', ['calendar_heading', 'calendar_intro', 'calendar_image', 'calendar_image_alt']),
            ('Contact page & school office', ['contact_heading', 'contact_text', 'contact_image', 'contact_image_alt', 'address', 'office_hours', 'email', 'phone', 'google_maps_embed_url']),
            ('School statistics', ['statistics_title', 'statistics_text']),
            ('Admissions', ['admissions_open', 'admissions_heading', 'admissions_text', 'admissions_image', 'admissions_image_alt', 'admissions_requirements']),
            ('Admissions cycle & interview details', ADMISSIONS_CYCLE_FIELDS),
            ('Privacy & demonstration', ['privacy_text', 'demo_mode']),
        ]
        return [(title, [self[name] for name in names]) for title, names in groups]


class ApplicationReviewForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['status', 'staff_notes']
        widgets = {'staff_notes': forms.Textarea(attrs={'rows': 6})}
        help_texts = {'staff_notes': 'Private to authorised admissions staff. This is never shown on the public site.'}


class StaffUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(choices=[('Content editors', 'Content editor'), ('Admissions officers', 'School office — admissions and messages'),
                                      ('both', 'Content editor and admissions officer')])
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def clean_role(self):
        role = self.cleaned_data['role']
        required = ['Content editors', 'Admissions officers'] if role == 'both' else [role]
        if Group.objects.filter(name__in=required).count() != len(required):
            raise ValidationError('Staff roles are not configured. Run setup_staff_groups first.')
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if commit:
            user.save()
            names = ['Content editors', 'Admissions officers'] if self.cleaned_data['role'] == 'both' else [self.cleaned_data['role']]
            user.groups.set(Group.objects.filter(name__in=names))
        return user


class ContactReviewForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['status', 'staff_notes']
        widgets = {'staff_notes': forms.Textarea(attrs={'rows': 5})}
        help_texts = {'staff_notes': 'Internal notes are visible only to authorised staff.'}


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['title', 'description', 'order', 'published']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class StaffMemberForm(forms.ModelForm):
    class Meta:
        model = StaffMember
        fields = ['title', 'honorific', 'position', 'date_from', 'departments', 'biography', 'image', 'image_alt', 'order', 'published']
        widgets = {'biography': forms.Textarea(attrs={'rows': 8}), 'departments': forms.CheckboxSelectMultiple,
                   'date_from': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})}
        help_texts = {'image': 'Optional JPEG, PNG or WebP, up to 5 MB. The name’s initial is shown without a photo.',
                      'published': 'Show this profile on the staff directory. Members of hidden departments remain hidden unless they also belong to a published department.'}


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['title', 'slug', 'introduction', 'body', 'image', 'image_alt', 'order', 'published']
        widgets = {'body': forms.Textarea(attrs={'class': 'rich-editor'}), 'introduction': forms.Textarea(attrs={'rows': 3})}
        help_texts = {'body': 'Use the image upload button to embed images alongside formatted subject content.'}


class StatisticForm(forms.ModelForm):
    class Meta:
        model = SchoolStatistic
        fields = ['title', 'value', 'description', 'icon', 'order', 'published', 'show_on_homepage', 'show_on_school_pages']
        help_texts = {'show_on_school_pages': 'Shown on the fixed About page.'}

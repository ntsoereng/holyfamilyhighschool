from .roles import STAFF_ROLE_CHOICES, ensure_staff_groups
from django.db import transaction
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Article, Event, SchoolValue, SiteSettings, Application, ContactMessage, Department, StaffMember, Subject, SchoolStatistic, StudentAuthor, SchoolLifePost, ENTRY_LEVEL_CHOICES
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
        fields = ['title', 'category', 'excerpt', 'body', 'image', 'image_alt', 'published', 'published_at']
        widgets = {'body': forms.Textarea(attrs={'class': 'rich-editor'}), 'published_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})}
        help_texts = {'body': 'Use Insert/edit image to upload an image within the article. JPEG, PNG and WebP images up to 5 MB are supported. Add an image description for accessibility.',
                      'published': 'Uncheck to keep this story as a draft.',
                      'published_at': 'Local Lesotho time. A future date schedules publication.'}


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'image', 'image_alt', 'location', 'starts_at', 'ends_at', 'published']
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

    def __init__(self, *args, admissions_separate=False, **kwargs):
        super().__init__(*args, **kwargs)
        if admissions_separate:
            for name in list(self.fields):
                if name.startswith('admissions_'):
                    self.fields.pop(name)
        if self.is_bound:
            # An older workspace form may not contain these new cycle settings.
            for name in ADMISSIONS_CYCLE_FIELDS:
                if name in self.fields and name not in self.data:
                    self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        # Preserve newly introduced content when an older settings form is submitted.
        for name in self.fields:
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
        return [(title, [self[name] for name in names if name in self.fields])
                for title, names in groups if any(name in self.fields for name in names)]


class AdmissionsSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ['admissions_open', 'admissions_heading', 'admissions_text', 'admissions_image',
                  'admissions_image_alt', 'admissions_requirements'] + ADMISSIONS_CYCLE_FIELDS
        widgets = {name: widget for name, widget in SettingsForm.Meta.widgets.items() if name.startswith('admissions_')}
        help_texts = {'admissions_open': 'When closed, the public page shows only a closure notice and application submissions are disabled.'}

    @property
    def fieldsets(self):
        return [('Admissions status & page', [self[name] for name in self.Meta.fields if name not in ADMISSIONS_CYCLE_FIELDS]),
                ('Intake, payment & interviews', [self[name] for name in ADMISSIONS_CYCLE_FIELDS])]


class ApplicationReviewForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['status', 'staff_notes']
        widgets = {'staff_notes': forms.Textarea(attrs={'rows': 6})}
        help_texts = {'staff_notes': 'Private to authorised admissions staff. This is never shown on the public site.'}


class StaffUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(choices=STAFF_ROLE_CHOICES, help_text=(
        'Content editor manages public content and Site Settings. School office manages admissions settings and private applications and messages, '
        'including deletion. The combined role has both sets of access. None can manage staff accounts. '
        'See the role guide above for full details.'))
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if commit:
            with transaction.atomic():
                groups = ensure_staff_groups()
                user.save()
                names = ['Content editors', 'Admissions officers'] if self.cleaned_data['role'] == 'both' else [self.cleaned_data['role']]
                user.groups.set([groups[name] for name in names])
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
    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_management') and not cleaned.get('management_role'):
            self.add_error('management_role', 'Select a role for school management.')
        if not cleaned.get('is_management'):
            cleaned['management_role'] = ''
        return cleaned

    class Meta:
        model = StaffMember
        fields = ['title', 'honorific', 'position', 'date_from', 'is_management', 'management_role', 'departments', 'biography', 'image', 'image_alt', 'order', 'published']
        widgets = {'biography': forms.Textarea(attrs={'rows': 8}), 'departments': forms.CheckboxSelectMultiple,
                   'date_from': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})}
        help_texts = {'image': 'Optional JPEG, PNG or WebP, up to 5 MB. The name’s initial is shown without a photo.',
                      'published': 'Show this profile on the staff directory. Members of hidden departments remain hidden unless they are in school management or also belong to a published department.'}


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['title', 'introduction', 'body', 'image', 'image_alt', 'order', 'published']
        widgets = {'body': forms.Textarea(attrs={'class': 'rich-editor'}), 'introduction': forms.Textarea(attrs={'rows': 3})}
        help_texts = {'body': 'Use the image upload button to embed images alongside formatted subject content.'}


class StatisticForm(forms.ModelForm):
    class Meta:
        model = SchoolStatistic
        fields = ['title', 'value', 'description', 'icon', 'order', 'published', 'show_on_homepage', 'show_on_school_pages']
        help_texts = {'show_on_school_pages': 'Shown on the fixed About page.'}


class StudentAuthorForm(forms.ModelForm):
    class Meta:
        model = StudentAuthor
        fields = ['title', 'grade']

    def clean_title(self):
        from .submissions import normalize_name
        name = normalize_name(self.cleaned_data['title'])
        if not name or len(name) > 160:
            raise forms.ValidationError('Enter a student name of up to 160 characters.')
        return name


class SchoolLifePostForm(forms.ModelForm):
    new_author_name = forms.CharField(label='New student author’s name', max_length=160, required=False)
    new_author_grade = forms.ChoiceField(label='New student author’s grade', required=False,
                                         choices=[('', 'Select a grade'), *ENTRY_LEVEL_CHOICES])

    class Meta:
        model = SchoolLifePost
        fields = ['title', 'category', 'excerpt', 'body', 'image', 'image_alt', 'published_at', 'published',
                  'author', 'new_author_name', 'new_author_grade']
        widgets = {'body': forms.Textarea(attrs={'class': 'rich-editor'}),
                   'excerpt': forms.Textarea(attrs={'rows': 3}),
                   'published_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})}
        help_texts = {'body': 'Use Insert/edit image to upload images between paragraphs. You can also paste or drag images into the editor. Add an image description for accessibility.',
                      'published': 'Publish at the selected date and time. Future posts stay hidden until then.'}

    def __init__(self, *args, can_add_author=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['author'].required = False
        self.can_add_author = can_add_author
        if not can_add_author:
            for name in ['new_author_name', 'new_author_grade']:
                self.fields[name].disabled = True
        self.fields['author'].label = 'Existing student author'
        self.fields['author'].help_text = 'Reuse a saved author, or leave this blank and enter a new author below. Only the student’s name and grade are published.'

    def clean(self):
        from .submissions import normalize_name
        cleaned = super().clean()
        name = normalize_name(cleaned.get('new_author_name', ''))
        cleaned['new_author_name'] = name
        if len(name) > 160:
            self.add_error('new_author_name', 'Enter a student name of up to 160 characters.')
        grade, author = cleaned.get('new_author_grade'), cleaned.get('author')
        if author and (name or grade):
            self.add_error('author', 'Choose an existing author or enter a new author, rather than both.')
        elif not author:
            if not self.can_add_author:
                self.add_error('author', 'Select an existing student author.')
            elif not name or not grade:
                self.add_error('author', 'Select an existing author, or enter both a new author’s name and grade.')
        return cleaned

    def save(self, commit=True):
        from .models import StudentAuthor
        post = super().save(commit=False)
        if not self.cleaned_data.get('author'):
            author, _ = StudentAuthor.objects.get_or_create(title=self.cleaned_data['new_author_name'],
                                                           grade=self.cleaned_data['new_author_grade'])
            post.author = author
        if commit:
            post.save()
            self.save_m2m()
        return post


    @property
    def fieldsets(self):
        return [('Writing & publication', [self[name] for name in ['title', 'category', 'excerpt', 'body', 'image', 'image_alt', 'published_at', 'published']]),
                ('Student author', [self[name] for name in ['author', 'new_author_name', 'new_author_grade']])]

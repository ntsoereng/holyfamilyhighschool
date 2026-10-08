import uuid
from datetime import date, time
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from tinymce.models import HTMLField
from .security import clean_html, validate_image, validate_google_maps_embed

ENTRY_LEVEL_CHOICES = [(f'Grade {i}', f'Grade {i}') for i in range(8, 13)] + [
    (f'Form {i}', f'Form {i}') for i in range(1, 6)]
DISTRICT_CHOICES = [(name, name) for name in [
    'Berea', 'Botha-Bothe', 'Leribe', 'Mafeteng', 'Maseru', "Mohale's Hoek",
    'Mokhotlong', "Qacha's Nek", 'Quthing', 'Thaba-Tseka', 'Other']]


def image_path(instance, filename):
    from pathlib import Path
    return f'school/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'

class SiteSettings(models.Model):
    name = models.CharField(max_length=150, default='Holy Family High School')
    motto = models.CharField(max_length=150, default='Quid retribuam')
    logo = models.ImageField(upload_to=image_path, validators=[validate_image], blank=True)
    hero_eyebrow = models.CharField(max_length=120, default='Faith. Learning. Possibility.')
    hero_title = models.CharField(max_length=180, default='A strong foundation. A world of possibility.')
    hero_text = models.TextField(default='A place to grow in knowledge, faith and confidence. Discover your strengths, follow your curiosity and shape your future at Holy Family.')
    hero_image = models.ImageField(upload_to=image_path, validators=[validate_image], blank=True)
    hero_image_alt = models.CharField(max_length=200, blank=True)
    about_title = models.CharField(max_length=180, default='An education for the whole person.')
    about_text = models.TextField(default='At Holy Family, learning extends beyond the classroom. We believe in nurturing curious minds, building character, and helping every learner find a meaningful path forward.')
    about_heading = models.CharField(max_length=180, default='Rooted in faith. Growing in possibility.', blank=True)
    about_intro = models.TextField(default='Discover the story and purpose of Holy Family High School.', blank=True)
    curriculum_heading = models.CharField(max_length=180, default='Curiosity today. Possibility tomorrow.', blank=True)
    curriculum_intro = models.TextField(default='Explore the subjects that help you build knowledge, confidence and a sense of purpose.', blank=True)
    staff_heading = models.CharField(max_length=180, default='The people behind every possibility.', blank=True)
    staff_intro = models.TextField(default='Find your department and meet the teachers and school team who support you every day.', blank=True)
    calendar_heading = models.CharField(max_length=180, default='A community in motion.', blank=True)
    calendar_intro = models.TextField(default='School events and important dates, all in one place.', blank=True)
    about_image = models.ImageField('About header image', upload_to=image_path, validators=[validate_image], blank=True)
    about_image_alt = models.CharField('About header image description', max_length=200, blank=True)
    curriculum_image = models.ImageField('Curriculum header image', upload_to=image_path, validators=[validate_image], blank=True)
    curriculum_image_alt = models.CharField('Curriculum header image description', max_length=200, blank=True)
    staff_image = models.ImageField('Staff header image', upload_to=image_path, validators=[validate_image], blank=True)
    staff_image_alt = models.CharField('Staff header image description', max_length=200, blank=True)
    calendar_image = models.ImageField('Calendar header image', upload_to=image_path, validators=[validate_image], blank=True)
    calendar_image_alt = models.CharField('Calendar header image description', max_length=200, blank=True)
    contact_image = models.ImageField('Contact header image', upload_to=image_path, validators=[validate_image], blank=True)
    contact_image_alt = models.CharField('Contact header image description', max_length=200, blank=True)
    admissions_image = models.ImageField('Admissions header image', upload_to=image_path, validators=[validate_image], blank=True)
    admissions_image_alt = models.CharField('Admissions header image description', max_length=200, blank=True)
    about_history = HTMLField('School history', blank=True)
    about_mission = models.TextField('Mission statement', blank=True)
    about_vision = models.TextField('Vision statement', blank=True)
    curriculum_body = HTMLField('Curriculum overview', blank=True)
    address = models.TextField(blank=True)
    google_maps_embed_url = models.URLField('Google Maps embed URL', max_length=3000, blank=True, validators=[validate_google_maps_embed],
        help_text='In Google Maps choose Share → Embed a map. Paste only the URL inside src="...", not the whole iframe. Leave blank to hide the map.')
    footer_text = models.TextField(default='A Catholic school for girls, educating the whole person in the tradition of the Holy Family Sisters.')
    contact_heading = models.CharField(max_length=160, default='Get in touch')
    contact_text = models.TextField(default='Contact our school office about admissions, school life or arranging a visit.')
    facebook_url = models.URLField(blank=True)
    statistics_title = models.CharField(max_length=160, default='Holy Family in numbers')
    statistics_text = models.TextField(blank=True, help_text='Optional introduction or date/context for your statistics.')
    office_hours = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    admissions_open = models.BooleanField(default=True)
    admissions_heading = models.CharField(max_length=180, default='Your next chapter starts here.')
    admissions_text = models.TextField(default='Take the next step in your learning journey. Complete your application with a parent or guardian, and our admissions team will guide you through what comes next.')
    admissions_requirements = models.TextField(default='Complete your application with a parent or guardian. Contact the admissions office if you need help with entry requirements, supporting documents or payment.')
    admissions_grade = models.CharField('Admission grade', max_length=30, choices=ENTRY_LEVEL_CHOICES, default='Grade 8')
    admissions_year = models.PositiveSmallIntegerField('Admission year', default=2027,
        validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    admissions_fee = models.DecimalField('Application fee (M)', max_digits=8, decimal_places=2,
        default=Decimal('50.00'), validators=[MinValueValidator(Decimal('0.00'))],
        help_text='The application fee is non-refundable.')
    admissions_payment_method = models.CharField('Payment method', max_length=80, default='M-pesa')
    admissions_merchant_number = models.CharField('School merchant number', max_length=30, default='5184')
    admissions_deadline = models.DateField('Application deadline', default=date(2026, 10, 14), null=True, blank=True)
    admissions_interview_date = models.DateField('Interview date', default=date(2026, 10, 17), null=True, blank=True)
    admissions_interview_time = models.TimeField('Interview time', default=time(8, 0), null=True, blank=True,
        help_text='Local school time in Lesotho.')
    admissions_interview_location = models.CharField('Interview venue', max_length=180, default='Holy Family High School', blank=True)
    admissions_interview_subjects = models.TextField('Interview subjects',
        default='English language, Sesotho, Science and Maths', blank=True)
    admissions_stationery_note = models.TextField('Stationery instructions',
        default='Stationery will be provided. Bring a pen, pencil and mathematical instruments.', blank=True)
    privacy_text = models.TextField(default='We use application details only to respond to your enquiry and assess admission. Authorised school staff can access your submission. Contact the school office to request a correction or deletion. Do not submit sensitive records through this form.')
    demo_mode = models.BooleanField(default=True, help_text='Show the pitch notice. Use fictional applicant details until the school approves launch.')
    class Meta:
        verbose_name = 'School settings'
        verbose_name_plural = 'School settings'
    def save(self, *args, **kwargs):
        self.pk = 1
        self.about_history = clean_html(self.about_history)
        self.curriculum_body = clean_html(self.curriculum_body)
        super().save(*args, **kwargs)
    @property
    def safe_maps_embed_url(self):
        try:
            validate_google_maps_embed(self.google_maps_embed_url)
        except ValidationError:
            return ''
        return self.google_maps_embed_url

    def __str__(self): return self.name

class PublishedQuerySet(models.QuerySet):
    def live(self): return self.filter(published=True, published_at__lte=timezone.now())

class Article(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=80, default='School life')
    excerpt = models.TextField(max_length=400)
    body = HTMLField()
    image = models.ImageField(upload_to=image_path, validators=[validate_image], blank=True)
    image_alt = models.CharField(max_length=200, blank=True)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(default=timezone.now)
    objects = PublishedQuerySet.as_manager()
    class Meta: ordering = ['-published_at']
    def save(self, *args, **kwargs):
        self.body = clean_html(self.body)
        super().save(*args, **kwargs)
    def __str__(self): return self.title

class Event(models.Model):
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    description = HTMLField()
    image = models.ImageField('Featured image', upload_to=image_path, validators=[validate_image], blank=True, help_text='Optional JPEG, PNG or WebP image, up to 5 MB.')
    image_alt = models.CharField('Featured image description', max_length=200, blank=True, help_text='Describe the photograph for visitors using a screen reader.')
    location = models.CharField(max_length=180)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(blank=True, null=True)
    published = models.BooleanField(default=False)
    class Meta: ordering = ['starts_at']
    def clean(self):
        if self.ends_at and self.starts_at and self.ends_at < self.starts_at:
            raise ValidationError({'ends_at': 'The end must be after the start.'})
    def save(self, *args, **kwargs):
        self.description = clean_html(self.description)
        super().save(*args, **kwargs)
    def __str__(self): return self.title

class Page(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    introduction = models.TextField()
    body = HTMLField(blank=True)
    image = models.ImageField('Featured image', upload_to=image_path, validators=[validate_image], blank=True, help_text='Optional JPEG, PNG or WebP image, up to 5 MB.')
    image_alt = models.CharField('Featured image description', max_length=200, blank=True, help_text='Describe the photograph for visitors using a screen reader.')
    mission = models.TextField(blank=True, help_text='Optional mission statement. Shown as a separate section on this page.')
    vision = models.TextField(blank=True, help_text='Optional vision statement. Shown as a separate section on this page.')
    layout = models.CharField(max_length=20, default='standard', choices=[('standard', 'Standard page'), ('staff', 'Staff directory'), ('curriculum', 'Subject directory')], help_text='Directory layouts display the published records managed in the staff workspace.')
    show_statistics = models.BooleanField(default=False, help_text='Display published statistics enabled for school pages.')
    show_school_values = models.BooleanField(default=False, help_text='Display the shared school values on this page. Edit their text and order in School values.')
    show_in_navigation = models.BooleanField(default=True)
    published = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ['order','title']
    def save(self, *args, **kwargs):
        self.body = clean_html(self.body)
        super().save(*args, **kwargs)
    def __str__(self): return self.title

class SchoolValue(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=400)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ['order']
    def __str__(self): return self.title

class Application(models.Model):
    reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    learner_name = models.CharField(max_length=200)
    surname = models.CharField('Surname', max_length=80, blank=True)
    given_name = models.CharField('Name', max_length=80, blank=True)
    date_of_birth = models.DateField()
    entry_level = models.CharField(max_length=30, choices=ENTRY_LEVEL_CHOICES)
    application_year = models.PositiveSmallIntegerField('Admission year', null=True, blank=True)
    physical_address = models.TextField('Physical address', max_length=1000, blank=True)
    district = models.CharField('District', max_length=40, choices=DISTRICT_CHOICES, blank=True)
    district_other = models.CharField('Other district', max_length=120, blank=True)
    boarding_required = models.BooleanField('Applying for boarding', null=True, blank=True)
    current_school = models.CharField(max_length=180, blank=True)
    guardian_name = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40)
    message = models.TextField(max_length=2000, blank=True)
    consent = models.BooleanField()
    status = models.CharField(max_length=20, default='new', choices=[('new','New'),('reviewing','Reviewing'),('contacted','Contacted'),('accepted','Accepted'),('closed','Closed')])
    staff_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-submitted_at']
    @property
    def district_display(self):
        return self.district_other if self.district == 'Other' and self.district_other else self.district
    def __str__(self): return f'{self.learner_name} — {self.entry_level}'

class SubmissionAttempt(models.Model):
    ip_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class ContactMessage(models.Model):
    name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    subject = models.CharField(max_length=180)
    message = models.TextField(max_length=5000)
    consent = models.BooleanField()
    status = models.CharField(max_length=20, default='new', choices=[('new', 'New'), ('reviewing', 'In progress'), ('closed', 'Closed')])
    staff_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return self.subject


class Department(models.Model):
    title = models.CharField('Department name', max_length=120, unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    published = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title


class StaffMember(models.Model):
    title = models.CharField('Full names', max_length=160)
    honorific = models.CharField('Title / honorific', max_length=40, blank=True,
        help_text='Optional, for example Mrs, Mr or Sr. Leave blank if already included in the full names.')
    position = models.CharField('Role / position', max_length=160, blank=True)
    date_from = models.DateField('At Holy Family from', null=True, blank=True,
        help_text='Optional. Add the start date only if it is known.')
    departments = models.ManyToManyField(Department, related_name='members', blank=True,
        help_text='Select one or more departments. Leave blank to show under School team.')
    biography = models.TextField('Biography', blank=True)
    image = models.ImageField('Profile photo', upload_to=image_path, validators=[validate_image], blank=True)
    image_alt = models.CharField('Photo description', max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    published = models.BooleanField(default=False)

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Staff profile'

    def __str__(self):
        return self.title

    @property
    def display_name(self):
        return f'{self.honorific} {self.title}' if self.honorific else self.title


class Subject(models.Model):
    title = models.CharField('Subject name', max_length=160)
    slug = models.SlugField(unique=True, max_length=180)
    introduction = models.TextField('Short introduction', blank=True)
    body = HTMLField('Subject content', blank=True)
    image = models.ImageField('Featured image', upload_to=image_path, validators=[validate_image], blank=True)
    image_alt = models.CharField('Image description', max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    published = models.BooleanField(default=False)

    class Meta:
        ordering = ['order', 'title']

    def save(self, *args, **kwargs):
        self.body = clean_html(self.body)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class SchoolStatistic(models.Model):
    title = models.CharField('Label', max_length=100)
    value = models.CharField('Display value', max_length=40, help_text='For example: 1,066, 43, 98% or 60+.')
    description = models.CharField('Supporting text', max_length=200, blank=True)
    icon = models.CharField(max_length=20, default='people', choices=[('people','People'), ('book','Learning'), ('shield','Achievement'), ('calendar','Years / dates')])
    order = models.PositiveSmallIntegerField(default=0)
    published = models.BooleanField(default=False)
    show_on_homepage = models.BooleanField(default=True)
    show_on_school_pages = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'School statistic'

    def __str__(self):
        return f'{self.title}: {self.value}'

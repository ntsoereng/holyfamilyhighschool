from html.parser import HTMLParser
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.test import TestCase, override_settings

from .forms import ApplicationForm
from .models import Application, Page, SiteSettings


COPY_MIGRATION = import_module('school.migrations.0011_learner_facing_copy')
STARTER_REPLACEMENTS = [
    ('hero_text',
     'A welcoming school community where young people are encouraged to learn with purpose, grow in faith, and serve with compassion.',
     'A place to grow in knowledge, faith and confidence. Discover your strengths, follow your curiosity and shape your future at Holy Family.'),
    ('hero_text',
     'Educating girls physically, morally and intellectually, and empowering them to occupy all spheres of life.',
     'Grow in knowledge, faith and confidence. At Holy Family, you can discover your strengths and prepare to contribute to every sphere of life.'),
    ('curriculum_intro',
     'Explore the subjects that help our learners build knowledge, confidence and a sense of purpose.',
     'Explore the subjects that help you build knowledge, confidence and a sense of purpose.'),
    ('staff_intro',
     'Meet the teachers and school team who support our learners every day.',
     'Find your department and meet the teachers and school team who support you every day.'),
    ('staff_intro',
     'Meet the people who lead, teach and support our school community.',
     'Meet the people who teach, guide and support you at Holy Family.'),
    ('admissions_text',
     'Tell us about your learner. Our admissions team will review your application and contact you about the next steps.',
     'Take the next step in your learning journey. Complete your application with a parent or guardian, and our admissions team will guide you through what comes next.'),
    ('admissions_requirements',
     'Complete the online enquiry with a parent or guardian. The admissions office will confirm entry requirements, supporting documents, fees, and available places.',
     'Complete your application with a parent or guardian. Contact the admissions office if you need help with entry requirements, supporting documents or payment.'),
]


class ConsentInputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.consent = None

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'input' and attributes.get('name') == 'consent':
            self.consent = attributes


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class LearnerFacingCopyTests(TestCase):
    def setUp(self):
        self.school = SiteSettings.objects.create(
            about_mission='Our approved mission statement.',
            about_vision='Our approved vision statement.',
            about_history='<p>Our recorded school history.</p>',
        )

    def refresh_copy(self):
        editor = SimpleNamespace(connection=SimpleNamespace(alias='default'))
        COPY_MIGRATION.refresh_default_copy(apps, editor)
        self.school.refresh_from_db()

    def test_known_starter_variants_are_updated_without_touching_school_history_or_purpose(self):
        for field, previous, replacement in STARTER_REPLACEMENTS:
            with self.subTest(field=field, previous=previous):
                SiteSettings.objects.filter(pk=self.school.pk).update(**{field: previous})
                self.refresh_copy()
                self.assertEqual(getattr(self.school, field), replacement)
                self.assertEqual(self.school.about_mission, 'Our approved mission statement.')
                self.assertEqual(self.school.about_vision, 'Our approved vision statement.')
                self.assertEqual(self.school.about_history, '<p>Our recorded school history.</p>')

    def test_custom_blank_and_near_matching_copy_is_preserved(self):
        for field, replacements in COPY_MIGRATION.COPY_UPDATES.items():
            previous = next(iter(replacements))
            for custom in ['A school-approved message written by our staff.', '', previous + ' ']:
                with self.subTest(field=field, custom=custom):
                    SiteSettings.objects.filter(pk=self.school.pk).update(**{field: custom})
                    self.refresh_copy()
                    self.assertEqual(getattr(self.school, field), custom)

    def test_unrelated_settings_and_featured_images_are_preserved(self):
        unchanged = {
            'name': 'Holy Family Community School',
            'hero_title': 'A title approved by the school',
            'hero_eyebrow': 'Our own introduction',
            'hero_image': 'school/approved-hero.png',
            'hero_image_alt': 'Our learners at school',
            'about_heading': 'Our own history heading',
            'about_text': 'Our own school description',
            'contact_text': 'Our office contact instructions',
            'admissions_heading': 'Join us next year',
            'calendar_intro': 'Dates approved by the school office',
        }
        SiteSettings.objects.filter(pk=self.school.pk).update(**unchanged)
        self.refresh_copy()
        for field, expected in unchanged.items():
            with self.subTest(field=field):
                self.assertEqual(str(getattr(self.school, field)), expected)

    def test_only_recognised_archived_staff_page_introductions_are_updated(self):
        previous = 'Meet the people who lead, teach and support our school community.'
        replacement = 'Meet the people who teach, guide and support you at Holy Family.'
        staff = [Page.objects.create(title='Staff', slug=slug, introduction=previous,
                                    body='<p>Approved staff details.</p>', mission='Keep this mission')
                 for slug in ['staff', 'our-staff']]
        other = Page.objects.create(title='About', slug='about', introduction=previous)
        self.refresh_copy()
        for page in staff:
            page.refresh_from_db()
            self.assertEqual(page.introduction, replacement)
            self.assertEqual(page.body, '<p>Approved staff details.</p>')
            self.assertEqual(page.mission, 'Keep this mission')
        other.refresh_from_db()
        self.assertEqual(other.introduction, previous)

    def test_custom_staff_page_intro_and_repeated_migration_are_preserved(self):
        custom = Page.objects.create(title='Staff', slug='staff', introduction='Our own introduction to the team.')
        self.refresh_copy()
        after_first_run = {field: getattr(self.school, field) for field in COPY_MIGRATION.COPY_UPDATES}
        self.refresh_copy()
        custom.refresh_from_db()
        self.assertEqual(custom.introduction, 'Our own introduction to the team.')
        self.assertEqual({field: getattr(self.school, field) for field in after_first_run}, after_first_run)

    def test_new_settings_defaults_use_the_learner_facing_copy(self):
        fresh = SiteSettings()
        expected_defaults = {}
        for field, previous, replacement in STARTER_REPLACEMENTS:
            expected_defaults.setdefault(field, replacement)
        for field, expected in expected_defaults.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(fresh, field), expected)

    def test_home_has_learner_invitation_without_old_hero_pills_overlay_or_shared_banner(self):
        self.school.hero_image = 'school/hero.png'
        self.school.hero_image_alt = 'Learners in the school grounds'
        self.school.save()
        response = self.client.get('/')
        for text in ['Your curiosity. Your character. Your next chapter.', 'Get to know Holy Family',
                     'What would you like to explore?', 'Start your application', 'Learners in the school grounds']:
            self.assertContains(response, text)
        for obsolete in ['hero-tagline', 'hero-points', 'hero-caption', 'class="admissions-band"']:
            self.assertNotContains(response, obsolete)
        self.assertContains(response, self.school.hero_image.url)
        self.assertEqual(response.content.count(b'<h1'), 1)

    def test_admissions_addresses_the_learner_and_still_requires_guardian_consent(self):
        response = self.client.get('/apply/')
        for text in ['Your details', 'Your home address', 'Your parent or guardian', 'Your surname',
                     'Your name', 'Your primary school', 'My parent or guardian agrees']:
            self.assertContains(response, text)
        self.assertNotContains(response, 'class="admissions-band"')
        self.assertNotContains(response, 'Tell us about your learner.')
        parser = ConsentInputParser()
        parser.feed(response.content.decode())
        self.assertIsNotNone(parser.consent)
        self.assertEqual(parser.consent['type'], 'checkbox')
        self.assertIn('required', parser.consent)
        self.assertTrue(ApplicationForm(school=self.school).fields['consent'].required)

    def test_submission_without_guardian_consent_is_rejected_after_copy_changes(self):
        response = self.client.post('/apply/', {
            'surname': 'Mokoena', 'given_name': 'Lerato', 'date_of_birth': '2013-03-05',
            'physical_address': '', 'district': 'Maseru', 'district_other': '',
            'current_school': 'Example Primary School', 'guardian_name': 'Mpho Mokoena',
            'phone': '58881234', 'boarding_required': 'no', 'website': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('consent', response.context['form'].errors)
        self.assertContains(response, 'Your application has not been submitted.')
        self.assertFalse(Application.objects.exists())

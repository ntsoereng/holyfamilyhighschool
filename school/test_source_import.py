from django.core.management import call_command
from django.test import TestCase, override_settings
from .models import Page, SiteSettings, Article, Event

@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class SourceImportTests(TestCase):
    def test_content_structure_and_repeat_import_preserves_edits(self):
        call_command('seed_demo', verbosity=0)
        call_command('import_google_sites', verbosity=0)
        self.assertEqual(SiteSettings.objects.get().email, 'holyfamilyhighschool56@gmail.com')
        self.assertFalse(Article.objects.filter(published=True).exists())
        self.assertFalse(Event.objects.filter(published=True).exists())
        for slug in ['about','our-staff','curriculum']:
            self.assertEqual(self.client.get(f'/school/{slug}/').status_code, 200)
        self.assertContains(self.client.get('/'), 'Curriculum')
        self.assertNotContains(self.client.get('/events/'), 'Calendar 2025')
        self.assertNotContains(self.client.get('/school/about/'), 'Original school website')
        site = SiteSettings.objects.get()
        site.curriculum_body = '<p>Updated curriculum content.</p>'
        site.save()
        page=Page.objects.get(slug='curriculum')
        page.body='<p>Updated by staff.</p>'
        page.save()
        call_command('import_google_sites', verbosity=0)
        page.refresh_from_db()
        self.assertEqual(page.body, '<p>Updated by staff.</p>')
        self.assertContains(self.client.get('/curriculum/'), 'Updated curriculum content.')
        for slug in ['st-monicas', 'school-life', 'action-research']:
            self.assertEqual(self.client.get(f'/school/{slug}/').status_code, 404)

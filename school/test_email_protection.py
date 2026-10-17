import json
import re

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Announcement, Article, Project, SiteSettings
from .templatetags.email_protection import protect_email_html


@override_settings(SECURE_SSL_REDIRECT=False, SITE_URL='https://school.example.test', STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class EmailProtectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = SiteSettings.objects.create(email='office@example.com', admissions_open=True,
            footer_text='Contact office@example.com about the school.')

    def test_public_contact_addresses_are_obfuscated_in_all_locations(self):
        for path in ['/', '/contact/', '/apply/', '/donation/', '/privacy/', '/terms/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'office [at] example.com')
                self.assertNotContains(response, 'office@example.com')
                self.assertNotContains(response, 'href="mailto:')
                self.assertContains(response, 'data-email-address="office [at] example.com"')
        self.assertContains(self.client.get('/donation/'), 'data-email-subject="Donation enquiry"')
        response = self.client.get('/')
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>',response.content.decode(),re.S)[1])
        self.assertNotIn('email', data)

    def test_embedded_emails_are_protected_without_changing_stored_content(self):
        for model, route in [(Article,'article'),(Announcement,'announcement'),(Project,'project')]:
            item = model.objects.create(title=f'Contact {route}', excerpt='Ask writer@example.org', published=True,
                body='<p>Email <a href="mailto:writer@example.org?subject=School%20enquiry">writer@example.org</a>.</p>')
            response = self.client.get(reverse(route, args=[item.slug]))
            self.assertContains(response, 'writer [at] example.org')
            self.assertNotContains(response, 'writer@example.org')
            self.assertNotContains(response, 'href="mailto:')
            self.assertContains(response, 'data-email-subject="School enquiry"')
            item.refresh_from_db()
            self.assertIn('mailto:writer@example.org', item.body)

    def test_escaped_markup_and_only_email_subject_are_preserved(self):
        html = protect_email_html('<p>&lt;script&gt; &amp; <strong>Safe</strong></p>'
            '<a href="mailto:office@example.com?subject=%22test%22&amp;bcc=bad@example.org">Email office@example.com</a>')
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('<strong>Safe</strong>', html)
        self.assertIn('data-email-subject="&quot;test&quot;"', html)
        self.assertNotIn('bcc=', html)
        self.assertNotIn('office@example.com', html)
        self.assertNotIn('bad@example.org', html)

    def test_private_form_addresses_and_database_settings_are_not_obfuscated(self):
        self.school.refresh_from_db()
        self.assertEqual(self.school.email, 'office@example.com')
        response = self.client.post('/contact/', {'name':'A Visitor','email':'visitor@example.org',
            'subject':'Enquiry','message':'','consent':'on'})
        self.assertContains(response, 'value="visitor@example.org"')

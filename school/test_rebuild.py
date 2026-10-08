from io import BytesIO
from django.contrib.auth.models import User, Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from PIL import Image
from .models import Article, ContactMessage, SiteSettings
from .security import clean_html


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class RebuildTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_staff_groups', verbosity=0)
        cls.editor = User.objects.create_user('editor', is_staff=True)
        cls.editor.groups.add(Group.objects.get(name='Content editors'))
        cls.officer = User.objects.create_user('office', is_staff=True)
        cls.officer.groups.add(Group.objects.get(name='Admissions officers'))
        SiteSettings.objects.create()

    def image(self):
        data = BytesIO()
        Image.new('RGB', (40, 30), '#174b3b').save(data, 'PNG')
        return SimpleUploadedFile('classroom.png', data.getvalue(), content_type='image/png')

    def payload(self):
        return {'name': 'Parent Example', 'email': 'parent@example.com', 'subject': 'A school visit',
                'message': 'May we arrange a visit?', 'consent': 'on'}

    def test_contact_message_saved_and_success_does_not_repeat_post(self):
        response = self.client.post('/contact/', self.payload())
        self.assertRedirects(response, '/contact/', fetch_redirect_response=False)
        self.assertEqual(ContactMessage.objects.count(), 1)
        response = self.client.get('/contact/')
        self.assertContains(response, 'Your message has been received')
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.client.get('/contact/')
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_contact_validation_and_csrf(self):
        for changes in [{'consent': ''}, {'website': 'bot'}, {'email': 'invalid'}, {'message': 'x' * 5001}]:
            self.assertEqual(self.client.post('/contact/', self.payload() | changes).status_code, 200)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertEqual(Client(enforce_csrf_checks=True).post('/contact/', self.payload()).status_code, 403)

    def test_contact_throttle(self):
        for _ in range(5):
            self.client.post('/contact/', {})
        self.assertEqual(self.client.post('/contact/', self.payload()).status_code, 429)
        self.assertFalse(ContactMessage.objects.exists())

    def test_inbox_permissions_review_search_and_delete(self):
        record = ContactMessage.objects.create(**{**self.payload(), 'consent': True})
        path = f'/staff/messages/{record.pk}/'
        self.assertEqual(self.client.get(path).status_code, 302)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get('/staff/messages/').status_code, 403)
        self.assertEqual(self.client.get(path).status_code, 403)
        self.client.force_login(self.officer)
        self.assertContains(self.client.get('/staff/messages/?q=school'), record.subject)
        self.assertNotContains(self.client.get('/staff/messages/?state=closed'), record.subject)
        self.assertRedirects(self.client.post(path, {'status': 'reviewing', 'staff_notes': 'Call parent.'}), path)
        record.refresh_from_db()
        self.assertEqual(record.status, 'reviewing')
        self.assertNotContains(self.client.get('/contact/'), 'Call parent.')
        self.assertEqual(self.client.get(path+'delete/').status_code, 200)
        self.assertTrue(ContactMessage.objects.exists())
        self.assertRedirects(self.client.post(path+'delete/'), '/staff/messages/')
        self.assertFalse(ContactMessage.objects.exists())

    def test_view_only_message_staff_cannot_mutate(self):
        record = ContactMessage.objects.create(**{**self.payload(), 'consent': True})
        viewer = User.objects.create_user('reader', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_contactmessage'))
        self.client.force_login(viewer)
        path = f'/staff/messages/{record.pk}/'
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.post(path, {'status': 'closed'}).status_code, 403)
        self.assertEqual(self.client.post(path+'delete/').status_code, 403)

    def test_upload_permission_csrf_and_validation(self):
        url = '/staff/images/upload/'
        self.assertEqual(self.client.post(url, {'file': self.image()}).status_code, 302)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.post(url, {'file': self.image()}).status_code, 403)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {}).status_code, 400)
        self.assertEqual(self.client.post(url, {'file': SimpleUploadedFile('bad.png', b'not an image')}).status_code, 400)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.editor)
        self.assertEqual(csrf_client.post(url, {'file': self.image()}).status_code, 403)

    def test_uploaded_image_survives_rich_text_save(self):
        self.client.force_login(self.editor)
        response = self.client.post('/staff/images/upload/', {'file': self.image()})
        self.assertEqual(response.status_code, 200)
        location = response.json()['location']
        self.assertRegex(location, r'^/media/editor/[a-f0-9]{32}\.jpg$')
        article = Article.objects.create(title='Learning together', slug='learning', excerpt='School story', published=True,
            body=f'<h2>In class</h2><figure><img src="{location}" alt="Our classroom"><figcaption>Learning together</figcaption></figure><table><tbody><tr><td>English</td></tr></tbody></table>')
        self.assertIn(location, article.body)
        response = self.client.get('/news/learning/')
        self.assertContains(response, location)
        self.assertContains(response, '<figcaption>Learning together</figcaption>')
        self.assertContains(response, '<td>English</td>')
        self.assertContains(self.client.get(f'/staff/content/articles/{article.pk}/'), 'js/editor.js')
        self.assertContains(self.client.get('/staff/content/events/new/'), 'rich-editor')

    def test_sanitizer_rejects_unsafe_and_external_images(self):
        html = clean_html('<img src="javascript:alert(1)" onerror="alert(1)"><img src="https://tracker.example/image.png"><img src="/media/editor/../../secret.png"><iframe src="https://example.com"></iframe><p style="color:red">Safe</p>')
        for unsafe in ['javascript:', 'onerror', 'tracker.example', '../', '<iframe', 'style=']:
            self.assertNotIn(unsafe, html)
        self.assertIn('<p>Safe</p>', html)

    def test_brand_and_shared_headers(self):
        response = self.client.get('/')
        self.assertContains(response, 'images/holy-family-original.png')
        self.assertContains(response, 'css/fonts.css')
        self.assertNotContains(response, '↗')
        for path in ['/news/', '/events/', '/contact/', '/apply/', '/privacy/']:
            self.assertContains(self.client.get(path), 'class="page-banner"')

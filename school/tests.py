from datetime import timedelta
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.utils import timezone
from .models import SiteSettings, Article, Application, Event, Page

@override_settings(STORAGES={'default': {'BACKEND':'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}, SECURE_SSL_REDIRECT=False)
class SchoolTests(TestCase):
    def setUp(self):
        self.site = SiteSettings.objects.create()
        self.payload = {'given_name': 'Demo', 'surname': 'Learner', 'date_of_birth': '2012-03-05',
            'district': 'Maseru', 'current_school': 'Demo Primary', 'boarding_required': 'no',
            'guardian_name': 'Demo Guardian', 'phone': '555123456', 'consent': 'on'}

    def test_public_pages(self):
        for url in ['/', '/news/', '/events/', '/apply/', '/contact/', '/privacy/']:
            with self.subTest(url=url): self.assertEqual(self.client.get(url).status_code, 200)

    def test_application_saved_and_private_receipt(self):
        response = self.client.post('/apply/', self.payload)
        self.assertRedirects(response, '/apply/received/', fetch_redirect_response=False)
        self.assertEqual(Application.objects.count(), 1)
        receipt = self.client.get('/apply/received/')
        self.assertContains(receipt, str(Application.objects.get().reference))
        self.assertNotContains(receipt, 'Demo Learner')
        self.assertEqual(self.client.get('/apply/received/').status_code, 302)
        self.assertEqual(Client().get('/apply/received/').status_code, 302)

    def test_consent_honeypot_and_future_birth_rejected(self):
        for changes in [{'consent':''}, {'website':'spam'}, {'date_of_birth':'2999-01-01'}]:
            self.client.post('/apply/', {**self.payload, **changes})
        self.assertEqual(Application.objects.count(), 0)

    def test_closed_admissions_reject_post(self):
        self.site.admissions_open = False
        self.site.save()
        self.client.post('/apply/', self.payload)
        self.assertFalse(Application.objects.exists())

    def test_csrf(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post('/apply/', self.payload).status_code, 403)

    def test_rate_limit(self):
        for _ in range(5): self.client.post('/apply/', {})
        self.assertEqual(self.client.post('/apply/', self.payload).status_code, 429)
        self.assertFalse(Application.objects.exists())

    def test_unpublished_content_and_scheduled_articles_hidden(self):
        for published, date, slug in [(False,timezone.now(),'draft'), (True,timezone.now()+timedelta(days=1),'scheduled')]:
            Article.objects.create(title=slug,slug=slug,excerpt='Private story',body='<p>Private</p>',published=published,published_at=date)
            self.assertEqual(self.client.get(f'/news/{slug}/').status_code, 404)
        self.assertNotContains(self.client.get('/news/'), 'Private story')
        Page.objects.create(title='Private page',slug='private',introduction='Private',body='Private')
        self.assertEqual(self.client.get('/school/private/').status_code,404)

    def test_rich_text_is_sanitized(self):
        story = Article.objects.create(title='Safe',slug='safe',excerpt='Text',body='<script>alert(1)</script><p onclick="bad()">Hello <strong>world</strong><a href="javascript:alert(1)">link</a></p>')
        self.assertNotIn('<script', story.body)
        self.assertNotIn('onclick', story.body)
        self.assertNotIn('javascript:', story.body)
        self.assertIn('<strong>world</strong>', story.body)

    def test_security_headers(self):
        response = self.client.get('/')
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Cross-Origin-Opener-Policy'], 'same-origin')
        self.assertEqual(self.client.get('/apply/')['Cache-Control'], 'no-store, private')

    @override_settings(SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True,
                       CSRF_COOKIE_SECURE=True, SECURE_HSTS_SECONDS=3600)
    def test_https_redirect_hsts_and_secure_cookies(self):
        self.assertEqual(self.client.get('/apply/').status_code, 301)
        response = self.client.get('/apply/', secure=True)
        self.assertEqual(response['Strict-Transport-Security'], 'max-age=3600')
        self.assertTrue(response.cookies['csrftoken']['secure'])
        response = self.client.post('/apply/', self.payload, secure=True)
        self.assertTrue(response.cookies['sessionid']['secure'])

    @override_settings(ALLOWED_HOSTS=['school.test'], SECURE_SSL_REDIRECT=True)
    def test_forged_host_and_forwarded_proto_are_rejected(self):
        response = self.client.get('/', HTTP_HOST='attacker.test')
        self.assertEqual(response.status_code, 400)
        response = self.client.get('/', HTTP_HOST='school.test', HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response.status_code, 301)

    def test_admin_private_and_staff_groups(self):
        self.assertEqual(self.client.get('/admin/school/application/').status_code, 302)
        call_command('setup_staff_groups', verbosity=0)
        user = User.objects.create_user('editor',password='Strong-test-password-729',is_staff=True)
        user.groups.add(Group.objects.get(name='Content editors'))
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/school/application/').status_code,302)
        self.assertEqual(self.client.get('/staff/applications/').status_code,403)
        self.assertEqual(self.client.get('/admin/school/article/').status_code,302)
        self.assertEqual(self.client.get('/staff/content/articles/').status_code,200)

    def test_login_lockout(self):
        User.objects.create_user('staff',password='Strong-test-password-729',is_staff=True)
        for _ in range(5): self.client.post('/admin/login/', {'username':'staff','password':'wrong'})
        response = self.client.post('/admin/login/', {'username':'staff','password':'Strong-test-password-729'})
        self.assertEqual(response.status_code,429)

    def test_demo_seed_is_idempotent(self):
        call_command('seed_demo', verbosity=0)
        self.site.refresh_from_db()
        self.site.hero_title = 'Staff edited title'
        self.site.save()
        call_command('seed_demo', verbosity=0)
        self.site.refresh_from_db()
        self.assertEqual(self.site.hero_title, 'Staff edited title')
        self.assertEqual(Article.objects.count(),3)

    def test_staff_editor_is_self_hosted(self):
        user = User.objects.create_superuser('admin', 'admin@example.com', 'Strong-test-password-729')
        self.client.force_login(user)
        response = self.client.get('/admin/school/article/add/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'django_tinymce/init_tinymce.js')
        self.assertContains(response, 'data-mce-conf')
        self.assertContains(response, '/static/tinymce')

    def test_image_validation(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core.exceptions import ValidationError
        from .security import validate_image
        buffer = BytesIO()
        Image.new('RGB', (10, 10)).save(buffer, format='PNG')
        validate_image(SimpleUploadedFile('valid.png', buffer.getvalue()))
        for name, data in [('bad.png', b'<script>bad()</script>'), ('bad.html', buffer.getvalue())]:
            with self.assertRaises(ValidationError):
                validate_image(SimpleUploadedFile(name, data))

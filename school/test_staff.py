from datetime import timedelta
from io import BytesIO
from PIL import Image
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User, Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, Client, override_settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from .models import Article, Application, Event, SiteSettings


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class StaffWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_staff_groups', verbosity=0)
        cls.password = 'Staff-testing-password-940!'
        cls.editor = User.objects.create_user('editor', password=cls.password, is_staff=True)
        cls.editor.groups.add(Group.objects.get(name='Content editors'))
        cls.officer = User.objects.create_user('officer', password=cls.password, is_staff=True)
        cls.officer.groups.add(Group.objects.get(name='Admissions officers'))
        cls.owner = User.objects.create_superuser('owner', 'owner@example.com', cls.password)
        cls.ordinary = User.objects.create_user('ordinary', password=cls.password)
        cls.site = SiteSettings.objects.create()
        cls.article = Article.objects.create(title='Draft article', slug='draft', excerpt='An introduction', body='<p>Draft body</p>')
        cls.application = Application.objects.create(learner_name='Private Learner', date_of_birth='2012-01-01',
            entry_level='Form 1', guardian_name='Private Guardian', email='guardian@example.com', phone='55512345', consent=True)

    def article_data(self, **kwargs):
        return {'title': 'Updated article', 'slug': 'updated', 'category': 'Learning', 'excerpt': 'School story',
            'body': '<p>A <strong>formatted</strong> story.</p>', 'published_at': '2026-01-01T10:00', **kwargs}

    def test_anonymous_redirects_and_nonstaff_denied(self):
        paths = ['/staff/', '/staff/settings/', '/staff/content/articles/', '/staff/content/articles/new/',
                 f'/staff/content/articles/{self.article.pk}/', '/staff/applications/',
                 f'/staff/applications/{self.application.pk}/', '/staff/team/', '/staff/password/']
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/staff/login/', response.url)
        self.client.force_login(self.ordinary)
        for path in paths:
            with self.subTest(path=path): self.assertEqual(self.client.get(path).status_code, 403)

    def test_role_based_navigation_and_direct_access(self):
        self.client.force_login(self.editor)
        response = self.client.get('/staff/')
        self.assertContains(response, 'News &amp; articles')
        self.assertNotContains(response, 'Private Learner')
        self.assertNotContains(response, 'href="/staff/applications/"')
        for path in ['/staff/applications/', f'/staff/applications/{self.application.pk}/', '/staff/team/']:
            self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(self.client.post(path, {}).status_code, 403)
        self.client.force_login(self.officer)
        for path in ['/staff/settings/', '/staff/content/articles/new/', f'/staff/content/articles/{self.article.pk}/']:
            self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(self.client.post(path, self.article_data()).status_code, 403)
        self.assertContains(self.client.get('/staff/'), 'Private Learner')

    def test_staff_login_and_safe_next(self):
        response = self.client.post('/staff/login/?next=https://evil.example/', {'username':'editor', 'password':self.password})
        self.assertRedirects(response, '/staff/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/staff/').status_code, 200)

    def test_nonstaff_cannot_login(self):
        response = self.client.post('/staff/login/', {'username':'ordinary', 'password':self.password})
        self.assertContains(response, 'does not have staff access')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_staff_login_is_rate_limited(self):
        for _ in range(5):
            self.client.post('/staff/login/', {'username':'editor', 'password':'incorrect'})
        response = self.client.post('/staff/login/', {'username':'editor', 'password':self.password})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_is_post_only(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get('/staff/logout/').status_code,405)
        self.assertRedirects(self.client.post('/staff/logout/'), '/staff/login/')
        self.assertEqual(self.client.get('/staff/').status_code,302)

    def test_content_create_edit_delete_and_audit(self):
        self.client.force_login(self.editor)
        response = self.client.post('/staff/content/articles/new/', self.article_data())
        article = Article.objects.get(slug='updated')
        self.assertRedirects(response, f'/staff/content/articles/{article.pk}/')
        self.assertFalse(article.published)
        self.assertEqual(self.client.get('/news/updated/').status_code,404)
        response = self.client.post(f'/staff/content/articles/{article.pk}/', self.article_data(published='on', body='<script>bad()</script><p>Safe</p>'))
        article.refresh_from_db()
        self.assertNotIn('<script', article.body)
        self.assertContains(self.client.get('/news/updated/'), '<p>Safe</p>')
        self.assertTrue(LogEntry.objects.filter(user=self.editor, object_id=str(article.pk), action_flag=2).exists())
        path = f'/staff/content/articles/{article.pk}/delete/'
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertTrue(Article.objects.filter(pk=article.pk).exists())
        self.assertRedirects(self.client.post(path), '/staff/content/articles/')
        self.assertFalse(Article.objects.filter(pk=article.pk).exists())
        self.assertTrue(LogEntry.objects.filter(user=self.editor, action_flag=3).exists())

    def test_scheduled_article_hidden_and_duplicate_slug_reported(self):
        self.client.force_login(self.editor)
        response = self.client.post('/staff/content/articles/new/', self.article_data(published='on', published_at='2099-01-01T10:00'))
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.get('/news/updated/').status_code,404)
        self.assertContains(self.client.get('/staff/content/articles/'), 'Scheduled')
        response = self.client.post('/staff/content/articles/new/', self.article_data())
        self.assertEqual(response.status_code,200)
        self.assertContains(response, 'already exists')
        self.assertEqual(Article.objects.filter(slug='updated').count(),1)

    def test_events_and_values(self):
        self.client.force_login(self.editor)
        payloads = {
            'events': {'title':'Open day','slug':'open-day','description':'<p>Welcome</p>','location':'School hall','starts_at':'2099-01-01T09:00','ends_at':'2099-01-01T10:00','published':'on'},
            'values': {'title':'Service','description':'Serving our community','order':2},
        }
        for section, data in payloads.items():
            with self.subTest(section=section):
                self.assertEqual(self.client.post(f'/staff/content/{section}/new/', data).status_code,302)
                self.assertContains(self.client.get(f'/staff/content/{section}/'),data['title'])
        self.assertEqual(self.client.get('/school/our-school/').status_code,404)
        self.assertEqual(self.client.get('/events/open-day/').status_code,200)
        bad_event = {**payloads['events'], 'slug':'bad-event', 'ends_at':'2098-01-01T10:00'}
        self.assertContains(self.client.post('/staff/content/events/new/', bad_event),'end must be after')
        self.assertFalse(Event.objects.filter(slug='bad-event').exists())

    def test_settings_edit_and_upload(self):
        self.client.force_login(self.editor)
        from .staff_forms import SettingsForm
        data = {name: getattr(self.site, name) for name in SettingsForm._meta.fields if not isinstance(self.site._meta.get_field(name), models.ImageField)}
        data['hero_title'] = 'A staff-managed homepage'
        buffer = BytesIO()
        Image.new('RGB',(20,20)).save(buffer,format='PNG')
        data['logo'] = SimpleUploadedFile('crest.png',buffer.getvalue(),content_type='image/png')
        self.assertRedirects(self.client.post('/staff/settings/',data),'/staff/settings/')
        self.site.refresh_from_db()
        self.assertTrue(self.site.logo)
        self.assertContains(self.client.get('/'), 'A staff-managed homepage')
        data['logo'] = SimpleUploadedFile('bad.png',b'<script>bad</script>',content_type='image/png')
        self.assertEqual(self.client.post('/staff/settings/',data).status_code,200)
        self.assertEqual(SiteSettings.objects.count(),1)

    def test_application_review_cannot_change_applicant_data(self):
        self.client.force_login(self.officer)
        path = f'/staff/applications/{self.application.pk}/'
        self.assertContains(self.client.get(path),'Private Guardian')
        self.assertRedirects(self.client.post(path, {'status':'reviewing','staff_notes':'Follow up next week',
            'learner_name':'Tampered name','consent':False}),path)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status,'reviewing')
        self.assertEqual(self.application.learner_name,'Private Learner')
        self.assertTrue(self.application.consent)
        self.assertNotContains(self.client.get('/'),'Follow up next week')

    def test_view_only_officer_cannot_mutate(self):
        viewer = User.objects.create_user('viewer',is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_application'))
        self.client.force_login(viewer)
        path=f'/staff/applications/{self.application.pk}/'
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.client.post(path,{'status':'accepted'}).status_code,403)
        self.assertEqual(self.client.post(path+'delete/').status_code,403)

    def test_delete_application_requires_permission_and_confirmation(self):
        path=f'/staff/applications/{self.application.pk}/delete/'
        self.client.force_login(self.editor)
        self.assertEqual(self.client.post(path).status_code,403)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertTrue(Application.objects.filter(pk=self.application.pk).exists())
        self.assertRedirects(self.client.post(path),'/staff/applications/')
        self.assertFalse(Application.objects.filter(pk=self.application.pk).exists())

    def test_csrf_for_staff_mutations(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.editor)
        for path in ['/staff/content/articles/new/',f'/staff/content/articles/{self.article.pk}/delete/', '/staff/settings/', '/staff/logout/']:
            with self.subTest(path=path): self.assertEqual(client.post(path,{}).status_code,403)

    def test_owner_manages_accounts_without_privilege_escalation(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/staff/team/').status_code,200)
        self.assertRedirects(self.client.post('/staff/team/',{'username':'newstaff','email':'new@example.com',
            'password1':self.password,'password2':self.password,'role':'Content editors','is_superuser':'on'}),'/staff/team/')
        user=User.objects.get(username='newstaff')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.has_perm('school.change_article'))
        self.assertFalse(user.has_perm('school.view_application'))
        self.client.post(f'/staff/team/{user.pk}/toggle/')
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(self.client.post(f'/staff/team/{self.owner.pk}/toggle/').status_code,403)

    def test_disabled_account_cannot_reuse_session(self):
        self.client.force_login(self.editor)
        self.editor.is_active=False
        self.editor.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/staff/').status_code,302)

    def test_password_change_keeps_session(self):
        self.client.force_login(self.editor)
        response=self.client.post('/staff/password/', {'old_password':self.password,
            'new_password1':'A-different-secure-password-392!', 'new_password2':'A-different-secure-password-392!'})
        self.assertRedirects(response,'/staff/')
        self.editor.refresh_from_db()
        self.assertTrue(self.editor.check_password('A-different-secure-password-392!'))

    def test_private_headers_and_self_hosted_editor(self):
        self.client.force_login(self.editor)
        response=self.client.get('/staff/content/articles/new/')
        self.assertContains(response,'js/editor.js')
        self.assertContains(response,'rich-editor')
        self.assertEqual(response['Cache-Control'],'no-store, private')
        self.assertIn("script-src 'self'",response['Content-Security-Policy'])
        self.assertIn("style-src 'self' 'unsafe-inline'",response['Content-Security-Policy'])
        self.assertNotIn('unsafe-inline',self.client.get('/')['Content-Security-Policy'])

    def test_logo_favicon_and_simplified_design(self):
        response=self.client.get('/')
        self.assertContains(response,'images/holy-family-original.png')
        self.assertContains(response,'rel="icon" href="/static/images/holy-family-favicon.ico"')
        self.assertContains(response,'/staff/')
        self.assertNotContains(response,'caption-dot')
        self.assertNotContains(response,'brand-mark')
        self.assertNotContains(self.client.get('/apply/'),'status-pill')
        from pathlib import Path
        from django.conf import settings
        for filename, size in [('school-logo-transparent.png',256),('favicon-transparent-32.png',32),('apple-touch-icon-transparent.png',180)]:
            with Image.open(Path(settings.BASE_DIR)/'static/images'/filename) as image:
                self.assertEqual(image.size,(size,size))

    def test_admin_is_reserved_for_superusers(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get('/admin/').status_code,302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/admin/').status_code,200)

    def test_unknown_content_registry_is_not_exposed(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/staff/content/users/').status_code,404)
        self.assertEqual(self.client.post('/staff/content/users/new/',{}).status_code,404)

    def test_role_revocation_hides_previous_private_activity(self):
        self.client.force_login(self.officer)
        self.client.post(f'/staff/applications/{self.application.pk}/', {'status':'reviewing','staff_notes':'Private follow-up'})
        self.officer.groups.set([Group.objects.get(name='Content editors')])
        response=self.client.get('/staff/')
        self.assertNotContains(response,'Private Learner')
        self.assertNotContains(response,'Application review updated')
        self.assertEqual(self.client.get(f'/staff/applications/{self.application.pk}/').status_code,403)

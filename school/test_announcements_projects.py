from datetime import timedelta
from importlib import import_module

from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Announcement, Project, SiteSettings
from .staff_forms import AnnouncementForm


@override_settings(SECURE_SSL_REDIRECT=False, DEBUG=False, SITE_URL='https://school.example.test',
                   ALLOWED_HOSTS=['testserver'], STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class AnnouncementsProjectsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = SiteSettings.objects.create(demo_mode=False)
        call_command('setup_staff_groups', verbosity=0)
        cls.editor = User.objects.create_user('new-content-editor', is_staff=True)
        cls.editor.groups.add(Group.objects.get(name='Content editors'))
        cls.office = User.objects.create_user('new-content-office', is_staff=True)
        cls.office.groups.add(Group.objects.get(name='Admissions officers'))
        cls.now = timezone.now()
        cls.notice = Announcement.objects.create(title='Uniform collection', excerpt='Collect from the office.',
            body='<p>Collection arrangements.</p>', published=True, pinned=True)
        cls.project = Project.objects.create(title='Library improvement', excerpt='Improving our reading space.',
            body='<p>Project details.</p>', published=True, status='ongoing')

    def test_homepage_and_public_pages_separate_notices_projects_and_events(self):
        response = self.client.get('/')
        self.assertContains(response, 'Uniform collection')
        self.assertContains(response, 'Library improvement')
        self.assertLess(response.content.index(b'id="announcements-heading"'), response.content.index(b'Upcoming dates'))
        self.assertContains(self.client.get('/announcements/'), 'Uniform collection')
        self.assertContains(self.client.get('/projects/'), 'Ongoing')
        for route, item, label in [('announcement', self.notice, 'Back to announcements'), ('project', self.project, 'Back to projects')]:
            response = self.client.get(reverse(route, args=[item.slug]))
            self.assertContains(response, label)
            self.assertContains(response, 'name="description"')
            self.assertContains(response, 'rel="canonical"')
            self.assertEqual(response.content.count(b'<h1'), 1)

    def test_drafts_future_and_expired_notices_never_leak(self):
        for changes in [{'published': False}, {'published_at': self.now + timedelta(days=1)},
                        {'expires_at': self.now - timedelta(seconds=1)}]:
            notice = Announcement.objects.create(title='Hidden notice', excerpt='Do not show', body='<p>Private</p>',
                                                **{'published': True, **changes})
            self.assertEqual(self.client.get(reverse('announcement', args=[notice.slug])).status_code, 404)
            self.assertNotContains(self.client.get('/announcements/'), 'Hidden notice')
            self.assertNotContains(self.client.get('/'), 'Hidden notice')
            self.assertNotContains(self.client.get('/sitemap.xml'), reverse('announcement', args=[notice.slug]))
        self.project.published_at = self.now + timedelta(days=1)
        self.project.save()
        self.assertEqual(self.client.get(reverse('project', args=[self.project.slug])).status_code, 404)
        self.assertNotContains(self.client.get('/'), 'Library improvement')

    def test_pinned_notices_first_and_project_order_is_respected(self):
        newer = Announcement.objects.create(title='Later notice', excerpt='New notice', body='<p>Notice</p>', published=True)
        self.assertEqual(list(Announcement.objects.live())[:2], [self.notice, newer])
        self.project.order = 2
        self.project.save()
        first = Project.objects.create(title='Priority project', excerpt='Priority', body='<p>Details</p>', published=True, order=0)
        self.assertEqual(list(Project.objects.live())[:2], [first, self.project])

    def test_emoji_content_survives_save_and_public_rendering(self):
        for model, route in [(Announcement, 'announcement'), (Project, 'project')]:
            with self.subTest(model=model.__name__):
                item = model.objects.create(
                    title='📢 School update', excerpt='📚 News for families',
                    body='<p>Welcome 🎉</p>', published=True,
                )
                item.refresh_from_db()
                self.assertEqual(item.title, '📢 School update')
                self.assertEqual(item.excerpt, '📚 News for families')
                self.assertEqual(item.body, '<p>Welcome 🎉</p>')
                response = self.client.get(reverse(route, args=[item.slug]))
                self.assertContains(response, item.title)
                self.assertContains(response, item.excerpt)
                self.assertContains(response, item.body, html=True)

    def test_expiry_validation_and_slugs_are_automatic_stable_and_unique(self):
        form = AnnouncementForm({'title': 'Invalid expiry', 'excerpt': 'Summary', 'body': '<p>Body</p>',
                                 'published_at': self.now, 'expires_at': self.now - timedelta(hours=1)})
        self.assertFalse(form.is_valid())
        self.assertIn('expires_at', form.errors)
        for model in [Announcement, Project]:
            one = model.objects.create(title='Shared title', excerpt='Summary', body='<script>alert(1)</script><p>Safe</p>')
            two = model.objects.create(title='Shared title', excerpt='Summary', body='<p>Safe</p>')
            self.assertEqual(one.slug, 'shared-title')
            self.assertEqual(two.slug, 'shared-title-2')
            one.title = 'New title'; one.save()
            self.assertEqual(one.slug, 'shared-title')
            self.assertNotIn('<script', one.body)

    def test_editor_can_manage_new_sections_with_audit_and_public_preview(self):
        self.client.force_login(self.editor)
        for section, model, route in [('announcements', Announcement, 'announcement'), ('projects', Project, 'project')]:
            response = self.client.get(reverse('staff-list', args=[section]))
            self.assertContains(response, f'/staff/content/{section}/new/')
            data = {'title': f'New {section}', 'excerpt': 'Summary', 'body': '<p>Content</p>',
                    'published': 'on', 'published_at': (self.now-timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M'),
                    'order': 0, 'status': 'planned'}
            response = self.client.post(reverse('staff-create', args=[section]), data)
            self.assertEqual(response.status_code, 302)
            item = model.objects.get(title=f'New {section}')
            self.assertTrue(LogEntry.objects.filter(object_id=str(item.pk), content_type__model=model._meta.model_name).exists())
            self.assertContains(self.client.get(reverse('staff-edit', args=[section, item.pk])), reverse(route, args=[item.slug]))
            self.assertEqual(self.client.post(reverse('staff-delete', args=[section, item.pk])).status_code, 302)
            self.assertFalse(model.objects.filter(pk=item.pk).exists())

    def test_office_cannot_manage_new_public_content(self):
        self.client.force_login(self.office)
        for section in ['announcements', 'projects']:
            self.assertEqual(self.client.get(reverse('staff-list', args=[section])).status_code, 403)
            self.assertEqual(self.client.post(reverse('staff-create', args=[section]), {'title': 'Unauthorised'}).status_code, 403)
        response = self.client.get('/staff/')
        self.assertNotContains(response, '/staff/content/announcements/')
        self.assertNotContains(response, '/staff/content/projects/')

    def test_pagination_back_links_and_sitemap_include_only_live_items(self):
        for number in range(10):
            Announcement.objects.create(title=f'Notice {number}', excerpt='Summary', body='<p>Body</p>', published=True)
        response = self.client.get('/announcements/?page=2')
        self.assertContains(response, '?page=2')
        item = response.context['items'][0]
        self.assertContains(self.client.get(reverse('announcement', args=[item.slug])+'?page=2'), '/announcements/?page=2')
        sitemap = self.client.get('/sitemap.xml')
        for path in ['/announcements/', '/projects/', reverse('announcement', args=[self.notice.slug]), reverse('project', args=[self.project.slug])]:
            self.assertContains(sitemap, 'https://school.example.test'+path)

    def test_obsolete_controls_removed_and_history_remains_editable(self):
        self.client.force_login(self.editor)
        response = self.client.get('/staff/settings/')
        for field in ['motto', 'about_title', 'admissions_fee']:
            self.assertNotContains(response, f'name="{field}"')
        self.assertContains(response, 'name="about_text"')
        self.assertContains(response, 'name="about_history"')

    def test_existing_editor_groups_gain_new_permissions_on_upgrade(self):
        group = Group.objects.get(name='Content editors')
        group.permissions.remove(*Permission.objects.filter(content_type__app_label='school', content_type__model__in=['announcement', 'project']))
        original = set(group.permissions.values_list('pk', flat=True))
        import_module('school.migrations.0020_announcement_project').grant_content_permissions(apps, connection.schema_editor())
        self.assertTrue(original.issubset(set(group.permissions.values_list('pk', flat=True))))
        self.assertEqual(group.permissions.filter(content_type__model__in=['announcement','project']).count(), 8)

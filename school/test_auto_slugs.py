from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import connection, IntegrityError, models
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Article, Event, Page, SchoolLifePost, SiteSettings, StaffMember, StudentAuthor, Subject
from .staff_forms import ArticleForm, EventForm, SchoolLifePostForm, StaffMemberForm, SubjectForm


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class AutomaticSlugTests(TestCase):
    def setUp(self):
        SiteSettings.objects.create()
        self.author = StudentAuthor.objects.create(title='Student Example', grade='Grade 8')

    def content_types(self):
        return [(Article, {'excerpt':'News', 'body':'<p>News</p>'}),
                (Event, {'description':'<p>Event</p>', 'location':'School', 'starts_at':timezone.now()}),
                (Subject, {}), (StaffMember, {}), (Page, {'introduction':'Page'}),
                (SchoolLifePost, {'excerpt':'Poem', 'body':'<p>Poem</p>', 'category':'poem', 'author':self.author})]

    def test_all_content_generates_unique_slugs_and_preserves_existing_urls(self):
        for Model, defaults in self.content_types():
            with self.subTest(model=Model.__name__):
                first = Model.objects.create(title='Learning & growing together!', **defaults)
                second = Model.objects.create(title=first.title, **defaults)
                self.assertEqual(first.slug, 'learning-growing-together')
                self.assertEqual(second.slug, 'learning-growing-together-2')
                first.title = 'A changed title'
                first.save()
                first.refresh_from_db()
                self.assertEqual(first.slug, 'learning-growing-together')
                legacy = Model.objects.create(title='Imported title', slug='previously-shared-address', **defaults)
                legacy.title = 'Updated imported title'
                legacy.save()
                self.assertEqual(legacy.slug, 'previously-shared-address')

    def test_long_non_ascii_and_numeric_names_get_valid_bounded_slugs(self):
        for Model, defaults in self.content_types():
            with self.subTest(model=Model.__name__):
                max_length = Model._meta.get_field('slug').max_length
                for title in ['A' * Model._meta.get_field('title').max_length, '学校', '123']:
                    first = Model.objects.create(title=title, **defaults)
                    second = Model.objects.create(title=title, **defaults)
                    for item in [first, second]:
                        self.assertRegex(item.slug, r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
                        self.assertLessEqual(len(item.slug), max_length)
                        self.assertFalse(item.slug.isdecimal())
                    self.assertNotEqual(first.slug, second.slug)

    def test_generated_slug_is_persisted_in_partial_updates(self):
        member = StaffMember.objects.create(title='A staff member')
        StaffMember.objects.filter(pk=member.pk).update(slug='')
        member.refresh_from_db()
        member.title = 'Updated staff member'
        member.save(update_fields=['title'])
        member.refresh_from_db()
        self.assertEqual(member.slug, 'updated-staff-member')

    def test_concurrent_slug_collision_is_retried_but_other_integrity_errors_are_not_hidden(self):
        original_save = models.Model.save
        attempts = []
        def race(instance, *args, **kwargs):
            attempts.append(instance.slug)
            if len(attempts) == 1:
                raise IntegrityError('Another writer claimed this slug')
            return original_save(instance, *args, **kwargs)
        with patch.object(models.QuerySet, 'exists', side_effect=[False, True, False]), patch.object(models.Model, 'save', race):
            article = Article.objects.create(title='Shared title', excerpt='News', body='News')
        self.assertEqual(attempts, ['shared-title', 'shared-title-2'])
        self.assertEqual(article.slug, 'shared-title-2')
        with patch.object(models.Model, 'save', side_effect=IntegrityError('Other constraint')), self.assertRaises(IntegrityError):
            Article.objects.create(title='Unrelated error', excerpt='News', body='News')

    def test_staff_editors_do_not_request_or_accept_slug_fields(self):
        for Form in [ArticleForm, EventForm, SubjectForm, StaffMemberForm, SchoolLifePostForm]:
            self.assertNotIn('slug', Form().fields)
        call_command('setup_staff_groups', verbosity=0)
        editor = User.objects.create_user('slug-editor', is_staff=True)
        editor.groups.add(Group.objects.get(name='Content editors'))
        self.client.force_login(editor)
        for section in ['articles','events','subjects','staff-profiles','school-life']:
            self.assertNotContains(self.client.get(f'/staff/content/{section}/new/'), 'name="slug"')
        response = self.client.post('/staff/content/articles/new/', {
            'title':'Automatically addressed', 'slug':'injected-address', 'category':'News',
            'excerpt':'News', 'body':'<p>News</p>', 'published_at':'2026-10-15T10:00'})
        self.assertEqual(response.status_code, 302)
        article = Article.objects.get(title='Automatically addressed')
        self.assertEqual(article.slug, 'automatically-addressed')

    def test_backfill_changes_only_missing_slugs(self):
        first = Article.objects.create(title='Imported story', slug='imported-story', excerpt='News',body='News')
        blank = Article.objects.create(title='Imported story', excerpt='News',body='News')
        Article.objects.filter(pk=blank.pk).update(slug='')
        migration = import_module('school.migrations.0017_alter_article_slug_alter_event_slug_alter_page_slug_and_more')
        migration.fill_missing_slugs(apps, connection.schema_editor())
        first.refresh_from_db(); blank.refresh_from_db()
        self.assertEqual(first.slug, 'imported-story')
        self.assertEqual(blank.slug, 'imported-story-2')

from datetime import timedelta

from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Article, SchoolLifePost, SiteSettings, StudentAuthor
from .staff_forms import SchoolLifePostForm


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class SchoolLifeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        SiteSettings.objects.create(demo_mode=False)
        call_command('setup_staff_groups', verbosity=0)
        cls.editor = User.objects.create_user('writing-editor', is_staff=True)
        cls.editor.groups.add(Group.objects.get(name='Content editors'))
        cls.author = StudentAuthor.objects.create(title='Lerato Mokoena', grade='Grade 8')

    def payload(self, **changes):
        return dict(title='A hopeful morning', slug='', category='poem', excerpt='A student poem.',
                    body='<p>First line.<br>Second line.</p>', published=True,
                    published_at=(timezone.now()-timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M'),
                    author=self.author.pk, **changes)

    def post(self, **changes):
        defaults = dict(title='A hopeful morning', category='poem', excerpt='A student poem.',
                        body='<p>First line.<br>Second line.</p>', author=self.author, published=True)
        return SchoolLifePost.objects.create(**(defaults | changes))

    def test_only_live_posts_are_public_and_news_remains_separate(self):
        item = self.post()
        draft = self.post(title='Private writing', published=False)
        future = self.post(title='Tomorrow’s writing', published_at=timezone.now()+timedelta(days=1))
        Article.objects.create(title='Official school news', slug='official', excerpt='News', body='News', published=True)
        response = self.client.get('/school-life/')
        for text in [item.title, 'Poem', self.author.title, 'Grade 8']:
            self.assertContains(response, text)
        for text in [draft.title, future.title, 'Official school news']:
            self.assertNotContains(response, text)
        self.assertNotContains(self.client.get('/news/'), item.title)
        self.assertEqual(self.client.get(reverse('school-life-post', args=[draft.slug])).status_code, 404)
        self.assertEqual(self.client.get(reverse('school-life-post', args=[future.slug])).status_code, 404)
        detail = self.client.get(reverse('school-life-post', args=[item.slug]))
        self.assertContains(detail, 'Written by')
        self.assertContains(detail, 'Grade 8')
        self.assertContains(detail, '<br>')
        self.assertContains(detail, '<time datetime=')
        self.assertEqual(detail.content.count(b'<h1'), 1)

    def test_inline_author_creation_reuse_and_credit_snapshot(self):
        self.client.force_login(self.editor)
        data = self.payload()
        data.update(author='', new_author_name='  THABO   MOLEFE  ', new_author_grade='Grade 9')
        response = self.client.post('/staff/content/school-life/new/', data)
        self.assertEqual(response.status_code, 302)
        first = SchoolLifePost.objects.get()
        self.assertEqual(first.author_name, 'Thabo Molefe')
        data.update(title='Another poem', slug='another-poem')
        self.assertEqual(self.client.post('/staff/content/school-life/new/', data).status_code, 302)
        self.assertEqual(StudentAuthor.objects.filter(title='Thabo Molefe').count(), 1)
        author = first.author
        author.grade = 'Grade 10'
        author.save()
        first.title = 'A corrected title'
        old_slug = first.slug
        first.save()
        first.refresh_from_db()
        self.assertEqual(first.author_grade, 'Grade 9')
        self.assertEqual(first.slug, old_slug)
        second = self.post(title='New term', author=author)
        self.assertEqual(second.author_grade, 'Grade 10')
        with self.assertRaises(ProtectedError):
            author.delete()
        response = self.client.post(f'/staff/content/student-authors/{author.pk}/delete/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StudentAuthor.objects.filter(pk=author.pk).exists())

    def test_migration_adds_editor_permissions_without_removing_existing_grants(self):
        from importlib import import_module
        from django.apps import apps
        from django.db import connection
        group = Group.objects.get(name='Content editors')
        original = set(group.permissions.values_list('pk', flat=True))
        grant = import_module('school.migrations.0016_studentauthor_schoollifepost').grant_existing_editors
        grant(apps, connection.schema_editor())
        self.assertTrue(original.issubset(set(group.permissions.values_list('pk', flat=True))))
        self.assertEqual(group.permissions.filter(content_type__model__in=['studentauthor','schoollifepost']).count(), 8)

    def test_existing_author_saves_and_content_is_sanitized(self):
        form = SchoolLifePostForm(self.payload())
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertEqual(item.author, self.author)
        item.body = '<script>bad()</script><p onclick="bad()">Safe</p>'
        item.save()
        self.assertNotIn('<script', item.body)
        self.assertNotIn('onclick', item.body)
        copy = self.post(title=item.title)
        self.assertNotEqual(item.slug, copy.slug)
        data = self.payload()
        data.update(new_author_name='Other student', new_author_grade='Grade 8')
        self.assertFalse(SchoolLifePostForm(data).is_valid())

    def test_embedded_upload_can_be_saved_and_rendered_by_school_life_editor(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        writer = User.objects.create_user('image-writer', is_staff=True)
        writer.user_permissions.add(Permission.objects.get(codename='add_schoollifepost'))
        self.client.force_login(writer)
        buffer = BytesIO()
        Image.new('RGB', (30, 20), '#174b3b').save(buffer, format='PNG')
        response = self.client.post('/staff/images/upload/', {'file':SimpleUploadedFile('classroom.png',buffer.getvalue(),content_type='image/png')})
        self.assertEqual(response.status_code, 200)
        location = response.json()['location']
        self.assertRegex(location, r'^/media/editor/[a-f0-9]{32}\.jpg$')
        data = self.payload()
        data['body'] = f'<p>Before the photo.</p><figure><img src="{location}" alt="Our classroom"><figcaption>A day at school</figcaption></figure><p>After the photo.</p>'
        self.assertEqual(self.client.post('/staff/content/school-life/new/', data).status_code, 302)
        item = SchoolLifePost.objects.get()
        response = self.client.get(reverse('school-life-post', args=[item.slug]))
        self.assertContains(response, location)
        self.assertContains(response, 'alt="Our classroom"')
        self.assertContains(response, '<figcaption>A day at school</figcaption>')

    def test_permissions_and_author_validation(self):
        self.assertEqual(self.client.get('/staff/content/school-life/').status_code, 302)
        office = User.objects.create_user('office-writer', is_staff=True)
        office.groups.add(Group.objects.get(name='Admissions officers'))
        self.client.force_login(office)
        self.assertEqual(self.client.get('/staff/content/school-life/').status_code, 403)
        self.assertEqual(self.client.post('/staff/content/student-authors/new/', {'title':'Student','grade':'Grade 8'}).status_code, 403)
        limited = User.objects.create_user('limited-writer', is_staff=True)
        limited.user_permissions.add(Permission.objects.get(codename='add_schoollifepost'))
        self.client.force_login(limited)
        data = self.payload()
        data.update(author='', new_author_name='Unauthorized author', new_author_grade='Grade 8')
        self.assertEqual(self.client.post('/staff/content/school-life/new/', data).status_code, 200)
        self.assertFalse(StudentAuthor.objects.filter(title='Unauthorized Author').exists())
        for changes in [dict(author=''), dict(author='',new_author_name='Name'), dict(author='',new_author_grade='Grade 8')]:
            form = SchoolLifePostForm(self.payload() | changes)
            self.assertFalse(form.is_valid())

    def test_filters_pagination_and_navigation(self):
        self.post(title='A story', category='story')
        for number in range(10):
            self.post(title=f'Poem {number}')
        response = self.client.get('/school-life/?category=poem')
        self.assertEqual(len(response.context['items']), 9)
        self.assertNotContains(response, 'A story')
        self.assertContains(response, '?category=poem&amp;page=2')
        for path in ['/', '/news/', '/school-life/']:
            response = self.client.get(path)
            self.assertContains(response, '>Community ')
            self.assertContains(response, 'href="/news/"')
            self.assertContains(response, 'href="/school-life/"')
        self.client.force_login(self.editor)
        response = self.client.get('/staff/content/school-life/new/')
        self.assertContains(response, '<legend>Student author</legend>')
        self.assertContains(response, 'name="author"')
        self.assertContains(response, 'name="new_author_grade"')
        self.assertEqual(self.client.get('/staff/content/student-authors/?state=published').status_code, 200)

    @override_settings(SITE_URL='https://school.example.test', DEBUG=False)
    def test_seo_and_sitemap_include_only_published_work(self):
        item = self.post()
        draft = self.post(title='Private poem', published=False)
        response = self.client.get(reverse('school-life-post', args=[item.slug]))
        self.assertContains(response, f'https://school.example.test/school-life/{item.slug}/')
        self.assertContains(response, 'property="article:published_time"')
        sitemap = self.client.get('/sitemap.xml')
        self.assertContains(sitemap, f'/school-life/{item.slug}/')
        self.assertNotContains(sitemap, f'/school-life/{draft.slug}/')

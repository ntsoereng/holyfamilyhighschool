from importlib import import_module
from io import BytesIO

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, models
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Department, Page, SiteSettings, StaffMember, Subject
from .staff_forms import SettingsForm


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class FixedPageTests(TestCase):
    def setUp(self):
        self.site = SiteSettings.objects.create(about_history='<p>School history.</p>')
        call_command('setup_staff_groups', verbosity=0)
        self.editor = User.objects.create_user('page-editor', is_staff=True)
        self.editor.groups.add(Group.objects.get(name='Content editors'))

    def payload(self, **changes):
        self.site.refresh_from_db()
        return {**{name: getattr(self.site, name) for name in SettingsForm._meta.fields
                   if not isinstance(self.site._meta.get_field(name), models.ImageField)}, **changes}

    def image(self):
        data = BytesIO()
        Image.new('RGB', (100, 60), '#174b3b').save(data, format='PNG')
        return SimpleUploadedFile('header.png', data.getvalue(), content_type='image/png')

    def test_all_seven_pages_are_available_without_page_records(self):
        for path in ['/', '/about/', '/contact/', '/curriculum/', '/our-staff/', '/events/', '/apply/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content.count(b'<h1'), 1)
                self.assertNotIn(b'style=', response.content)
                self.assertIn("script-src 'self'", response['Content-Security-Policy'])

    def test_every_header_image_can_be_uploaded_and_cleared(self):
        self.client.force_login(self.editor)
        for key, path in [('about', '/about/'), ('curriculum', '/curriculum/'), ('staff', '/our-staff/'),
                          ('calendar', '/events/'), ('contact', '/contact/'), ('admissions', '/apply/')]:
            with self.subTest(key=key):
                self.assertNotContains(self.client.get(path), 'has-header-image')
                response = self.client.post('/staff/settings/', self.payload(**{
                    key + '_image': self.image(), key + '_image_alt': key + ' photograph'}))
                self.assertEqual(response.status_code, 302)
                self.site.refresh_from_db()
                response = self.client.get(path)
                self.assertContains(response, 'has-header-image')
                self.assertContains(response, getattr(self.site, key + '_image').url)
                self.assertContains(response, f'alt="{key} photograph"')
                response = self.client.post('/staff/settings/', self.payload(**{key + '_image-clear': 'on'}))
                self.assertEqual(response.status_code, 302)
                self.assertNotContains(self.client.get(path), 'has-header-image')

    def test_page_builder_routes_and_controls_are_removed(self):
        archived = Page.objects.create(title='Hidden legacy page', slug='arbitrary', introduction='Legacy', published=True)
        self.client.force_login(self.editor)
        for path in ['/staff/content/pages/', '/staff/content/pages/new/',
                     f'/staff/content/pages/{archived.pk}/', '/school/arbitrary/']:
            self.assertEqual(self.client.get(path).status_code, 404)
        response = self.client.get('/staff/settings/')
        for control in ['name="layout"', 'name="show_in_navigation"', 'name="show_school_values"']:
            self.assertNotContains(response, control)
        self.assertContains(response, 'name="about_history"')
        self.assertContains(response, 'name="hero_image"')
        self.assertNotContains(self.client.get('/'), 'Hidden legacy page')

    def test_history_and_curriculum_are_sanitized(self):
        self.site.about_history = '<script>bad()</script><p onclick="bad()">History</p>'
        self.site.curriculum_body = '<a href="javascript:bad()">Learning</a>'
        self.site.save()
        self.assertNotIn('<script', self.site.about_history)
        self.assertNotIn('onclick', self.site.about_history)
        self.assertNotIn('javascript:', self.site.curriculum_body)

    def test_data_migration_preserves_archived_content_and_existing_edits(self):
        page = Page.objects.create(title='Our history', slug='about', introduction='Our roots', body='<p>Archived history.</p>',
                                   mission='Our mission text', vision='Our vision text', image='school/old-header.png')
        preserve = import_module('school.migrations.0008_preserve_fixed_page_content').preserve_content
        preserve(apps, connection.schema_editor())
        self.site.refresh_from_db()
        self.assertEqual(self.site.about_history, '<p>School history.</p>')
        self.assertEqual(self.site.about_mission, page.mission)
        self.assertEqual(self.site.about_vision, page.vision)
        self.assertEqual(self.site.about_image.name, page.image.name)
        self.assertTrue(Page.objects.filter(pk=page.pk).exists())

    def test_subjects_and_staff_do_not_depend_on_page_layout_settings(self):
        Subject.objects.create(title='Mathematics', slug='mathematics', published=True)
        Subject.objects.create(title='Draft subject', slug='draft')
        department = Department.objects.create(title='Sciences')
        teacher = StaffMember.objects.create(title='Demo Teacher', published=True)
        teacher.departments.add(department)
        StaffMember.objects.create(title='Private profile')
        self.assertContains(self.client.get('/curriculum/'), 'Mathematics')
        self.assertNotContains(self.client.get('/curriculum/'), 'Draft subject')
        response = self.client.get('/our-staff/')
        self.assertContains(response, 'Sciences')
        self.assertNotContains(response, 'Demo Teacher')
        department_url = reverse('school-department', kwargs={'pk': department.pk})
        self.assertContains(response, f'href="{department_url}"')
        self.assertContains(self.client.get(department_url), 'Demo Teacher')
        self.assertNotContains(self.client.get('/our-staff/'), 'Private profile')

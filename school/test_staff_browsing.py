from datetime import date
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Department, SiteSettings, StaffMember
from .staff_forms import StaffMemberForm


TEST_STORAGE = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGE)
class PublicStaffBrowsingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = SiteSettings.objects.create()
        cls.sciences = Department.objects.create(title='Sciences', description='Explore science.', order=1)
        cls.languages = Department.objects.create(title='Languages', order=2)
        cls.empty_department = Department.objects.create(title='School administration', order=3)
        cls.hidden_department = Department.objects.create(title='Private department', published=False)
        cls.teacher = StaffMember.objects.create(
            title='Lerato Mokoena', honorific='Dr.', position='Science teacher',
            biography=' '.join(f'Biographyword{number}' for number in range(1, 36)),
            date_from=date(2020, 2, 1), published=True,
        )
        cls.teacher.departments.add(cls.sciences, cls.languages, cls.hidden_department)
        cls.draft = StaffMember.objects.create(title='Private draft teacher', published=False)
        cls.draft.departments.add(cls.sciences)
        cls.hidden_teacher = StaffMember.objects.create(title='Private department teacher', published=True)
        cls.hidden_teacher.departments.add(cls.hidden_department)
        cls.unassigned = StaffMember.objects.create(title='School team member', published=True)
        cls.draft_unassigned = StaffMember.objects.create(title='Private unassigned draft', published=False)

    def department_url(self, department):
        return reverse('school-department', kwargs={'pk': department.pk})

    def profile_url(self, member):
        return reverse('school-staff-profile', kwargs={'pk': member.pk})

    def test_directory_starts_with_departments_and_published_member_counts(self):
        response = self.client.get(reverse('school-staff'))
        self.assertEqual(response.status_code, 200)
        departments = list(response.context['departments'])
        self.assertEqual([department.pk for department in departments], [
            self.sciences.pk, self.languages.pk, self.empty_department.pk,
        ])
        self.assertEqual({department.pk: department.public_member_count for department in departments}, {
            self.sciences.pk: 1, self.languages.pk: 1, self.empty_department.pk: 0,
        })
        self.assertContains(response, '1 staff member', count=2)
        self.assertContains(response, '0 staff members', count=1)
        for department in [self.sciences, self.languages, self.empty_department]:
            self.assertContains(response, department.title)
            self.assertContains(response, f'href="{self.department_url(department)}"')
        self.assertNotContains(response, self.teacher.title)
        self.assertNotContains(response, self.profile_url(self.teacher))
        for private_name in [
            self.hidden_department.title, self.hidden_teacher.title,
            self.draft.title, self.draft_unassigned.title,
        ]:
            self.assertNotContains(response, private_name)

    def test_unassigned_published_members_have_school_team_fallback(self):
        response = self.client.get(reverse('school-staff'))
        self.assertContains(response, 'School team')
        self.assertContains(response, self.unassigned.title)
        self.assertContains(response, f'href="{self.profile_url(self.unassigned)}"')
        self.assertNotContains(response, self.draft_unassigned.title)

    def test_department_lists_only_published_members_and_links_profiles(self):
        for department in [self.sciences, self.languages]:
            with self.subTest(department=department.title):
                response = self.client.get(self.department_url(department))
                self.assertContains(response, department.title)
                self.assertEqual([member.pk for member in response.context['members']], [self.teacher.pk])
                self.assertContains(response, self.teacher.display_name)
                self.assertContains(response, f'href="{self.profile_url(self.teacher)}"')
                self.assertContains(response, 'Biographyword24')
                self.assertNotContains(response, 'Biographyword25')
                self.assertNotContains(response, self.draft.title)
                self.assertNotContains(response, self.hidden_teacher.title)
                self.assertNotContains(response, self.unassigned.title)

    def test_empty_published_department_is_accessible_and_hidden_department_is_not(self):
        response = self.client.get(self.department_url(self.empty_department))
        self.assertContains(response, self.empty_department.title)
        self.assertContains(response, 'More about our team, soon.')
        self.assertNotContains(response, self.teacher.title)
        self.assertContains(response, f'href="{reverse("school-staff")}"')
        self.assertEqual(self.client.get(self.department_url(self.hidden_department)).status_code, 404)
        self.assertEqual(self.client.get(reverse('school-department', kwargs={'pk': 999999})).status_code, 404)

    def test_profile_shows_full_biography_metadata_and_only_public_department_links(self):
        response = self.client.get(self.profile_url(self.teacher))
        self.assertContains(response, 'Dr. Lerato Mokoena')
        self.assertContains(response, 'Science teacher')
        self.assertContains(response, self.teacher.biography)
        self.assertContains(response, 'February 2020')
        for department in [self.sciences, self.languages]:
            self.assertContains(response, f'href="{self.department_url(department)}"')
        self.assertNotContains(response, self.hidden_department.title)
        self.assertNotContains(response, self.department_url(self.hidden_department))
        self.assertEqual(response.content.count(b'<h1'), 1)

    def test_profile_visibility_requires_published_member_and_public_membership_or_no_departments(self):
        for member, status in [
            (self.teacher, 200), (self.unassigned, 200),
            (self.draft, 404), (self.draft_unassigned, 404), (self.hidden_teacher, 404),
        ]:
            with self.subTest(member=member.title):
                self.assertEqual(self.client.get(self.profile_url(member)).status_code, status)
        self.assertEqual(self.client.get(reverse('school-staff-profile', kwargs={'pk': 999999})).status_code, 404)

    def test_revoking_last_public_department_hides_profile_without_revealing_drafts(self):
        self.sciences.published = False
        self.sciences.save()
        self.assertEqual(self.client.get(self.profile_url(self.teacher)).status_code, 200)
        self.languages.published = False
        self.languages.save()
        self.assertEqual(self.client.get(self.profile_url(self.teacher)).status_code, 404)
        self.assertNotContains(self.client.get(reverse('school-staff')), self.teacher.title)

    def test_existing_names_remain_unchanged_and_optional_metadata_is_not_invented(self):
        legacy = StaffMember.objects.create(title='Sr. Mary Example', published=True)
        legacy.refresh_from_db()
        self.assertEqual(legacy.title, 'Sr. Mary Example')
        self.assertEqual(legacy.display_name, 'Sr. Mary Example')
        self.assertEqual(legacy.honorific, '')
        self.assertIsNone(legacy.date_from)
        response = self.client.get(self.profile_url(legacy))
        self.assertContains(response, 'Sr. Mary Example')
        self.assertNotContains(response, 'None')
        self.assertNotContains(response, 'src=""')
        self.assertContains(response, 'A biography hasn’t been shared yet.')
        self.assertNotContains(response, 'At Holy Family from')
        self.assertRegex(response.content.decode(), r'aria-hidden="true"[^>]*>\s*S\s*</')

    def test_profile_escapes_biography_and_honorific(self):
        member = StaffMember.objects.create(
            title='Safe Name', honorific='<script>bad()</script>',
            biography='<img src=x onerror="bad()">', published=True,
        )
        response = self.client.get(self.profile_url(member))
        self.assertContains(response, '&lt;script&gt;bad()&lt;/script&gt;')
        self.assertContains(response, '&lt;img')
        self.assertNotContains(response, '<script>bad()</script>')
        self.assertNotContains(response, '<img src=x')

    def test_directory_empty_state_remains_accessible(self):
        StaffMember.objects.all().delete()
        Department.objects.all().delete()
        response = self.client.get(reverse('school-staff'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['departments']), [])
        self.assertEqual(list(response.context['other_staff']), [])
        self.assertEqual(response.content.count(b'<h1'), 1)
        self.assertContains(response, 'Our team, coming soon.')
        self.assertContains(response, f'href="{reverse("contact")}"')


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGE)
class StaffProfileEditingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_staff_groups', verbosity=0)
        cls.school = SiteSettings.objects.create()
        cls.editor = User.objects.create_user('profile-editor', is_staff=True)
        cls.editor.groups.add(Group.objects.get(name='Content editors'))
        cls.department = Department.objects.create(title='Languages')

    def payload(self, **changes):
        return {
            'title': 'Mpho Example', 'honorific': 'Ms.', 'position': 'Language teacher',
            'date_from': '2021-08-02', 'departments': [self.department.pk],
            'biography': 'Supports learners in the language classroom.',
            'image_alt': 'Mpho in the school grounds', 'order': 0, 'published': 'on',
            **changes,
        }

    def image(self):
        data = BytesIO()
        Image.new('RGB', (80, 100), '#174b3b').save(data, format='PNG')
        return SimpleUploadedFile('teacher.png', data.getvalue(), content_type='image/png')

    def test_optional_honorific_and_start_date_are_editable_in_staff_workspace(self):
        form = StaffMemberForm()
        self.assertEqual(form.fields['title'].label, 'Full names')
        self.assertFalse(form.fields['honorific'].required)
        self.assertFalse(form.fields['date_from'].required)
        self.client.force_login(self.editor)
        response = self.client.post('/staff/content/staff-profiles/new/', self.payload(image=self.image()))
        member = StaffMember.objects.get(title='Mpho Example')
        self.assertRedirects(response, f'/staff/content/staff-profiles/{member.pk}/', fetch_redirect_response=False)
        self.assertEqual(member.honorific, 'Ms.')
        self.assertEqual(member.date_from, date(2021, 8, 2))
        self.assertEqual(member.display_name, 'Ms. Mpho Example')
        self.assertEqual(list(member.departments.all()), [self.department])
        response = self.client.get(reverse('school-staff-profile', kwargs={'pk': member.pk}))
        self.assertContains(response, member.image.url)
        self.assertContains(response, 'alt="Mpho in the school grounds"')
        self.assertContains(response, 'August 2021')

    def test_legacy_staff_form_can_save_without_new_optional_metadata(self):
        member = StaffMember.objects.create(title='Sr. Existing Teacher', published=True)
        data = self.payload(title=member.title, honorific='', date_from='')
        data.pop('honorific')
        data.pop('date_from')
        form = StaffMemberForm(data, instance=member)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        member.refresh_from_db()
        self.assertEqual(member.title, 'Sr. Existing Teacher')
        self.assertEqual(member.display_name, 'Sr. Existing Teacher')
        self.assertEqual(member.honorific, '')
        self.assertIsNone(member.date_from)

    def test_invalid_or_oversized_profile_metadata_is_rejected(self):
        for changes, field in [
            ({'honorific': 'A' * 41}, 'honorific'),
            ({'date_from': 'not-a-date'}, 'date_from'),
            ({'date_from': '2021-02-30'}, 'date_from'),
        ]:
            with self.subTest(field=field, changes=changes):
                form = StaffMemberForm(self.payload(**changes))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        self.assertFalse(StaffMember.objects.exists())

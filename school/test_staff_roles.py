from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings

from .roles import STAFF_ROLES
from .staff import CONTENT


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class StaffRoleGuideTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_staff_groups', verbosity=0)
        cls.owner = User.objects.create_superuser('roles-owner', 'owner@example.com', 'Not-used-for-login-94!')

    def test_standard_roles_cover_current_content_without_private_data_leakage(self):
        expected_content = {model._meta.model_name for model, *_ in CONTENT.values()} | {'sitesettings'}
        self.assertEqual(set(STAFF_ROLES[0]['models']), expected_content)
        editor = Group.objects.get(name='Content editors')
        office = Group.objects.get(name='Admissions officers')
        self.assertEqual(set(editor.permissions.values_list('content_type__model', flat=True)), expected_content)
        self.assertEqual(set(office.permissions.values_list('content_type__model', flat=True)), {'application', 'contactmessage'})
        self.assertFalse(editor.permissions.filter(content_type__app_label__in=['auth', 'axes']).exists())
        self.assertEqual(editor.permissions.count(), len(expected_content) * 4)
        self.assertEqual(office.permissions.count(), 8)

    def test_admin_sees_role_powers_and_form_help(self):
        self.client.force_login(self.owner)
        response = self.client.get('/staff/team/')
        for text in ['Choose the right access', 'School Life stories, poems and articles',
                     'reusable student authors', 'permanent deletion', 'Website administrator',
                     'school management titles', 'id_role_helptext']:
            self.assertContains(response, text)

    def test_content_editor_cannot_manage_accounts(self):
        editor = User.objects.create_user('role-editor', is_staff=True)
        editor.groups.add(Group.objects.get(name='Content editors'))
        self.client.force_login(editor)
        self.assertEqual(self.client.get('/staff/team/').status_code, 403)

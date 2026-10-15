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

    def test_account_creation_provisions_missing_groups_for_each_role(self):
        self.client.force_login(self.owner)
        for number, (role, expected) in enumerate([
            ('Content editors', {'Content editors'}),
            ('Admissions officers', {'Admissions officers'}),
            ('both', {'Content editors', 'Admissions officers'}),
        ]):
            Group.objects.filter(name__in=['Content editors', 'Admissions officers']).delete()
            response = self.client.post('/staff/team/', {
                'username': f'new-role-{number}', 'role': role,
                'password1': 'Staff-test-password-749!', 'password2': 'Staff-test-password-749!',
            })
            self.assertRedirects(response, '/staff/team/')
            user = User.objects.get(username=f'new-role-{number}')
            self.assertTrue(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertEqual(set(user.groups.values_list('name', flat=True)), expected)
            self.assertEqual(user.has_perm('school.view_application'), role != 'Content editors')
            self.assertEqual(user.has_perm('school.add_schoollifepost'), role != 'Admissions officers')

    def test_automatic_setup_repairs_missing_permissions_and_preserves_custom_grants(self):
        from django.contrib.auth.models import Permission
        from .roles import ensure_staff_groups
        editor = Group.objects.get(name='Content editors')
        custom = Permission.objects.get(codename='view_group', content_type__app_label='auth')
        editor.permissions.set([custom])
        ensure_staff_groups()
        self.assertTrue(editor.permissions.filter(pk=custom.pk).exists())
        self.assertTrue(editor.permissions.filter(codename='add_schoollifepost').exists())
        original = set(editor.permissions.values_list('pk', flat=True))
        ensure_staff_groups()
        self.assertEqual(set(editor.permissions.values_list('pk', flat=True)), original)

    def test_invalid_role_does_not_create_an_account_or_groups(self):
        self.client.force_login(self.owner)
        Group.objects.all().delete()
        response = self.client.post('/staff/team/', {
            'username': 'invalid-role', 'role': 'Website administrator',
            'password1': 'Staff-test-password-749!', 'password2': 'Staff-test-password-749!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='invalid-role').exists())
        self.assertFalse(Group.objects.exists())

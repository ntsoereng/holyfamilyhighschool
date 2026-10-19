"""Standard staff roles shared by account guidance and permission setup."""
STAFF_ROLES = (
    {
        'name': 'Content editors',
        'label': 'Content editor',
        'icon': 'news',
        'models': ('announcement', 'project', 'schoollifepost', 'studentauthor', 'sitesettings', 'article', 'event',
                   'schoolvalue', 'department', 'staffmember', 'subject', 'schoolstatistic'),
        'summary': 'Manages the public website and school content.',
        'powers': (
            'Create, edit, publish, schedule and delete announcements, projects, news, events and School Life stories, poems and articles.',
            'Manage reusable student authors and grades, departments, staff profiles and management roles, subjects, school values and statistics.',
            'Upload content images and update Site Settings, including page content, contact details, Facebook, admissions information and the additional privacy notice.',
        ),
        'limits': 'Cannot read private applications or contact messages, manage staff accounts, or access Django administration.',
    },
    {
        'name': 'Admissions officers',
        'label': 'School office — admissions and messages',
        'icon': 'mail',
        'models': ('application', 'contactmessage', 'admissionrelease'),
        'extra_permissions': ('change_admissions_settings',),
        'summary': 'Handles admissions settings, private applications and enquiries.',
        'powers': (
            'Open or close admissions and update intake, payment and interview settings.',
            'Upload, publish, withdraw and delete annual admission results in bulk.',
            'View, search and export applications to Excel, update their review status and add private staff notes.',
            'View and search contact messages, update their status and add private staff notes.',
            'Permanently delete applications and contact messages when authorised under the school’s recordkeeping policy.',
        ),
        'limits': 'Cannot edit other website content or general Site Settings, manage staff accounts, or access Django administration.',
    },
)
STAFF_ROLE_CHOICES = tuple((role['name'], role['label']) for role in STAFF_ROLES) + (
    ('both', 'Content editor and school office'),
)


def ensure_staff_groups(*, synchronise=False):
    """Provision standard access; only explicit setup removes custom grants."""
    from django.contrib.auth.models import Group, Permission
    from django.db import transaction

    groups = {}
    with transaction.atomic():
        for role in STAFF_ROLES:
            group, _ = Group.objects.get_or_create(name=role['name'])
            permissions = Permission.objects.filter(
                content_type__app_label='school', content_type__model__in=role['models'],
                codename__in=[f'{action}_{model}' for model in role['models']
                              for action in ('view', 'add', 'change', 'delete')])
            permissions = list(permissions) + list(Permission.objects.filter(
                content_type__app_label='school', content_type__model='sitesettings',
                codename__in=role.get('extra_permissions', ())))
            if synchronise:
                group.permissions.set(permissions)
            else:
                group.permissions.add(*permissions)
            groups[role['name']] = group
    return groups

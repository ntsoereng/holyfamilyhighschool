"""Standard staff roles shared by account guidance and permission setup."""
STAFF_ROLES = (
    {
        'name': 'Content editors',
        'label': 'Content editor',
        'icon': 'news',
        'models': ('schoollifepost', 'studentauthor', 'sitesettings', 'article', 'event',
                   'schoolvalue', 'department', 'staffmember', 'subject', 'schoolstatistic'),
        'summary': 'Manages the public website and school content.',
        'powers': (
            'Create, edit, publish, schedule and delete news, events and School Life stories, poems and articles.',
            'Manage reusable student authors and grades, departments, staff profiles and management roles, subjects, school values and statistics.',
            'Upload content images and update Site Settings, including page content, contact details, Facebook, admissions information and the additional privacy notice.',
        ),
        'limits': 'Cannot read private applications or contact messages, manage staff accounts, or access Django administration.',
    },
    {
        'name': 'Admissions officers',
        'label': 'School office — admissions and messages',
        'icon': 'mail',
        'models': ('application', 'contactmessage'),
        'summary': 'Handles private admissions records and enquiries.',
        'powers': (
            'View and search applications, update their review status and add private staff notes.',
            'View and search contact messages, update their status and add private staff notes.',
            'Permanently delete applications and contact messages when authorised under the school’s recordkeeping policy.',
        ),
        'limits': 'Cannot edit or publish website content, change Site Settings, manage staff accounts, or access Django administration.',
    },
)
STAFF_ROLE_CHOICES = tuple((role['name'], role['label']) for role in STAFF_ROLES) + (
    ('both', 'Content editor and school office'),
)

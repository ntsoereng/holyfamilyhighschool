from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from school.roles import STAFF_ROLES

class Command(BaseCommand):
    help = 'Create least-privilege content editor and admissions officer groups.'
    def handle(self, *args, **options):
        for role in STAFF_ROLES:
            group, _ = Group.objects.get_or_create(name=role['name'])
            group.permissions.set(Permission.objects.filter(
                content_type__app_label='school', content_type__model__in=role['models'],
                codename__in=[f'{action}_{model}' for model in role['models']
                              for action in ('view', 'add', 'change', 'delete')]))
        self.stdout.write(self.style.SUCCESS('Staff groups ready. Create staff accounts through /staff/team/ as a website administrator.'))

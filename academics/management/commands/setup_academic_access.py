from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create the Reporting administrators group. Grant it only to authorised active staff users.'

    def handle(self, **options):
        group, _ = Group.objects.get_or_create(name='Reporting administrators')
        group.permissions.add(Permission.objects.get(content_type__app_label='academics', codename='manage_academics'))
        self.stdout.write(self.style.SUCCESS('Reporting administrators group ready. Assign it to authorised staff via Django administration. Teachers and families need only portal accounts.'))

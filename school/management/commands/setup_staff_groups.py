from django.core.management.base import BaseCommand
from school.roles import ensure_staff_groups


class Command(BaseCommand):
    help = 'Create and synchronise standard content editor and school office groups.'

    def handle(self, *args, **options):
        ensure_staff_groups(synchronise=True)
        self.stdout.write(self.style.SUCCESS('Staff groups ready. Create staff accounts through /staff/team/ as a website administrator.'))

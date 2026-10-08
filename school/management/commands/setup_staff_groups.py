from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Create least-privilege content editor and admissions officer groups.'
    def handle(self, *args, **options):
        for name, models in [('Content editors', ['sitesettings','article','event','schoolvalue','department','staffmember','subject','schoolstatistic']),
                             ('Admissions officers', ['application', 'contactmessage'])]:
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.filter(content_type__app_label='school', content_type__model__in=models))
        self.stdout.write(self.style.SUCCESS('Staff groups ready. Create staff accounts through /staff/team/ as a website administrator.'))

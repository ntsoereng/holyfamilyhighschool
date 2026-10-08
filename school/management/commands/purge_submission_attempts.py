from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from school.models import SubmissionAttempt

class Command(BaseCommand):
    help = 'Delete expired admission throttle records. Run daily.'
    def handle(self, *args, **options):
        count, _ = SubmissionAttempt.objects.filter(created_at__lt=timezone.now()-timedelta(days=1)).delete()
        self.stdout.write(f'Deleted {count} expired records.')

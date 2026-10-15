from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from school.models import SubmissionAttempt, SubmissionThrottle

class Command(BaseCommand):
    help = 'Delete expired submission counters and old attempt records. Run daily.'
    def handle(self, *args, **options):
        count, _ = SubmissionAttempt.objects.filter(created_at__lt=timezone.now()-timedelta(days=1)).delete()
        removed, _ = SubmissionThrottle.objects.filter(expires_at__lt=timezone.now()-timedelta(days=1)).delete()
        count += removed
        self.stdout.write(f'Deleted {count} expired records.')

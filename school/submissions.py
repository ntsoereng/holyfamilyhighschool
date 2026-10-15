"""Shared, database-backed submission limits and canonical applicant identity."""
from datetime import timedelta
import hashlib
import ipaddress
import json
import math
import unicodedata

from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac


def normalize_text(value, multiline=False):
    value = unicodedata.normalize('NFKC', value or '')
    if not multiline:
        value = ' '.join(value.split())
    # Preserve line breaks in messages/addresses, never invisible/control characters.
    value = ''.join(char for char in value if not unicodedata.category(char).startswith('C')
                    or (multiline and char in '\n\r\t'))
    if multiline:
        return '\n'.join(' '.join(line.split()) for line in value.splitlines()).strip()
    return ' '.join(value.split())


def normalize_name(value):
    return normalize_text(value).replace('’', "'").replace('‐', '-').replace('‑', '-').title()


def application_identity(given_name, surname, dob, year, grade):
    if not all((given_name, surname, dob, year, grade)):
        return None  # Incomplete historical records are retained without guessing identity.
    parts = [normalize_name(given_name).casefold(), normalize_name(surname).casefold(),
             dob.isoformat(), int(year), normalize_text(grade).casefold()]
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def rate_subject(address):
    try:
        ip = ipaddress.ip_address(address)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            return str(ip.ipv4_mapped)
        if isinstance(ip, ipaddress.IPv6Address):
            # One IPv6 /64 gets one allowance, not one allowance per temporary address.
            return str(ipaddress.ip_network(f'{ip}/64', strict=False))
        return str(ip)
    except ValueError:
        return 'unknown'


def consume_limit(subject, scope, limit, seconds, now=None):
    """Atomic conditional SQL increment; shared across processes and hosts.

    A stable unique key bounds storage to one counter per subject/scope/window.
    Denied traffic neither extends the window nor grows an attempt log.
    """
    from .models import SubmissionThrottle
    now = now or timezone.now()
    key = salted_hmac('submission-throttle-v1', f'{scope}:{seconds}:{subject}', algorithm='sha256').hexdigest()
    row, _ = SubmissionThrottle.objects.get_or_create(key=key, defaults={
        'expires_at': now + timedelta(seconds=seconds), 'count': 0})
    SubmissionThrottle.objects.filter(pk=row.pk, expires_at__lte=now).update(
        count=0, expires_at=now + timedelta(seconds=seconds))
    accepted = SubmissionThrottle.objects.filter(pk=row.pk, expires_at__gt=now, count__lt=limit).update(count=F('count') + 1)
    if accepted:
        return 0
    expires_at = SubmissionThrottle.objects.values_list('expires_at', flat=True).get(pk=row.pk)
    return max(1, math.ceil((expires_at - now).total_seconds()))

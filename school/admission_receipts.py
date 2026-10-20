"""Bounded, browser-bound PRG receipts containing references, not student details."""
import re
import secrets
import time

from django.http import HttpResponseRedirect
from django.urls import reverse

from .admission_results import SELECTION_MAX_AGE

SESSION_KEY = 'admission_lookup_receipts'
MAX_RECEIPTS = 10


def redirect_to_receipt(request, state):
    now = int(time.time())
    receipts = request.session.get(SESSION_KEY, {})
    receipts = {key: value for key, value in receipts.items() if value['expires_at'] > now}
    receipts = dict(list(receipts.items())[-(MAX_RECEIPTS - 1):])
    reference = secrets.token_urlsafe(24)
    receipts[reference] = {**state, 'expires_at': now + SELECTION_MAX_AGE}
    request.session[SESSION_KEY] = receipts
    # 303 explicitly turns the following browser navigation into a GET.
    return HttpResponseRedirect(reverse('admission-results') + '?r=' + reference, status=303)


def read_receipt(request, reference):
    if not re.fullmatch(r'[A-Za-z0-9_-]{32}', reference):
        return None
    now = int(time.time())
    receipts = request.session.get(SESSION_KEY, {})
    current = {key: value for key, value in receipts.items() if value['expires_at'] > now}
    if len(current) != len(receipts):
        request.session[SESSION_KEY] = current
    return current.get(reference)

"""Bulk staff workflow, bounded admitted-student search and boarding details."""
import csv
import uuid

from django.contrib import messages
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.core.exceptions import PermissionDenied
from django.core import signing
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_safe

from .admission_results import (HEADERS, MAX_MATCHES, SELECTION_MAX_AGE, SELECTION_SALT,
    SelectionForm, ImportForm, LookupForm, ReleaseActionForm, selection_token)
from .models import AdmissionRelease, AdmissionResult
from .staff import audit, require_permission, staff_required
from .submissions import consume_limit


@never_cache
@require_safe
@staff_required
def import_template(request):
    require_permission(request, AdmissionRelease, 'view')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="HFHS-admission-results-template.csv"'
    csv.writer(response).writerow(HEADERS)
    return response


@never_cache
@sensitive_post_parameters()
@sensitive_variables()
@require_http_methods(['GET', 'HEAD', 'POST'])
def lookup(request):
    selecting = request.method == 'POST' and request.POST.get('action') == 'view'
    form = LookupForm(request.POST if request.method == 'POST' and not selecting else None)
    outcome = None
    candidates = []
    selected = None
    release = AdmissionRelease.objects.filter(published=True).order_by('-year').first()
    year = release.year if release else None
    status = 200
    retry = 0
    if selecting:
        selection_form = SelectionForm(request.POST)
        outcome = 'no-match'
        if selection_form.is_valid() and release:
            try:
                selection = signing.loads(selection_form.cleaned_data['selection'],
                    salt=SELECTION_SALT, max_age=SELECTION_MAX_AGE)
                result = AdmissionResult.objects.select_related('release').filter(
                    pk=selection['result'], release__year=selection['year'],
                    release_id=release.pk,
                    release__revision=selection['revision'], release__published=True).first()
            except (signing.BadSignature, KeyError, TypeError, ValueError):
                result = None
            if result and result.surname and result.first_names and result.primary_school:
                retry = consume_limit(result.identity_key, 'admission-identity', settings.ADMISSION_DETAIL_RATE_PER_DAY, 86400)
                if not retry:
                    year = result.release.year
                    selected = result
                    outcome = 'boarding' if result.boarding else 'day'
    elif request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        # The same search shares an allowance across changing network addresses.
        key = salted_hmac('admission-search-v1',
            f'{year}:{data["surname"].casefold()}:{data["first_names"].casefold()}', algorithm='sha256').hexdigest()
        retry = consume_limit(key, 'admission-search', settings.ADMISSION_SEARCH_RATE_PER_DAY, 86400)
        if not retry:
            results = AdmissionResult.objects.select_related('release').filter(
                release_id=release.pk if release else None, release__published=True, surname__icontains=data['surname'],
                first_names__icontains=data['first_names']).exclude(surname='').exclude(first_names='').exclude(primary_school='')
            results = list(results.order_by('surname', 'first_names', 'pk')[:MAX_MATCHES + 1])
            outcome = 'no-match'
            if len(results) > MAX_MATCHES:
                outcome = 'too-many'
            elif results:
                outcome = 'matches'
                candidates = [{'surname': result.surname, 'first_names': result.first_names,
                               'primary_school': result.primary_school,
                               'selection': selection_token(result)} for result in results]
            # Do not keep searched names in the returned page, session or URL.
            form = LookupForm()
    if retry:
        status = 429
        outcome = 'limited'
    response = render(request, 'school/admission_results.html', {
        'form': form, 'outcome': outcome, 'candidates': candidates, 'selected': selected, 'result_year': year}, status=status)
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    if retry:
        response['Retry-After'] = str(retry)
    return response


@never_cache
@sensitive_post_parameters()
@sensitive_variables()
@require_http_methods(['GET', 'HEAD', 'POST'])
@staff_required
def manage(request):
    require_permission(request, AdmissionRelease, 'view')
    form = ImportForm()
    status = 200
    action_error = ''
    if request.method == 'POST':
        if request.POST.get('action') == 'upload':
            # Replacement is a bulk change, not permission to edit individual pupils.
            for action in ('add', 'change', 'delete'):
                require_permission(request, AdmissionRelease, action)
            form = ImportForm(request.POST, request.FILES)
            if form.is_valid():
                data = form.cleaned_data
                with transaction.atomic():
                    release, created = AdmissionRelease.objects.select_for_update().get_or_create(year=data['year'])
                    release.results.all().delete()
                    AdmissionResult.objects.bulk_create([
                        AdmissionResult(release=release, **row) for row in data['rows']
                    ], batch_size=500)
                    release.published = False
                    release.revision = uuid.uuid4()
                    release.save()
                    audit(request, release, ADDITION if created else CHANGE,
                          f'Imported {len(data["rows"])} admission results as unpublished.')
                messages.success(request, f'{release.year}: {len(data["rows"])} students imported privately. Review the totals below, then publish when ready.')
                return redirect('staff-admission-results')
            status = 400
        else:
            action_form = ReleaseActionForm(request.POST)
            if not action_form.is_valid():
                action_error = 'Choose a valid year and action from the results below.'
                status = 400
            else:
                data = action_form.cleaned_data
                require_permission(request, AdmissionRelease, 'delete' if data['action'] == 'delete' else 'change')
                with transaction.atomic():
                    release = get_object_or_404(AdmissionRelease.objects.select_for_update(), year=data['year'])
                    if release.revision != data['revision']:
                        action_error = 'These results changed after you opened the page. Review the updated totals before trying again.'
                        status = 409
                    else:
                        if data['action'] == 'delete':
                            audit(request, release, DELETION, 'Deleted admission results for this year.')
                            release.delete()
                            messages.success(request, f'{data["year"]} results have been deleted.')
                        else:
                            release.published = data['action'] == 'publish'
                            if release.published and not release.results.exists():
                                raise PermissionDenied('An empty admission list cannot be published.')
                            release.revision = uuid.uuid4()
                            release.save()
                            audit(request, release, CHANGE, 'Published admission results.' if release.published else 'Withdrew admission results.')
                            messages.success(request, f'{release.year} results are now {"available for individual lookup" if release.published else "hidden"}.')
                        return redirect('staff-admission-results')
    releases = AdmissionRelease.objects.annotate(student_count=Count('results'),
        boarding_count=Count('results', filter=Q(results__boarding=True)),
        legacy_count=Count('results', filter=Q(results__surname='') | Q(results__first_names='') | Q(results__primary_school='')))
    return render(request, 'staff/admission_results.html', {
        'form': form, 'releases': releases, 'action_error': action_error}, status=status)

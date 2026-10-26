import uuid

from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from .models import Prospectus, ProspectusPage
from .prospectus_forms import ProspectusUploadForm, ProspectusActionForm
from .staff import audit, require_permission, staff_required


def current_prospectus():
    return Prospectus.objects.defer('pdf').filter(pk=1).first()


@never_cache
@require_safe
def prospectus(request):
    document = current_prospectus()
    available = document and document.published and document.page_count > 0
    # The page queryset is evaluated while rendering. Recheck the revision and
    # publication then too, so a concurrent replacement cannot expose draft text.
    pages = document.pages.filter(prospectus__published=True,
        prospectus__revision=document.revision).defer('image') if available else []
    return render(request, 'school/prospectus.html', {'document': document if available else None, 'pages': pages})


@never_cache
@require_safe
def page_image(request, revision, number):
    page = get_object_or_404(ProspectusPage.objects.only('image'), prospectus_id=1,
        prospectus__revision=revision, prospectus__published=True, number=number)
    return HttpResponse(bytes(page.image), content_type='image/jpeg')


@never_cache
@require_safe
def download(request, revision):
    document = get_object_or_404(Prospectus.objects.only('pdf'), pk=1, revision=revision, published=True, page_count__gt=0)
    # The PDF is already in memory (and bounded to 8 MB). FileResponse would
    # hand BytesIO to WSGI file wrappers that may require a real file descriptor.
    response = HttpResponse(bytes(document.pdf), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Holy-Family-High-School-prospectus.pdf"'
    response['Content-Length'] = len(response.content)
    return response


@never_cache
@require_safe
@staff_required
def preview_image(request, revision, number):
    require_permission(request, Prospectus, 'view')
    page = get_object_or_404(ProspectusPage.objects.only('image'), prospectus_id=1,
        prospectus__revision=revision, number=number)
    return HttpResponse(bytes(page.image), content_type='image/jpeg')


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
@staff_required
def manage(request):
    require_permission(request, Prospectus, 'view')
    document = current_prospectus()
    form = ProspectusUploadForm()
    action_error = ''
    status = 200
    if request.method == 'POST':
        if request.POST.get('action') == 'upload':
            for action in ('add', 'change', 'delete'):
                require_permission(request, Prospectus, action)
            form = ProspectusUploadForm(request.POST, request.FILES)
            if form.is_valid():
                prepared = form.cleaned_data['pdf']
                with transaction.atomic():
                    document, created = Prospectus.objects.select_for_update().get_or_create(pk=1)
                    document.pages.all().delete()
                    document.pdf = prepared['pdf']
                    document.page_count = len(prepared['pages'])
                    document.published = False
                    document.revision = uuid.uuid4()
                    document.save()
                    ProspectusPage.objects.bulk_create([
                        ProspectusPage(prospectus=document, **page) for page in prepared['pages']
                    ], batch_size=1)
                    audit(request, document, ADDITION if created else CHANGE,
                          f'Uploaded {document.page_count} prospectus pages as unpublished.')
                messages.success(request, 'Prospectus uploaded privately. Review the pages, then publish when ready.')
                return redirect('staff-prospectus')
            status = 400
        else:
            action_form = ProspectusActionForm(request.POST)
            if not action_form.is_valid():
                action_error, status = 'Choose an action for the current prospectus.', 400
            else:
                data = action_form.cleaned_data
                require_permission(request, Prospectus, 'delete' if data['action'] == 'delete' else 'change')
                with transaction.atomic():
                    document = get_object_or_404(Prospectus.objects.select_for_update().defer('pdf'), pk=1)
                    if document.revision != data['revision']:
                        action_error, status = 'The prospectus changed. Review the latest upload before trying again.', 409
                    else:
                        if data['action'] == 'delete':
                            audit(request, document, DELETION, 'Deleted the prospectus.')
                            document.delete()
                            messages.success(request, 'Prospectus deleted.')
                        else:
                            if data['action'] == 'publish' and (not document.page_count or not document.pages.exists()):
                                raise PermissionDenied('Upload a prospectus before publishing.')
                            document.published = data['action'] == 'publish'
                            document.revision = uuid.uuid4()
                            document.save(update_fields=['published', 'revision', 'updated_at'])
                            audit(request, document, CHANGE, 'Published prospectus.' if document.published else 'Withdrew prospectus.')
                            messages.success(request, 'Prospectus published.' if document.published else 'Prospectus withdrawn. Viewing and downloading are now disabled.')
                        return redirect('staff-prospectus')
    pages = document.pages.defer('image', 'text') if document else []
    return render(request, 'staff/prospectus.html', {
        'document': document, 'pages': pages, 'form': form, 'action_error': action_error}, status=status)

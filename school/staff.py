from functools import wraps
from django.contrib import messages
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from .models import Article, Event, SchoolValue, SiteSettings, Application, ContactMessage, Department, StaffMember, Subject, SchoolStatistic
from .staff_forms import (StaffAuthenticationForm, ArticleForm, EventForm, ValueForm,
                          SettingsForm, ApplicationReviewForm, StaffUserCreationForm, ContactReviewForm, DepartmentForm, StaffMemberForm, SubjectForm, StatisticForm)

# Fixed registry: URL input can never choose arbitrary models, forms or permissions.
CONTENT = {
    'departments': (Department, DepartmentForm, 'Departments', 'department'),
    'staff-profiles': (StaffMember, StaffMemberForm, 'Staff profiles', 'staff profile'),
    'subjects': (Subject, SubjectForm, 'Subjects', 'subject'),
    'statistics': (SchoolStatistic, StatisticForm, 'School statistics', 'statistic'),
    'articles': (Article, ArticleForm, 'News & articles', 'article'),
    'events': (Event, EventForm, 'Events', 'event'),
    'values': (SchoolValue, ValueForm, 'School values', 'value'),
}


def staff_required(view):
    @wraps(view)
    @login_required(login_url='staff-login')
    def guarded(request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return guarded


def require_permission(request, model, action):
    if not request.user.has_perm(f'{model._meta.app_label}.{action}_{model._meta.model_name}'):
        raise PermissionDenied


def audit(request, obj, action, message):
    LogEntry.objects.log_actions(user_id=request.user.pk, queryset=[obj], action_flag=action, change_message=message)


class StaffLoginView(LoginView):
    template_name = 'staff/login.html'
    authentication_form = StaffAuthenticationForm
    redirect_authenticated_user = False
    def get_success_url(self):
        return self.get_redirect_url() or reverse('staff-home')


@require_POST
@staff_required
def sign_out(request):
    logout(request)
    return redirect('staff-login')


@staff_required
def dashboard(request):
    sections = []
    for key, (model, form, title, singular) in CONTENT.items():
        if request.user.has_perm(f'school.view_{model._meta.model_name}'):
            sections.append({'title': title, 'count': model.objects.count(), 'url': reverse('staff-list', args=[key])})
    can_admissions = request.user.has_perm('school.view_application')
    recent = Application.objects.all()[:5] if can_admissions else []
    readable_types = [ContentType.objects.get_for_model(model).pk for model in
                      [Article, Event, SchoolValue, SiteSettings, Application, ContactMessage, Department, StaffMember, Subject, SchoolStatistic]
                      if request.user.has_perm(f'school.view_{model._meta.model_name}')]
    if request.user.is_superuser:
        readable_types.append(ContentType.objects.get_for_model(User).pk)
    return render(request, 'staff/home.html', {'sections': sections, 'recent_applications': recent,
        'application_count': Application.objects.filter(status='new').count() if can_admissions else None,
        'message_count': ContactMessage.objects.filter(status='new').count() if request.user.has_perm('school.view_contactmessage') else None,
        'recent_changes': LogEntry.objects.filter(user_id=request.user.pk, content_type_id__in=readable_types).select_related('content_type')[:6]})


def content_config(section):
    if section not in CONTENT:
        raise Http404
    return CONTENT[section]


@staff_required
def content_list(request, section):
    model, form, title, singular = content_config(section)
    require_permission(request, model, 'view')
    query = request.GET.get('q', '').strip()[:200]
    records = model.objects.all()
    if section == 'staff-profiles':
        records = records.prefetch_related('departments')
    if query:
        records = records.filter(title__icontains=query)
    state = request.GET.get('state', '')
    if section != 'values' and state in ['published', 'draft']:
        records = records.filter(published=state == 'published')
    rows = Paginator(records, 20).get_page(request.GET.get('page'))
    return render(request, 'staff/list.html', {'items': rows, 'section': section, 'title': title,
        'singular': singular, 'query': query, 'state': state, 'has_publishing': section != 'values',
        'can_add': request.user.has_perm(f'school.add_{model._meta.model_name}'),
        'can_change': request.user.has_perm(f'school.change_{model._meta.model_name}')})


@require_http_methods(['GET', 'POST'])
@staff_required
def content_edit(request, section, pk=None):
    model, form_class, title, singular = content_config(section)
    require_permission(request, model, 'change' if pk else 'add')
    obj = get_object_or_404(model, pk=pk) if pk else None
    form = form_class(request.POST if request.method == 'POST' else None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            record = form.save()
            audit(request, record, CHANGE if pk else ADDITION, f'{singular.title()} saved in staff workspace.')
        messages.success(request, f'{singular.title()} saved.')
        return redirect('staff-edit', section=section, pk=record.pk)
    preview = None
    if obj and getattr(obj, 'published', False):
        if section == 'articles' and obj.published_at <= timezone.now():
            preview = reverse('article', args=[obj.slug])
        elif section == 'subjects':
            preview = reverse('subject', args=[obj.slug])
        elif section == 'departments':
            preview = reverse('school-department', args=[obj.pk])
        elif section == 'staff-profiles':
            if obj.departments.filter(published=True).exists() or not obj.departments.exists():
                preview = reverse('school-staff-profile', args=[obj.pk])
        elif section == 'statistics' and obj.show_on_homepage:
            preview = reverse('home')
        elif section == 'events':
            preview = reverse('event', args=[obj.slug])
    return render(request, 'staff/edit.html', {'form': form, 'title': f'Edit {singular}' if pk else f'New {singular}',
        'back_url': reverse('staff-list', args=[section]), 'section': section, 'record': obj, 'preview_url': preview,
        'delete_url': reverse('staff-delete', args=[section, pk]) if pk and request.user.has_perm(f'school.delete_{model._meta.model_name}') else None})


@require_http_methods(['GET', 'POST'])
@staff_required
def content_delete(request, section, pk):
    model, form, title, singular = content_config(section)
    require_permission(request, model, 'delete')
    obj = get_object_or_404(model, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            audit(request, obj, DELETION, f'{singular.title()} deleted in staff workspace.')
            obj.delete()
        messages.success(request, f'{singular.title()} deleted.')
        return redirect('staff-list', section=section)
    return render(request, 'staff/delete.html', {'record': obj, 'section': section})


@require_http_methods(['GET', 'POST'])
@staff_required
def school_settings(request):
    require_permission(request, SiteSettings, 'change')
    obj = SiteSettings.objects.first() or SiteSettings(pk=1)
    form = SettingsForm(request.POST if request.method == 'POST' else None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            record = form.save()
            audit(request, record, CHANGE, 'School settings updated in staff workspace.')
        messages.success(request, 'School settings saved. Your website is up to date.')
        return redirect('staff-settings')
    return render(request, 'staff/edit.html', {'form': form, 'title': 'School settings', 'back_url': reverse('staff-home'),
                                            'settings_editor': True})


@staff_required
def applications(request):
    require_permission(request, Application, 'view')
    records = Application.objects.all()
    query = request.GET.get('q', '').strip()[:200]
    if query:
        records = records.filter(Q(learner_name__icontains=query) | Q(guardian_name__icontains=query)
            | Q(phone__icontains=query) | Q(email__icontains=query) | Q(current_school__icontains=query)
            | Q(reference__icontains=query))
    state = request.GET.get('state', '')
    if state in dict(Application._meta.get_field('status').choices):
        records = records.filter(status=state)
    return render(request, 'staff/applications.html', {'items': Paginator(records, 20).get_page(request.GET.get('page')),
        'query': query, 'state': state, 'statuses': Application._meta.get_field('status').choices})


@require_http_methods(['GET', 'POST'])
@staff_required
def application_detail(request, pk):
    require_permission(request, Application, 'view')
    if request.method == 'POST':
        require_permission(request, Application, 'change')
    record = get_object_or_404(Application, pk=pk)
    form = ApplicationReviewForm(request.POST if request.method == 'POST' else None, instance=record)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            obj = form.save()
            audit(request, obj, CHANGE, 'Application review updated in staff workspace.')
        messages.success(request, 'Application review saved.')
        return redirect('staff-application', pk=record.pk)
    return render(request, 'staff/application.html', {'record': record, 'form': form,
        'can_change': request.user.has_perm('school.change_application'),
        'can_delete': request.user.has_perm('school.delete_application')})


@require_http_methods(['GET', 'POST'])
@staff_required
def application_delete(request, pk):
    require_permission(request, Application, 'view')
    require_permission(request, Application, 'delete')
    record = get_object_or_404(Application, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            # Do not retain applicant names in deletion history.
            LogEntry.objects.create(user=request.user, content_type=ContentType.objects.get_for_model(Application),
                object_id=str(record.pk), object_repr='Deleted application', action_flag=DELETION,
                change_message='Application permanently removed in staff workspace.')
            record.delete()
        messages.success(request, 'Application deleted.')
        return redirect('staff-applications')
    return render(request, 'staff/delete.html', {'record': record, 'application_delete': True})


@require_http_methods(['GET', 'POST'])
@staff_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Your password has been changed.')
        return redirect('staff-home')
    return render(request, 'staff/edit.html', {'form': form, 'title': 'Change password', 'back_url': reverse('staff-home')})


@require_http_methods(['GET', 'POST'])
@staff_required
def team(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    form = StaffUserCreationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            audit(request, user, ADDITION, 'Staff account created in staff workspace.')
        messages.success(request, 'Staff account created. Share the credentials securely with the staff member.')
        return redirect('staff-team')
    return render(request, 'staff/team.html', {'form': form, 'staff_members': User.objects.filter(is_staff=True).prefetch_related('groups')})


@require_POST
@staff_required
def toggle_staff(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    user = get_object_or_404(User, pk=pk, is_staff=True)
    if user.is_superuser or user.pk == request.user.pk:
        raise PermissionDenied
    with transaction.atomic():
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        audit(request, user, CHANGE, 'Staff account enabled.' if user.is_active else 'Staff account disabled.')
    messages.success(request, 'Staff access updated.')
    return redirect('staff-team')


@staff_required
def contact_messages(request):
    require_permission(request, ContactMessage, 'view')
    records = ContactMessage.objects.all()
    query = request.GET.get('q', '').strip()[:200]
    state = request.GET.get('state', '')
    if query:
        records = records.filter(Q(name__icontains=query) | Q(email__icontains=query) | Q(subject__icontains=query))
    if state in dict(ContactMessage._meta.get_field('status').choices):
        records = records.filter(status=state)
    return render(request, 'staff/messages.html', {'items': Paginator(records, 20).get_page(request.GET.get('page')),
        'query': query, 'state': state, 'statuses': ContactMessage._meta.get_field('status').choices})


@require_http_methods(['GET', 'POST'])
@staff_required
def contact_message(request, pk):
    require_permission(request, ContactMessage, 'view')
    if request.method == 'POST':
        require_permission(request, ContactMessage, 'change')
    record = get_object_or_404(ContactMessage, pk=pk)
    form = ContactReviewForm(request.POST if request.method == 'POST' else None, instance=record)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            obj = form.save()
            audit(request, obj, CHANGE, 'Contact message review updated.')
        messages.success(request, 'Message review saved.')
        return redirect('staff-message', pk=record.pk)
    return render(request, 'staff/message.html', {'record': record, 'form': form})


@require_http_methods(['GET', 'POST'])
@staff_required
def contact_message_delete(request, pk):
    require_permission(request, ContactMessage, 'view')
    require_permission(request, ContactMessage, 'delete')
    record = get_object_or_404(ContactMessage, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            LogEntry.objects.create(user=request.user, content_type=ContentType.objects.get_for_model(ContactMessage),
                object_id=str(record.pk), object_repr='Deleted contact message', action_flag=DELETION,
                change_message='Contact message permanently removed.')
            record.delete()
        messages.success(request, 'Message deleted.')
        return redirect('staff-messages')
    return render(request, 'staff/message_delete.html', {'record': record})


@require_POST
@staff_required
def editor_image_upload(request):
    from io import BytesIO
    from uuid import uuid4
    from PIL import Image, ImageOps
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.core.exceptions import ValidationError
    from django.http import JsonResponse
    from .security import validate_image
    if not any(request.user.has_perm(f'school.{action}_{model}') for action in ['add', 'change'] for model in ['article', 'event', 'page', 'subject']):
        raise PermissionDenied
    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'error': 'Choose an image to upload.'}, status=400)
    try:
        validate_image(upload)
        image = ImageOps.exif_transpose(Image.open(upload))
        image.thumbnail((2400, 2400))
        output = BytesIO()
        image.convert('RGB').save(output, format='JPEG', quality=88)
        name = default_storage.save(f'editor/{uuid4().hex}.jpg', ContentFile(output.getvalue()))
    except (ValidationError, OSError, ValueError) as exc:
        return JsonResponse({'error': 'Upload a valid JPEG, PNG or WebP image under 5 MB.'}, status=400)
    return JsonResponse({'location': default_storage.url(name)})

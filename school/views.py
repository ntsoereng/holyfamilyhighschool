from django.conf import settings
from datetime import timedelta
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_http_methods
from .models import SiteSettings, Article, Event, SchoolValue, SubmissionAttempt, Department, StaffMember, Subject, SchoolStatistic
from .forms import ApplicationForm, ContactForm
from django.contrib import messages
from .security import client_ip
from .calendar import build_calendar_context


def home(request):
    return render(request, 'school/home.html', {
        'articles': Article.objects.live()[:3],
        'events': Event.objects.filter(published=True, starts_at__gte=timezone.now())[:3],
        'values': SchoolValue.objects.all(),
        'statistics': SchoolStatistic.objects.filter(published=True, show_on_homepage=True),
    })


def about(request):
    return render(request, 'school/about.html', {
        'values': SchoolValue.objects.all(),
        'statistics': SchoolStatistic.objects.filter(published=True, show_on_school_pages=True),
    })


def curriculum(request):
    return render(request, 'school/curriculum.html', {'subjects': Subject.objects.filter(published=True)})


def staff_directory(request):
    departments = Department.objects.filter(published=True).annotate(
        public_member_count=Count('members', filter=Q(members__published=True), distinct=True))
    return render(request, 'school/staff_directory.html', {
        'departments': departments,
        'other_staff': StaffMember.objects.filter(published=True, departments__isnull=True),
    })

def department_detail(request, pk):
    department = get_object_or_404(Department, pk=pk, published=True)
    return render(request, 'school/department_detail.html', {
        'department': department,
        'members': department.members.filter(published=True),
    })

def staff_profile(request, pk):
    public_members = StaffMember.objects.filter(published=True).filter(
        Q(departments__published=True) | Q(departments__isnull=True)).distinct()
    member = get_object_or_404(public_members, pk=pk)
    return render(request, 'school/staff_profile.html', {
        'member': member,
        'departments': member.departments.filter(published=True),
    })

def news(request):
    items = Paginator(Article.objects.live(), 9).get_page(request.GET.get('page'))
    return render(request, 'school/news.html', {'items': items})

def article(request, slug):
    item = get_object_or_404(Article.objects.live(), slug=slug)
    return render(request, 'school/detail.html', {'item': item, 'body': item.body, 'introduction': item.excerpt, 'kind': 'News & stories'})

def events(request):
    return render(request, 'school/events.html', build_calendar_context(request.GET))

def event(request, slug):
    item = get_object_or_404(Event, published=True, slug=slug)
    return render(request, 'school/detail.html', {'item': item, 'body': item.description, 'introduction': '', 'kind': 'School calendar'})

def page(request, slug):
    # Existing core URLs remain valid; arbitrary database pages are no longer public.
    from django.http import Http404
    fixed_views = {'about': about, 'about-us': about, 'curriculum': curriculum,
                   'our-staff': staff_directory, 'staff': staff_directory}
    if slug not in fixed_views:
        raise Http404
    return fixed_views[slug](request)


def subject(request, slug):
    item = get_object_or_404(Subject, slug=slug, published=True)
    return render(request, 'school/detail.html', {'item': item, 'body': item.body,
        'introduction': item.introduction, 'kind': 'Curriculum',
        'is_subject': True})

@require_http_methods(['GET', 'POST'])
def contact(request):
    form = ContactForm(request.POST if request.method == 'POST' else None)
    rate_limited = False
    if request.method == 'POST':
        ip_hash = salted_hmac('contact-message-ip', client_ip(request)).hexdigest()
        cutoff = timezone.now() - timedelta(hours=1)
        if SubmissionAttempt.objects.filter(ip_hash=ip_hash, created_at__gte=cutoff).count() >= 5:
            rate_limited = True
        else:
            SubmissionAttempt.objects.create(ip_hash=ip_hash)
            if form.is_valid():
                form.save()
                messages.success(request, 'Your message has been received. The school office will respond using the contact details you provided.')
                return redirect('contact')
    return render(request, 'school/contact.html', {'form': form, 'rate_limited': rate_limited}, status=429 if rate_limited else 200)
def privacy(request): return render(request, 'school/privacy.html')

@require_http_methods(['GET','POST'])
def apply(request):
    school = SiteSettings.objects.first() or SiteSettings(email=settings.CONTACT_EMAIL, phone=settings.CONTACT_PHONE)
    form = ApplicationForm(request.POST if request.method == 'POST' else None, school=school)
    if request.method == 'POST' and school.admissions_open:
        ip_hash = salted_hmac('admissions-ip', client_ip(request)).hexdigest()
        cutoff = timezone.now() - timedelta(hours=1)
        if SubmissionAttempt.objects.filter(ip_hash=ip_hash, created_at__gte=cutoff).count() >= 5:
            return render(request, 'school/apply.html', {'form': form, 'rate_limited': True}, status=429)
        SubmissionAttempt.objects.create(ip_hash=ip_hash)
        if form.is_valid():
            application = form.save()
            request.session['application_receipt'] = str(application.reference)
            return redirect('application-success')
    return render(request, 'school/apply.html', {'form': form})

def application_success(request):
    reference = request.session.pop('application_receipt', None)
    if not reference: return redirect('apply')
    return render(request, 'school/success.html', {'reference': reference})

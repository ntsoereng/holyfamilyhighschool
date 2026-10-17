from django.conf import settings
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.urls import reverse
from .navigation import writing_return_url
from django.views.decorators.http import require_http_methods, require_safe
from .models import Announcement, Project, SiteSettings, Article, Event, SchoolValue, Application, Department, StaffMember, Subject, SchoolStatistic, SchoolLifePost
from .forms import ApplicationForm, ContactForm
from django.contrib import messages
from .calendar import build_calendar_context


@require_safe
def home(request):
    return render(request, 'school/home.html', {
        'articles': Article.objects.live()[:3],
        'announcements': Announcement.objects.live()[:3],
        'projects': Project.objects.live()[:3],
        'events': Event.objects.filter(published=True, starts_at__gte=timezone.now())[:3],
        'values': SchoolValue.objects.all(),
        'statistics': SchoolStatistic.objects.filter(published=True, show_on_homepage=True),
    })


@require_safe
def about(request):
    return render(request, 'school/about.html', {
        'values': SchoolValue.objects.all(),
        'statistics': SchoolStatistic.objects.filter(published=True, show_on_school_pages=True),
    })


@require_safe
def curriculum(request):
    return render(request, 'school/curriculum.html', {'subjects': Subject.objects.filter(published=True)})


@require_safe
def staff_directory(request):
    departments = Department.objects.filter(published=True).annotate(
        public_member_count=Count('members', filter=Q(members__published=True), distinct=True))
    return render(request, 'school/staff_directory.html', {
        'departments': departments,
        'management': StaffMember.objects.filter(published=True, is_management=True),
        'other_staff': StaffMember.objects.filter(published=True, is_management=False, departments__isnull=True),
    })

@require_safe
def department_detail(request, pk):
    department = get_object_or_404(Department, pk=pk, published=True)
    return render(request, 'school/department_detail.html', {
        'department': department,
        'members': department.members.filter(published=True),
        'back_url': reverse('school-staff'), 'back_label': 'Back to staff',
    })

@require_safe
def staff_profile(request, slug=None, pk=None):
    public_members = StaffMember.objects.filter(published=True).filter(
        Q(is_management=True) | Q(departments__published=True) | Q(departments__isnull=True)).distinct()
    member = get_object_or_404(public_members, **({'pk': pk} if pk is not None else {'slug': slug}))
    if pk is not None:
        return redirect('school-staff-profile', slug=member.slug, permanent=True)
    return render(request, 'school/staff_profile.html', {
        'member': member,
        'departments': member.departments.filter(published=True),
        'back_url': reverse('school-staff'), 'back_label': 'Back to staff',
    })

@require_safe
def news(request):
    items = Paginator(Article.objects.live(), 9).get_page(request.GET.get('page'))
    return render(request, 'school/news.html', {'items': items})

@require_safe
def article(request, slug):
    item = get_object_or_404(Article.objects.live(), slug=slug)
    return render(request, 'school/detail.html', {'item': item, 'body': item.body, 'introduction': item.excerpt, 'kind': 'News',
        'back_url': writing_return_url(request, 'news', Article.objects.live()), 'back_label': 'Back to news'})

@require_safe
def events(request):
    return render(request, 'school/events.html', build_calendar_context(request.GET))

@require_safe
def event(request, slug):
    item = get_object_or_404(Event, published=True, slug=slug)
    start = timezone.localtime(item.starts_at) if timezone.is_aware(item.starts_at) else item.starts_at
    return render(request, 'school/detail.html', {'item': item, 'body': item.description, 'introduction': '', 'kind': 'School calendar',
        'back_url': reverse('events') + f'?year={start.year}&month={start.month}#calendar-month-heading',
        'back_label': 'Back to calendar'})

@require_safe
def page(request, slug):
    # Existing core URLs remain valid; arbitrary database pages are no longer public.
    from django.http import Http404
    fixed_views = {'about': about, 'about-us': about, 'curriculum': curriculum,
                   'our-staff': staff_directory, 'staff': staff_directory}
    if slug not in fixed_views:
        raise Http404
    return fixed_views[slug](request)


@require_safe
def subject(request, slug):
    item = get_object_or_404(Subject, slug=slug, published=True)
    return render(request, 'school/detail.html', {'item': item, 'body': item.body,
        'introduction': item.introduction, 'kind': 'Curriculum',
        'is_subject': True, 'back_url': reverse('curriculum') + '#subjects', 'back_label': 'Back to curriculum'})

@require_http_methods(['GET', 'HEAD', 'POST'])
def contact(request):
    form = ContactForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your message has been received. The school office will respond using the contact details you provided.')
        return redirect('contact')
    return render(request, 'school/contact.html', {'form': form})
@require_safe
def privacy(request): return render(request, 'school/privacy.html')

def terms(request): return render(request, 'school/terms.html')

def donation(request): return render(request, 'school/donation.html')

@require_http_methods(['GET', 'HEAD', 'POST'])
def apply(request):
    school = SiteSettings.objects.first() or SiteSettings(email=settings.CONTACT_EMAIL, phone=settings.CONTACT_PHONE)
    form = ApplicationForm(request.POST if request.method == 'POST' else None, school=school)
    if request.method == 'POST' and school.admissions_open:
        if form.is_valid():
            application = form.save(commit=False)
            try:
                with transaction.atomic():
                    application.save()
            except IntegrityError:
                # The unique key handles concurrent submissions as well as browser retries.
                # Never reveal an existing applicant's reference or private details.
                from .submissions import application_identity
                key = application_identity(application.given_name, application.surname, application.date_of_birth,
                                           application.application_year, application.entry_level)
                if not key or not Application.objects.filter(duplicate_key=key).exists():
                    raise
                form.add_error(None, 'An application for these learner details and this intake has already been received. Please contact the school office if you need to correct or check an application.')
                return render(request, 'school/apply.html', {'form': form}, status=409)
            request.session['application_receipt'] = str(application.reference)
            return redirect('application-success')
    return render(request, 'school/apply.html', {'form': form})

@require_safe
def application_success(request):
    reference = request.session.get('application_receipt')
    if request.method == 'GET':
        request.session.pop('application_receipt', None)
    if not reference: return redirect('apply')
    return render(request, 'school/success.html', {'reference': reference})


@require_http_methods(['GET', 'HEAD'])
def school_life(request):
    posts = SchoolLifePost.objects.live().select_related('author')
    category = request.GET.get('category', '')
    categories = SchoolLifePost._meta.get_field('category').choices
    if category in dict(categories):
        posts = posts.filter(category=category)
    else:
        category = ''
    return render(request, 'school/school_life.html', {
        'items': Paginator(posts, 9).get_page(request.GET.get('page')),
        'categories': categories, 'selected_category': category})


@require_http_methods(['GET', 'HEAD'])
def school_life_post(request, slug):
    item = get_object_or_404(SchoolLifePost.objects.live().select_related('author'), slug=slug)
    return render(request, 'school/school_life_post.html', {'item': item,
        'back_url': writing_return_url(request, 'school-life', SchoolLifePost.objects.live(), item.category),
        'back_label': 'Back to School Life'})


@require_safe
def announcements(request):
    return render(request, 'school/community_list.html', {
        'items': Paginator(Announcement.objects.live(), 9).get_page(request.GET.get('page')),
        'section_title': 'Announcements', 'introduction': 'Notices and important updates from the school office.',
        'detail_route': 'announcement', 'list_route': 'announcements', 'is_announcement': True})


@require_safe
def announcement(request, slug):
    item = get_object_or_404(Announcement.objects.live(), slug=slug)
    return render(request, 'school/community_detail.html', {'item': item, 'section_title': 'Announcements',
        'back_url': writing_return_url(request, 'announcements', Announcement.objects.live()),
        'back_label': 'Back to announcements', 'is_announcement': True})


@require_safe
def projects(request):
    return render(request, 'school/community_list.html', {
        'items': Paginator(Project.objects.live(), 9).get_page(request.GET.get('page')),
        'section_title': 'Projects', 'introduction': 'Explore the initiatives and improvements taking shape at Holy Family.',
        'detail_route': 'project', 'list_route': 'projects'})


@require_safe
def project(request, slug):
    item = get_object_or_404(Project.objects.live(), slug=slug)
    return render(request, 'school/community_detail.html', {'item': item, 'section_title': 'Projects',
        'back_url': writing_return_url(request, 'projects', Project.objects.live()), 'back_label': 'Back to projects'})

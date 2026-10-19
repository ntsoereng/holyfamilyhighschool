"""Public metadata uses the configured school origin, never the request host."""
from html import unescape
import re
from urllib.parse import urlsplit, urlencode

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import Truncator
from django.utils.html import strip_tags

from .templatetags.email_protection import protect_email_text
from .models import Announcement, Project, Article, Department, Event, SiteSettings, StaffMember, Subject, SchoolLifePost


PRIMARY_PAGES = ('home', 'about', 'contact', 'curriculum', 'school-staff', 'events', 'apply', 'news', 'school-life', 'privacy', 'terms', 'donation', 'announcements', 'projects')
PUBLIC_DETAIL_PAGES = ('article', 'event', 'subject', 'school-department', 'school-staff-profile', 'school-life-post', 'announcement', 'project')
LEGACY_PAGES = {'about': 'about', 'about-us': 'about', 'curriculum': 'curriculum',
                'our-staff': 'school-staff', 'staff': 'school-staff'}


def canonical_origin():
    value = getattr(settings, 'SITE_URL', '').strip().rstrip('/')
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment or any(char.isspace() for char in value)
                or '\\' in value):
            return ''
        parsed.port  # Reject malformed ports even when settings are overridden at runtime.
    except ValueError:
        return ''
    return value


def school_for_request(request):
    if not hasattr(request, '_seo_school'):
        request._seo_school = SiteSettings.objects.first() or SiteSettings(
            email=settings.CONTACT_EMAIL, phone=settings.CONTACT_PHONE)
    return request._seo_school


def indexing_enabled(request):
    return bool(canonical_origin()) and not settings.DEBUG and not school_for_request(request).demo_mode


def public_staff():
    return StaffMember.objects.filter(published=True).filter(
        Q(is_management=True) | Q(departments__published=True) | Q(departments__isnull=True)).distinct()


def plain_description(value):
    text = re.sub(r'\s+', ' ', strip_tags(unescape(str(value or '')))).strip()
    return Truncator(protect_email_text(text)).chars(160)


def first_description(*values):
    return next((text for value in values if (text := plain_description(value))), '')


def absolute_url(path):
    origin = canonical_origin()
    return origin + path if origin and path.startswith('/') and not path.startswith('//') else ''


def metadata(request):
    match = request.resolver_match
    if not match:
        # Error handlers can render without requiring an available database.
        return {'seo': {'title': 'Holy Family High School', 'site_name': 'Holy Family High School',
                        'description': '', 'robots': 'noindex, nofollow', 'og_type': 'website'}}
    school = school_for_request(request)
    route = match.url_name if match else None
    kwargs = match.kwargs if match else {}
    if route == 'page':
        route = LEGACY_PAGES.get(kwargs.get('slug'))

    pages = {
        'home': (school.name, school.hero_text, school.hero_image, school.hero_image_alt),
        'about': (f'About · {school.name}', first_description(school.about_intro, school.about_text), school.about_image, school.about_image_alt),
        'contact': (f'Contact · {school.name}', school.contact_text, school.contact_image, school.contact_image_alt),
        'curriculum': (f'Curriculum · {school.name}', school.curriculum_intro, school.curriculum_image, school.curriculum_image_alt),
        'school-staff': (f'Our staff · {school.name}', school.staff_intro, school.staff_image, school.staff_image_alt),
        'events': (f'Calendar · {school.name}', school.calendar_intro, school.calendar_image, school.calendar_image_alt),
        'apply': (f'Admissions · {school.name}', school.admissions_text if school.admissions_open else f'Admissions at {school.name} are currently closed. Contact the school office for information about the next intake.', school.admissions_image if school.admissions_open else None, school.admissions_image_alt if school.admissions_open else ''),
        'school-life': ('School Life · ' + school.name, f'Stories, poems and articles by students at {school.name}.', None, ''),
        'announcements': (f'Announcements · {school.name}', f'Official school notices and important updates from {school.name}.', None, ''),
        'projects': (f'Projects · {school.name}', f'Explore planned, ongoing and completed projects at {school.name}.', None, ''),
        'news': (f'News · {school.name}', f'News, achievements and updates from {school.name}.', None, ''),
        'application-success': (f'Application received · {school.name}', 'Your application has been received. Keep your private reference for follow-up with the school office.', None, ''),
        'admission-results': (f'Check admission results · {school.name}', 'Search admitted students by surname and select the related primary school to view boarding status.', None, ''),
        'privacy': (f'Privacy Policy · {school.name}', f'How {school.name} uses personal information, protects learner data and handles cookies under Lesotho’s data protection law.', None, ''),
        'donation': (f'Donation · {school.name}', f'Support {school.name} through monetary or in-kind donations. Contact the school to discuss current needs and arrange your contribution.', None, ''),
        'terms': (f'Terms of Use · {school.name}', f'Terms for using the {school.name} website, submitting applications and enquiries, and sharing school and student content.', None, ''),
    }
    fallbacks = {
        'home': f'Explore learning, admissions, school life and community updates at {school.name}.',
        'about': f'Learn about the history, purpose and community of {school.name}.',
        'curriculum': f'Explore the subjects and learning opportunities at {school.name}.',
        'school-staff': f'Meet the school management, departments and staff at {school.name}.',
        'events': f'Explore events and important dates in the {school.name} school calendar.',
        'apply': f'Find admission information and submit an application to {school.name}.',
        'contact': f'Contact {school.name} with enquiries about admissions, learning and school life.',
        'privacy': f'How {school.name} handles personal information supplied through applications and enquiries.',
    }
    title, description, image, image_alt = pages.get(route, (school.name, '', None, ''))
    description = first_description(description, fallbacks.get(route))
    public = route in PRIMARY_PAGES
    path = reverse(route) if public else ''
    og_type = 'website'
    published_at = None

    item = None
    if route in {'announcement', 'project'}:
        model = Announcement if route == 'announcement' else Project
        item = model.objects.live().filter(slug=kwargs.get('slug')).first()
        if item:
            description = first_description(item.excerpt, item.body, item.title)
            og_type, published_at = 'article', item.published_at
    elif route == 'school-life-post':
        item = SchoolLifePost.objects.live().filter(slug=kwargs.get('slug')).first()
        if item:
            description = first_description(item.excerpt, item.body, f'Read {item.title}, a {item.get_category_display().lower()} by {item.author_name} at {school.name}.')
            og_type, published_at = 'article', item.published_at
    elif route == 'article':
        item = Article.objects.live().filter(slug=kwargs.get('slug')).first()
        if item:
            description = first_description(item.excerpt, item.body, f'Read {item.title}, news from {school.name}.')
            og_type, published_at = 'article', item.published_at
    elif route == 'event':
        item = Event.objects.filter(published=True, slug=kwargs.get('slug')).first()
        if item:
            description = first_description(item.description, f'{item.title} at {item.location}, {school.name}.')
    elif route == 'subject':
        item = Subject.objects.filter(published=True, slug=kwargs.get('slug')).first()
        if item:
            description = first_description(item.introduction, item.body, f'Explore {item.title} and learning at {school.name}.')
    elif route == 'school-department':
        item = Department.objects.filter(published=True, pk=kwargs.get('pk')).first()
        if item:
            description = first_description(item.description, f'Meet the {item.title} department and its staff at {school.name}.')
    elif route == 'school-staff-profile':
        item = public_staff().filter(slug=kwargs.get('slug')).first()
        if item:
            description = first_description(item.biography, f'{item.display_name}, {item.get_management_role_display() if item.is_management and item.management_role else item.position or "staff member"} at {school.name}.')

    if item:
        public = True
        section_title = ' · Our staff' if route in {'school-staff-profile', 'school-department'} else ' · School Life' if route == 'school-life-post' else ''
        title = f'{item.display_name if isinstance(item, StaffMember) else item.title}{section_title} · {school.name}'
        image = getattr(item, 'image', None)
        image_alt = getattr(item, 'image_alt', '')
        path = reverse(route, kwargs=kwargs)
    elif route in PUBLIC_DETAIL_PAGES:
        public = False

    if route in {'news', 'school-life', 'announcements', 'projects'}:
        posts = {'school-life': SchoolLifePost, 'news': Article, 'announcements': Announcement, 'projects': Project}[route].objects.live()
        query = {}
        category = request.GET.get('category', '')
        if route == 'school-life' and category in dict(SchoolLifePost._meta.get_field('category').choices):
            posts = posts.filter(category=category)
            query['category'] = category
        page_number = Paginator(posts, 9).get_page(request.GET.get('page')).number
        if 'category' in query:
            label = {'story': 'Stories', 'poem': 'Poems', 'article': 'Articles'}[category]
            title = f'{label} · School Life · {school.name}'
            description = f'{label} by students at {school.name}.'
        if page_number > 1:
            query['page'] = page_number
            title = title.removesuffix(' · ' + school.name) + f' · Page {page_number} · {school.name}'
            suffix = f' Page {page_number}.'
            description = Truncator(description).chars(160 - len(suffix)) + suffix
        if query:
            path += '?' + urlencode(query)

    parent = {'admission-results': 'apply', 'article': 'news', 'school-life-post': 'school-life', 'subject': 'curriculum',
              'school-department': 'school-staff', 'school-staff-profile': 'school-staff', 'event': 'events', 'announcement': 'announcements', 'project': 'projects'}.get(route, route)
    section = 'school' if parent in {'about', 'curriculum', 'school-staff'} else 'community' if parent in {'news', 'school-life', 'donation', 'announcements', 'projects'} else parent
    return {'seo': {
        'parent': parent, 'section': section,
        'title': title,
        'description': plain_description(description),
        'canonical': absolute_url(path) if public else '',
        'image': absolute_url(image.url if image else static('images/holy-family-favicon-512.png')),
        'image_alt': image_alt or school.name,
        'site_name': school.name,
        'locale': '_'.join(part if index == 0 else part.upper()
            for index, part in enumerate(getattr(settings, 'LANGUAGE_CODE', 'en-gb').replace('-', '_').split('_'))),
        'og_type': og_type,
        'published_at': published_at,
        'robots': 'index, follow, max-image-preview:large' if public and indexing_enabled(request) else 'noindex, nofollow',
    }}

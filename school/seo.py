"""Public metadata uses the configured school origin, never the request host."""
from html import unescape
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import Truncator
from django.utils.html import strip_tags

from .models import Article, Department, Event, SiteSettings, StaffMember, Subject


PRIMARY_PAGES = ('home', 'about', 'contact', 'curriculum', 'school-staff', 'events', 'apply', 'news', 'privacy')
PUBLIC_DETAIL_PAGES = ('article', 'event', 'subject', 'school-department', 'school-staff-profile')
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
        Q(departments__published=True) | Q(departments__isnull=True)).distinct()


def plain_description(value):
    text = re.sub(r'\s+', ' ', strip_tags(unescape(str(value or '')))).strip()
    return Truncator(text).chars(160)


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
        'about': (f'About · {school.name}', school.about_intro or school.about_text, school.about_image, school.about_image_alt),
        'contact': (f'Contact · {school.name}', school.contact_text, school.contact_image, school.contact_image_alt),
        'curriculum': (f'Curriculum · {school.name}', school.curriculum_intro, school.curriculum_image, school.curriculum_image_alt),
        'school-staff': (f'Our staff · {school.name}', school.staff_intro, school.staff_image, school.staff_image_alt),
        'events': (f'Calendar · {school.name}', school.calendar_intro, school.calendar_image, school.calendar_image_alt),
        'apply': (f'Admissions · {school.name}', school.admissions_text, school.admissions_image, school.admissions_image_alt),
        'news': (f'News & stories · {school.name}', f'News, achievements and updates from {school.name}.', None, ''),
        'privacy': (f'Privacy · {school.name}', school.privacy_text, None, ''),
    }
    title, description, image, image_alt = pages.get(route, (school.name, '', None, ''))
    public = route in PRIMARY_PAGES
    path = reverse(route) if public else ''
    og_type = 'website'
    published_at = None

    item = None
    if route == 'article':
        item = Article.objects.live().filter(slug=kwargs.get('slug')).first()
        if item:
            description = item.excerpt or item.body
            og_type, published_at = 'article', item.published_at
    elif route == 'event':
        item = Event.objects.filter(published=True, slug=kwargs.get('slug')).first()
        if item:
            description = item.description or f'{item.title} at {item.location}.'
    elif route == 'subject':
        item = Subject.objects.filter(published=True, slug=kwargs.get('slug')).first()
        if item:
            description = item.introduction or item.body or school.curriculum_intro
    elif route == 'school-department':
        item = Department.objects.filter(published=True, pk=kwargs.get('pk')).first()
        if item:
            description = item.description or school.staff_intro
    elif route == 'school-staff-profile':
        item = public_staff().filter(pk=kwargs.get('pk')).first()
        if item:
            description = item.biography or item.position or school.staff_intro

    if item:
        public = True
        title = f'{item.display_name if isinstance(item, StaffMember) else item.title} · {school.name}'
        image = getattr(item, 'image', None)
        image_alt = getattr(item, 'image_alt', '')
        path = reverse(route, kwargs=kwargs)
    elif route in PUBLIC_DETAIL_PAGES:
        public = False

    if route == 'news':
        page_number = Paginator(Article.objects.live(), 9).get_page(request.GET.get('page')).number
        if page_number > 1:
            path += f'?page={page_number}'

    return {'seo': {
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

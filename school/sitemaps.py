"""Django sitemaps share the same origin and visibility rules as metadata."""
from types import SimpleNamespace
from urllib.parse import urlsplit

from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_safe

from .models import Article, Department, Event, Subject
from .seo import PRIMARY_PAGES, absolute_url, canonical_origin, indexing_enabled, public_staff


class ConfiguredSitemap(Sitemap):
    def get_urls(self, page=1, site=None, protocol=None):
        origin = canonical_origin()
        if not origin:
            return []
        parsed = urlsplit(origin)
        return super().get_urls(page=page, site=SimpleNamespace(domain=parsed.netloc), protocol=parsed.scheme)


class PrimaryPagesSitemap(ConfiguredSitemap):
    def items(self):
        return PRIMARY_PAGES

    def location(self, item):
        return reverse(item)


class ArticleSitemap(ConfiguredSitemap):
    def items(self):
        return Article.objects.live()

    def location(self, item):
        return reverse('article', kwargs={'slug': item.slug})


class EventSitemap(ConfiguredSitemap):
    def items(self):
        return Event.objects.filter(published=True)

    def location(self, item):
        return reverse('event', kwargs={'slug': item.slug})


class SubjectSitemap(ConfiguredSitemap):
    def items(self):
        return Subject.objects.filter(published=True)

    def location(self, item):
        return reverse('subject', kwargs={'slug': item.slug})


class DepartmentSitemap(ConfiguredSitemap):
    def items(self):
        return Department.objects.filter(published=True)

    def location(self, item):
        return reverse('school-department', kwargs={'pk': item.pk})


class StaffProfileSitemap(ConfiguredSitemap):
    def items(self):
        return public_staff()

    def location(self, item):
        return reverse('school-staff-profile', kwargs={'pk': item.pk})


SITEMAPS = {'pages': PrimaryPagesSitemap, 'articles': ArticleSitemap, 'events': EventSitemap,
            'subjects': SubjectSitemap, 'departments': DepartmentSitemap, 'staff': StaffProfileSitemap}


@require_safe
def sitemap_view(request):
    if not indexing_enabled(request):
        return HttpResponse('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>', content_type='application/xml')
    return sitemap(request, sitemaps=SITEMAPS)


@require_safe
def robots_txt(request):
    if not indexing_enabled(request):
        return HttpResponse('User-agent: *\nDisallow: /\n', content_type='text/plain; charset=utf-8')
    lines = ['User-agent: *', 'Allow: /', 'Disallow: /staff/', 'Disallow: /admin/',
             'Disallow: /tinymce/', 'Disallow: /apply/received/', '', f'Sitemap: {absolute_url(reverse("sitemap"))}', '']
    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')

from .security import GOOGLE_MAPS_EMBED_ORIGINS
from .seo import PRIMARY_PAGES, PUBLIC_DETAIL_PAGES, indexing_enabled
from django.conf import settings


class IndexingHeadersMiddleware:
    """Cover early SecurityMiddleware/CommonMiddleware errors as well as views."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        match = request.resolver_match
        known_public_route = match and match.url_name in (
            *PRIMARY_PAGES, *PUBLIC_DETAIL_PAGES, 'page', 'sitemap', 'robots-txt')
        private = request.path.startswith(('/admin/', '/staff/', '/apply/received/', '/tinymce/'))
        if response.status_code >= 400 or private:
            response['X-Robots-Tag'] = 'noindex, nofollow'
        elif request.path.startswith((settings.STATIC_URL, settings.MEDIA_URL)):
            # Public images and favicons must remain crawlable; avoid a DB query per asset.
            pass
        elif 300 <= response.status_code < 400 and not match:
            # SecurityMiddleware redirects before URL resolution or database access.
            pass
        elif not known_public_route or not indexing_enabled(request):
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # TinyMCE needs inline styles inside the authenticated editor. Public pages do not.
        styles = "'self' 'unsafe-inline'" if (request.path.startswith('/admin/') or (request.path.startswith('/staff/') and request.user.is_authenticated and request.user.is_staff)) else "'self'"
        images = "'self' data:"
        if request.path.startswith('/staff/') and request.user.is_authenticated and request.user.is_staff:
            images += ' blob:'
        frames = "'self'"
        if request.resolver_match and request.resolver_match.url_name == 'contact':
            frames += ' ' + ' '.join(GOOGLE_MAPS_EMBED_ORIGINS)
        response['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src " + styles + "; "
            f"img-src {images}; font-src 'self'; connect-src 'self'; "
            f"frame-src {frames}; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
        if request.path.startswith(('/admin/', '/apply/', '/staff/', '/contact/')):
            response['Cache-Control'] = 'no-store, private'
        return response

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
        if request.path.rstrip('/') in {'/admissions/results', '/staff/admissions/results'}:
            # Include middleware errors and CSRF failures, not just rendered views.
            response['Cache-Control'] = 'no-store, private'
            # no-referrer can make native form POSTs send Origin: null, which
            # correctly fails Django's CSRF origin check. Keep same-site form
            # metadata while withholding referrers from external destinations.
            response['Referrer-Policy'] = 'same-origin'
            response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        if request.path.startswith(('/prospectus/', '/staff/admissions/prospectus/')):
            # Include revoked/missing file errors and middleware/CSRF failures.
            response['Cache-Control'] = 'no-store, private'
            response['Referrer-Policy'] = 'same-origin'
            response['X-Content-Type-Options'] = 'nosniff'
            if match and match.url_name in {'prospectus-page', 'prospectus-download'}:
                response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
                response['Content-Security-Policy'] = "default-src 'none'; sandbox"
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


class SubmissionSecurityMiddleware:
    """Bound all form writes before parsing; rate limits also count invalid/CSRF failures."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.http import HttpResponse
        from django.core.exceptions import RequestDataTooBig
        from .security import client_ip
        from .submissions import consume_limit, rate_subject

        def reject(message, status, retry=None):
            response = HttpResponse(message, status=status, content_type='text/plain; charset=utf-8')
            response['Cache-Control'] = 'no-store, private'
            response['X-Robots-Tag'] = 'noindex, nofollow'
            if retry:
                response['Retry-After'] = str(retry)
            return response

        if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return self.get_response(request)
        subject = rate_subject(client_ip(request))
        path = request.path.rstrip('/')
        lookup = path == '/admissions/results'
        public_form = path in {'/apply', '/contact', '/admissions/results'}
        limits = [('all-form-writes', settings.FORM_WRITE_RATE_PER_MINUTE, 60)]
        if lookup:
            limits += [('admission-lookup-minute', settings.ADMISSION_LOOKUP_RATE_PER_MINUTE, 60),
                       ('admission-lookup-hour', settings.ADMISSION_LOOKUP_RATE_PER_HOUR, 3600),
                       ('admission-lookup-day', settings.ADMISSION_LOOKUP_RATE_PER_DAY, 86400)]
        elif public_form:
            limits += [('public-forms-daily', settings.PUBLIC_FORM_RATE_PER_DAY, 86400),
                       (f'public-form:{request.path.rstrip("/")}', settings.PUBLIC_FORM_RATE_PER_HOUR, 3600)]
        for scope, limit, seconds in limits:
            retry = consume_limit(subject, scope, limit, seconds)
            if retry:
                return reject('Too many submission attempts. Please wait before trying again, or contact the school office by phone.', 429, retry)
        if path == '/staff/admissions/results' and request.method == 'POST':
            try:
                if int(request.META.get('CONTENT_LENGTH') or 0) > 2 * 1024 * 1024 + 65536:
                    return reject('Choose a spreadsheet smaller than 2 MB.', 413)
            except ValueError:
                return reject('Invalid upload size.', 413)
        if path == '/staff/admissions/prospectus' and request.method == 'POST':
            try:
                if not 0 <= int(request.META.get('CONTENT_LENGTH') or 0) <= 8 * 1024 * 1024 + 65536:
                    return reject('Choose a PDF no larger than 8 MB.', 413)
            except ValueError:
                return reject('Invalid upload size.', 413)
        if public_form and request.method == 'POST':
            try:
                declared_size = int(request.META.get('CONTENT_LENGTH') or 0)
                if declared_size < 0 or declared_size > settings.PUBLIC_FORM_MAX_BYTES:
                    return reject('This form submission is too large.', 413)
                if len(request.body) > settings.PUBLIC_FORM_MAX_BYTES:
                    return reject('This form submission is too large.', 413)
            except (ValueError, RequestDataTooBig):
                return reject('This form submission is too large.', 413)
            if request.content_type not in {'application/x-www-form-urlencoded', 'multipart/form-data'}:
                return reject('Please submit using the school website form.', 415)
            if request.FILES:
                return reject('File uploads are not accepted by this form.', 400)
            # Single-valued fields cannot be smuggled in as repeated parameters.
            if any(len(values) != 1 for _, values in request.POST.lists()):
                return reject('Please submit each form field only once.', 400)
        return self.get_response(request)

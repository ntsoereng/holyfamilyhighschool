from pathlib import Path
from datetime import timedelta
from urllib.parse import urlsplit
from decouple import AutoConfig, Choices, Csv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
# Resolve the root .env even when Passenger starts from another directory.
config = AutoConfig(search_path=BASE_DIR)
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)
SECRET_KEY = config('DJANGO_SECRET_KEY', default=config('SECRET_KEY', default='development-only-change-me'))
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default=config('ALLOWED_HOSTS', default='localhost,127.0.0.1'), cast=Csv())
CSRF_TRUSTED_ORIGINS = config('DJANGO_CSRF_TRUSTED_ORIGINS', default=config('CSRF_TRUSTED_ORIGINS', default=''), cast=Csv())
SITE_URL = config('SITE_URL', default='http://localhost:8000' if DEBUG else '').strip()
if SITE_URL:
    try:
        site_origin = urlsplit(SITE_URL)
        site_origin.port
        if (site_origin.scheme not in {'http', 'https'} or not site_origin.hostname
                or site_origin.username or site_origin.password or site_origin.path not in {'', '/'}
                or site_origin.query or site_origin.fragment or '\\' in SITE_URL
                or any(character.isspace() for character in SITE_URL)):
            raise ValueError
        if not DEBUG and (site_origin.scheme != 'https' or site_origin.hostname not in ALLOWED_HOSTS
                or site_origin.hostname.endswith('.example')):
            raise ValueError
    except ValueError:
        raise ImproperlyConfigured('SITE_URL must be an HTTP(S) origin without credentials, paths or query strings; production requires HTTPS and an explicit allowed production host.')
    SITE_URL = SITE_URL.rstrip('/')
if not DEBUG:
    if (len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5
            or SECRET_KEY.lower().startswith(('replace-', 'django-insecure-', 'development-only-'))):
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be a unique random secret of at least 50 characters in production.')
    if (not ALLOWED_HOSTS or any('*' in host or host.startswith('.') for host in ALLOWED_HOSTS)
            or set(ALLOWED_HOSTS).issubset({'localhost', '127.0.0.1', '[::1]'})):
        raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must contain explicit production hosts without wildcards.')
    if any(host.endswith('.example') for host in ALLOWED_HOSTS):
        raise ImproperlyConfigured('Replace the example domains in DJANGO_ALLOWED_HOSTS.')
    for origin in CSRF_TRUSTED_ORIGINS:
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or '*' in parsed.netloc
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ImproperlyConfigured('DJANGO_CSRF_TRUSTED_ORIGINS must contain explicit HTTPS origins without paths or wildcards.')
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'django.contrib.sitemaps',
    'tinymce', 'axes', 'school',
]
MIDDLEWARE = [
    'school.middleware.IndexingHeadersMiddleware',
    'django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'school.middleware.SecurityHeadersMiddleware', 'axes.middleware.AxesMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages',
        'school.context_processors.school_settings', 'school.seo.metadata', 'school.structured_data.metadata']}}]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
DATABASE_ENGINE = config('DATABASE_ENGINE', default='sqlite' if DEBUG else 'mysql').strip().lower()
if not DEBUG and DATABASE_ENGINE == 'sqlite':
    raise ImproperlyConfigured('Production requires DATABASE_ENGINE=mysql or mariadb.')
# Django uses the MySQL backend for both MySQL and MariaDB.
if DATABASE_ENGINE in {'mysql', 'mariadb'}:
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('MYSQL_DATABASE'),
        'USER': config('MYSQL_USER'),
        'PASSWORD': config('MYSQL_PASSWORD'),
        'HOST': config('MYSQL_HOST', default='localhost'),
        'PORT': config('MYSQL_PORT', default=3306, cast=int),
        'CONN_MAX_AGE': config('MYSQL_CONN_MAX_AGE', default=60, cast=int),
        'CONN_HEALTH_CHECKS': config('MYSQL_CONN_HEALTH_CHECKS', default=True, cast=bool),
        'OPTIONS': {'charset': 'utf8mb4', 'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"},
    }}
    if not DEBUG:
        for name, value in DATABASES['default'].items():
            if name in {'NAME', 'USER', 'PASSWORD'} and (not value.strip() or value.startswith(('replace-', 'cpanelaccount_'))):
                raise ImproperlyConfigured('Replace the MYSQL_DATABASE, MYSQL_USER and MYSQL_PASSWORD placeholders in production.')
elif DATABASE_ENGINE == 'sqlite':
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / config('SQLITE_PATH', default='db.sqlite3'),
        'OPTIONS': {'timeout': config('SQLITE_TIMEOUT', default=20, cast=int)},
    }}
else:
    raise ImproperlyConfigured('DATABASE_ENGINE must be mysql, mariadb or sqlite.')
AUTHENTICATION_BACKENDS = ['axes.backends.AxesStandaloneBackend', 'django.contrib.auth.backends.ModelBackend']
AXES_FAILURE_LIMIT = config('DJANGO_AXES_FAILURE_LIMIT', default=5, cast=int)
AXES_COOLOFF_TIME = timedelta(minutes=config('DJANGO_AXES_COOLOFF_MINUTES', default=30, cast=int))
AXES_LOCKOUT_PARAMETERS = ['ip_address']
AXES_RESET_ON_SUCCESS = config('DJANGO_AXES_RESET_ON_SUCCESS', default=True, cast=bool)
AXES_CLIENT_IP_CALLABLE = 'school.security.client_ip'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': config('DJANGO_PASSWORD_MIN_LENGTH', default=12, cast=int)}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = config('DJANGO_LANGUAGE_CODE', default='en-gb')
TIME_ZONE = config('DJANGO_TIME_ZONE', default='Africa/Maseru')
USE_I18N = config('DJANGO_USE_I18N', default=True, cast=bool)
USE_TZ = config('DJANGO_USE_TZ', default=True, cast=bool)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = config('DJANGO_STATIC_URL', default='/static/')
STATIC_ROOT = Path(config('DJANGO_STATIC_ROOT', default=str(BASE_DIR / 'staticfiles')))
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = config('DJANGO_MEDIA_URL', default='/media/')
MEDIA_ROOT = Path(config('DJANGO_MEDIA_ROOT', default=str(BASE_DIR / 'media')))
if not STATIC_URL.startswith('/') or not STATIC_URL.endswith('/') or STATIC_URL.startswith('//'):
    raise ImproperlyConfigured('DJANGO_STATIC_URL must be a local absolute URL path ending in /.')
if MEDIA_URL != '/media/':
    raise ImproperlyConfigured('DJANGO_MEDIA_URL must be /media/ for the staff editor image sanitizer.')
for name, path in {'DJANGO_STATIC_ROOT': STATIC_ROOT, 'DJANGO_MEDIA_ROOT': MEDIA_ROOT}.items():
    if not path.is_absolute():
        raise ImproperlyConfigured(f'{name} must be an absolute filesystem path.')
    if not DEBUG and any(part in {'cpanelaccount', 'CPANEL_USERNAME'} for part in path.parts):
        raise ImproperlyConfigured(f'Replace the account placeholder in {name}.')
# Neither public file directory may expose the application source or overlap uploads.
roots = [STATIC_ROOT.resolve(), MEDIA_ROOT.resolve()]
if any(BASE_DIR.is_relative_to(root) for root in roots):
    raise ImproperlyConfigured('Static and media roots must not contain the application source.')
if roots[0].is_relative_to(roots[1]) or roots[1].is_relative_to(roots[0]):
    raise ImproperlyConfigured('Static and media roots must be separate, non-overlapping directories.')
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
SECURE_SSL_REDIRECT = config('DJANGO_SECURE_SSL_REDIRECT', default=not DEBUG, cast=bool)
SESSION_COOKIE_SECURE = config('DJANGO_SESSION_COOKIE_SECURE', default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = config('DJANGO_CSRF_COOKIE_SECURE', default=not DEBUG, cast=bool)
SECURE_HSTS_SECONDS = config('DJANGO_SECURE_HSTS_SECONDS', default=0 if DEBUG else 3600, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('DJANGO_SECURE_HSTS_PRELOAD', default=False, cast=bool)
if SECURE_HSTS_SECONDS < 0:
    raise ImproperlyConfigured('DJANGO_SECURE_HSTS_SECONDS must not be negative.')
if SECURE_HSTS_PRELOAD and (SECURE_HSTS_SECONDS < 31536000 or not SECURE_HSTS_INCLUDE_SUBDOMAINS):
    raise ImproperlyConfigured('HSTS preload requires at least one year and includeSubDomains.')
if not DEBUG and not all((SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE)):
    raise ImproperlyConfigured('Production requires HTTPS redirects and secure session/CSRF cookies.')
SECURE_CONTENT_TYPE_NOSNIFF = config('DJANGO_SECURE_CONTENT_TYPE_NOSNIFF', default=True, cast=bool)
SECURE_CROSS_ORIGIN_OPENER_POLICY = config('DJANGO_SECURE_CROSS_ORIGIN_OPENER_POLICY', default='same-origin', cast=Choices(['same-origin', 'same-origin-allow-popups', 'unsafe-none']))
SECURE_REFERRER_POLICY = config('DJANGO_SECURE_REFERRER_POLICY', default='strict-origin-when-cross-origin', cast=Choices(['no-referrer', 'same-origin', 'strict-origin', 'strict-origin-when-cross-origin']))
X_FRAME_OPTIONS = config('DJANGO_X_FRAME_OPTIONS', default='DENY', cast=Choices(['DENY', 'SAMEORIGIN']))
SESSION_COOKIE_HTTPONLY = config('DJANGO_SESSION_COOKIE_HTTPONLY', default=True, cast=bool)
CSRF_COOKIE_HTTPONLY = config('DJANGO_CSRF_COOKIE_HTTPONLY', default=True, cast=bool)
SESSION_COOKIE_SAMESITE = config('DJANGO_SESSION_COOKIE_SAMESITE', default='Lax', cast=Choices(['Lax', 'Strict']))
CSRF_COOKIE_SAMESITE = config('DJANGO_CSRF_COOKIE_SAMESITE', default='Lax', cast=Choices(['Lax', 'Strict']))
SESSION_COOKIE_AGE = config('DJANGO_SESSION_COOKIE_AGE', default=28800, cast=int)
if not DEBUG and not all((SECURE_CONTENT_TYPE_NOSNIFF, SESSION_COOKIE_HTTPONLY, CSRF_COOKIE_HTTPONLY)):
    raise ImproperlyConfigured('Production requires nosniff and HttpOnly session/CSRF cookies.')
if AXES_FAILURE_LIMIT < 1 or AXES_COOLOFF_TIME <= timedelta(0) or SESSION_COOKIE_AGE < 1:
    raise ImproperlyConfigured('Login limits, cooloff minutes and session lifetime must be positive.')
if AUTH_PASSWORD_VALIDATORS[1]['OPTIONS']['min_length'] < 12:
    raise ImproperlyConfigured('DJANGO_PASSWORD_MIN_LENGTH must be at least 12.')
# Enable only behind a proxy that strips incoming X-Forwarded-Proto.
USE_X_FORWARDED_HOST = config('DJANGO_USE_X_FORWARDED_HOST', default=False, cast=bool)
if config('DJANGO_TRUST_X_FORWARDED_PROTO', default=config('TRUST_PROXY_HTTPS', default=False, cast=bool), cast=bool):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
DATA_UPLOAD_MAX_MEMORY_SIZE = config('DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE', default=5 * 1024 * 1024, cast=int)
FILE_UPLOAD_MAX_MEMORY_SIZE = config('DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE', default=5 * 1024 * 1024, cast=int)
DATA_UPLOAD_MAX_NUMBER_FILES = config('DJANGO_DATA_UPLOAD_MAX_NUMBER_FILES', default=10, cast=int)
if min(DATA_UPLOAD_MAX_MEMORY_SIZE, FILE_UPLOAD_MAX_MEMORY_SIZE, DATA_UPLOAD_MAX_NUMBER_FILES) < 1:
    raise ImproperlyConfigured('Upload memory and file-count limits must be positive.')
FILE_UPLOAD_PERMISSIONS = 0o644
TINYMCE_DEFAULT_CONFIG = {'height': 420, 'menubar': False,
    'language': 'en_US', 'license_key': 'gpl', 'base_url': '/static/tinymce', 'suffix': '.min',
    'plugins': 'link lists code', 'toolbar': 'undo redo | blocks | bold italic | bullist numlist | link | removeformat code',
    'promotion': False, 'branding': False}
TINYMCE_EXTRA_MEDIA = {'css': {'all': ['css/editor.css']}}

CONTACT_EMAIL = config('CONTACT_EMAIL', default='holyfamilyhighschool56@gmail.com')
CONTACT_PHONE = config('CONTACT_PHONE', default='+266 2243 0282')
LOG_LEVEL = config('DJANGO_LOG_LEVEL', default='INFO', cast=Choices(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']))
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': LOG_LEVEL},
}

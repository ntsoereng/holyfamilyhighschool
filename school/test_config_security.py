"""Verify startup guards without a production database or real credentials."""
import os
from pathlib import Path
import subprocess
import sys

from django.test import SimpleTestCase
from django.test import override_settings
from .checks import canonical_site_url


class ProductionConfigurationTests(SimpleTestCase):
    @override_settings(DEBUG=False, SITE_URL='')
    def test_production_deployment_check_requires_actual_canonical_origin(self):
        self.assertEqual([issue.id for issue in canonical_site_url(None)], ['school.E001'])

    @override_settings(DEBUG=False, SITE_URL='https://school.test')
    def test_production_deployment_check_accepts_configured_canonical_origin(self):
        self.assertEqual(canonical_site_url(None), [])

    def load_settings(self, code='import config.settings', **overrides):
        env = dict(os.environ)
        env.update({
            'DJANGO_DEBUG': 'False',
            'DJANGO_SECRET_KEY': 'test-only-abcdefghijklmnopqrstuvwxyz0123456789-ABCDEFGHIJKLMN',
            'DJANGO_ALLOWED_HOSTS': 'school.test,www.school.test',
            'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://school.test,https://www.school.test',
            'SITE_URL': 'https://school.test',
            'DATABASE_ENGINE': 'mysql',
            'MYSQL_DATABASE': 'test_school', 'MYSQL_USER': 'test_school_user',
            'MYSQL_PASSWORD': 'test-only-database-password',
            'DJANGO_STATIC_URL': '/static/', 'DJANGO_MEDIA_URL': '/media/',
            'DJANGO_STATIC_ROOT': '/tmp/holyfamily-security/static',
            'DJANGO_MEDIA_ROOT': '/tmp/holyfamily-security/media',
            'DJANGO_SECURE_SSL_REDIRECT': 'True',
            'DJANGO_SESSION_COOKIE_SECURE': 'True',
            'DJANGO_CSRF_COOKIE_SECURE': 'True',
            'DJANGO_SECURE_HSTS_SECONDS': '3600',
            'DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS': 'False',
            'DJANGO_SECURE_HSTS_PRELOAD': 'False',
            'DJANGO_USE_X_FORWARDED_HOST': 'False',
            'DJANGO_TRUST_X_FORWARDED_PROTO': 'False',
            'DJANGO_LOG_LEVEL': 'INFO',
        })
        env.update(overrides)
        return subprocess.run(
            [sys.executable, '-c', code], env=env,
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, timeout=10,
        )

    def test_mysql_and_mariadb_production_configuration(self):
        for engine in ('mysql', 'mariadb'):
            with self.subTest(engine=engine):
                result = self.load_settings(DATABASE_ENGINE=engine)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_unsafe_production_configuration_fails_at_startup(self):
        cases = [
            {'DJANGO_SECRET_KEY': 'replace-with-a-long-random-secret-key-of-at-least-50-characters'},
            {'SITE_URL': 'http://school.test'},
            {'SITE_URL': 'https://another-school.test'},
            {'SITE_URL': 'https://user:password@school.test'},
            {'SITE_URL': 'https://school.test/subdirectory'},
            {'SITE_URL': 'https://school.test?tracking=example'},
            {'SITE_URL': 'https://school.test#section'},
            {'DJANGO_SECRET_KEY': 'x' * 60},
            {'DJANGO_SECRET_KEY': 'django-insecure-' + 'abcdefghijklmnopqrstuvwxyz' * 2},
            {'DJANGO_ALLOWED_HOSTS': ''},
            {'DJANGO_ALLOWED_HOSTS': '*'},
            {'DJANGO_ALLOWED_HOSTS': '.school.test'},
            {'DJANGO_ALLOWED_HOSTS': 'localhost,127.0.0.1'},
            {'DJANGO_ALLOWED_HOSTS': 'school.example'},
            {'DJANGO_CSRF_TRUSTED_ORIGINS': 'http://school.test'},
            {'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://*.school.test'},
            {'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://school.test/path'},
            {'MYSQL_PASSWORD': ''},
            {'MYSQL_PASSWORD': 'replace-with-the-mysql-user-password'},
            {'DATABASE_ENGINE': 'sqlite'},
            {'DJANGO_STATIC_ROOT': 'relative/static'},
            {'DJANGO_STATIC_ROOT': '/home/cpanelaccount/public_html/static'},
            {'DJANGO_STATIC_ROOT': '/'},
            {'DJANGO_MEDIA_ROOT': '/tmp/holyfamily-security/static/uploads'},
            {'DJANGO_MEDIA_URL': '/uploads/'},
            {'DJANGO_STATIC_URL': '//external.test/'},
            {'DJANGO_SECURE_SSL_REDIRECT': 'False'},
            {'DJANGO_SESSION_COOKIE_SECURE': 'False'},
            {'DJANGO_CSRF_COOKIE_SECURE': 'False'},
            {'DJANGO_SECURE_HSTS_SECONDS': '-1'},
            {'DJANGO_SECURE_HSTS_PRELOAD': 'True'},
            {'DJANGO_SESSION_COOKIE_HTTPONLY': 'False'},
            {'DJANGO_SECURE_CONTENT_TYPE_NOSNIFF': 'False'},
            {'DJANGO_AXES_FAILURE_LIMIT': '0'},
            {'DJANGO_AXES_COOLOFF_MINUTES': '0'},
            {'DJANGO_PASSWORD_MIN_LENGTH': '8'},
            {'DJANGO_SESSION_COOKIE_AGE': '0'},
            {'DJANGO_DATA_UPLOAD_MAX_NUMBER_FILES': '0'},
        ]
        for overrides in cases:
            with self.subTest(setting=next(iter(overrides))):
                result = self.load_settings(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ImproperlyConfigured', result.stderr)

    def test_invalid_log_level_is_rejected(self):
        result = self.load_settings(DJANGO_LOG_LEVEL='INVALID')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Value not in list', result.stderr)

    def test_missing_canonical_origin_is_a_deployment_error(self):
        code = '''
import django
django.setup()
from django.core.checks import run_checks
issues = run_checks(include_deployment_checks=True)
assert 'school.E001' in [issue.id for issue in issues]
'''
        result = self.load_settings(code=code, DJANGO_SETTINGS_MODULE='config.settings', SITE_URL='')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_development_retains_http_and_sqlite(self):
        result = self.load_settings(
            DJANGO_DEBUG='True', DATABASE_ENGINE='sqlite',
            DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1',
            DJANGO_SECURE_SSL_REDIRECT='False',
            DJANGO_SESSION_COOKIE_SECURE='False', DJANGO_CSRF_COOKIE_SECURE='False',
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mysql_backend_uses_pymysql_without_connecting(self):
        code = '''
import django
django.setup()
import pymysql
import MySQLdb
from django.db import connections
assert MySQLdb is pymysql
assert connections['default'].Database is pymysql
assert connections['default'].vendor == 'mysql'
'''
        for engine in ('mysql', 'mariadb'):
            result = self.load_settings(code=code, DJANGO_SETTINGS_MODULE='config.settings', DATABASE_ENGINE=engine)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_environment_values_are_cast_and_override_defaults(self):
        code = '''
from datetime import timedelta
from config import settings as s
assert s.TIME_ZONE == 'UTC'
assert s.LANGUAGE_CODE == 'en-us'
assert s.USE_I18N is False
assert s.AXES_FAILURE_LIMIT == 7
assert s.AXES_COOLOFF_TIME == timedelta(minutes=45)
assert s.SESSION_COOKIE_AGE == 7200
assert s.SESSION_COOKIE_SAMESITE == 'Strict'
assert s.DATA_UPLOAD_MAX_NUMBER_FILES == 3
assert s.AUTH_PASSWORD_VALIDATORS[1]['OPTIONS']['min_length'] == 16
'''
        result = self.load_settings(
            code=code, DJANGO_TIME_ZONE='UTC', DJANGO_LANGUAGE_CODE='en-us',
            DJANGO_USE_I18N='False', DJANGO_AXES_FAILURE_LIMIT='7',
            DJANGO_AXES_COOLOFF_MINUTES='45', DJANGO_SESSION_COOKIE_AGE='7200',
            DJANGO_SESSION_COOKIE_SAMESITE='Strict', DJANGO_DATA_UPLOAD_MAX_NUMBER_FILES='3',
            DJANGO_PASSWORD_MIN_LENGTH='16',
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_omitted_runtime_values_keep_defaults(self):
        # Bypass the real .env to verify defaults independently of local edits.
        code = '''
import os
from unittest.mock import patch
from decouple import Config, RepositoryEmpty
from datetime import timedelta
for name in ('DJANGO_TIME_ZONE', 'DJANGO_LANGUAGE_CODE', 'DJANGO_USE_I18N',
             'DJANGO_USE_TZ', 'DJANGO_AXES_FAILURE_LIMIT', 'DJANGO_AXES_COOLOFF_MINUTES',
             'DJANGO_SESSION_COOKIE_AGE', 'DJANGO_PASSWORD_MIN_LENGTH'):
    os.environ.pop(name, None)
with patch('decouple.AutoConfig', return_value=Config(RepositoryEmpty())):
    from config import settings as s
assert s.TIME_ZONE == 'Africa/Maseru'
assert s.LANGUAGE_CODE == 'en-gb'
assert s.USE_I18N is True and s.USE_TZ is True
assert s.AXES_FAILURE_LIMIT == 5
assert s.AXES_COOLOFF_TIME == timedelta(minutes=30)
assert s.SESSION_COOKIE_AGE == 28800
assert s.AUTH_PASSWORD_VALIDATORS[1]['OPTIONS']['min_length'] == 12
'''
        result = self.load_settings(code=code)
        self.assertEqual(result.returncode, 0, result.stderr)

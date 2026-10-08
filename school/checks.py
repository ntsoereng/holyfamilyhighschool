"""Checks that must be resolved against the actual deployment environment."""
from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def canonical_site_url(app_configs, **kwargs):
    if not settings.DEBUG and not getattr(settings, 'SITE_URL', ''):
        return [Error(
            'SITE_URL is required for production canonical URLs and the sitemap.',
            hint='Set SITE_URL to the school’s actual HTTPS origin in .env (for example https://your-school-domain).',
            id='school.E001',
        )]
    return []

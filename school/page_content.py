"""Preserve imported content while the public page structure stays fixed."""
from .models import Page, SiteSettings


def copy_legacy_content():
    site, _ = SiteSettings.objects.get_or_create(pk=1)
    for key, slugs, extras in [
        ('about', ['about', 'about-us'], {'body': 'about_history', 'mission': 'about_mission', 'vision': 'about_vision'}),
        ('curriculum', ['curriculum', 'academics'], {'body': 'curriculum_body'}),
        ('staff', ['our-staff', 'staff'], {}),
    ]:
        page = Page.objects.filter(slug__in=slugs).order_by('-published', 'order').first()
        if not page:
            continue
        for source, target in {'title': key + '_heading', 'introduction': key + '_intro',
                               'image': key + '_image', 'image_alt': key + '_image_alt', **extras}.items():
            value = getattr(page, source)
            current = getattr(site, target)
            default = SiteSettings._meta.get_field(target).get_default()
            if value and (not current or current == default):
                setattr(site, target, value)
    site.save()

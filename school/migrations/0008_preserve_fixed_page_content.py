from django.db import migrations


def preserve_content(apps, schema_editor):
    Page = apps.get_model('school', 'Page')
    SiteSettings = apps.get_model('school', 'SiteSettings')
    alias = schema_editor.connection.alias
    pages = Page.objects.using(alias)
    site = SiteSettings.objects.using(alias).first()
    if not site:
        if not pages.exists():
            return
        site = SiteSettings.objects.using(alias).create(pk=1)
    mappings = {'about': {'body': 'about_history', 'mission': 'about_mission', 'vision': 'about_vision'},
                'curriculum': {'body': 'curriculum_body'}, 'staff': {}}
    for key, extra in mappings.items():
        candidates = pages.filter(slug__in={'about': ['about', 'about-us'], 'curriculum': ['curriculum', 'academics'], 'staff': ['our-staff', 'staff']}[key])
        page = candidates.order_by('-published', 'order').first()
        if not page and key in {'curriculum', 'staff'}:
            page = pages.filter(layout=key).order_by('-published', 'order').first()
        if not page:
            continue
        for source, target in {'title': key + '_heading', 'introduction': key + '_intro',
                               'image': key + '_image', 'image_alt': key + '_image_alt', **extra}.items():
            value = getattr(page, source)
            current = getattr(site, target)
            default = SiteSettings._meta.get_field(target).get_default()
            if value and (not current or current == default):
                setattr(site, target, value)
    site.save(using=alias)


class Migration(migrations.Migration):
    dependencies = [('school', '0007_sitesettings_about_heading_and_more')]
    operations = [migrations.RunPython(preserve_content, migrations.RunPython.noop)]

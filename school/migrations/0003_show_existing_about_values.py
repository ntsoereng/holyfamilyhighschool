from django.db import migrations


def enable_about_values(apps, schema_editor):
    Page = apps.get_model('school', 'Page')
    Page.objects.using(schema_editor.connection.alias).filter(slug__in=['about', 'about-us']).update(show_school_values=True)


class Migration(migrations.Migration):
    dependencies = [('school', '0002_event_image_event_image_alt_page_image_and_more')]
    operations = [migrations.RunPython(enable_about_values, migrations.RunPython.noop)]

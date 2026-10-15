from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    StaffMember = apps.get_model('school', 'StaffMember')
    used = set()
    for member in StaffMember.objects.using(schema_editor.connection.alias).order_by('pk'):
        base = slugify(member.title)[:160] or 'staff-member'
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f'{base}-{suffix}'
            suffix += 1
        used.add(candidate)
        member.slug = candidate
        member.save(update_fields=['slug'])


class Migration(migrations.Migration):
    dependencies = [('school', '0013_staffmember_is_management')]
    operations = [
        migrations.AddField(model_name='staffmember', name='management_role', field=models.CharField(blank=True, max_length=30, choices=[('principal', 'Principal'), ('deputy-principal', 'Deputy Principal'), ('head-of-department', 'Head of Department')])),
        migrations.AddField(model_name='staffmember', name='slug', field=models.SlugField(blank=True, max_length=180, null=True)),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
        migrations.AlterField(model_name='staffmember', name='slug', field=models.SlugField(blank=True, max_length=180, unique=True)),
    ]

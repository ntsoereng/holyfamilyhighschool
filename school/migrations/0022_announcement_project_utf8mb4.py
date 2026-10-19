from django.db import migrations


def convert_content_tables(apps, schema_editor):
    # The connection charset does not change existing columns or table defaults.
    # Django also uses vendor='mysql' for MariaDB; SQLite needs no conversion.
    if schema_editor.connection.vendor != 'mysql':
        return
    for model_name in ('Announcement', 'Project'):
        table = apps.get_model('school', model_name)._meta.db_table
        schema_editor.execute(
            f'ALTER TABLE {schema_editor.quote_name(table)} '
            'CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('school', '0021_alter_sitesettings_admissions_interview_date'),
    ]

    # Deliberately irreversible: downgrading could destroy four-byte characters.
    operations = [migrations.RunPython(convert_content_tables, atomic=False)]
